"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { RefreshAudit } from "@/lib/snapshot-freshness";

export type Region = "中国" | "美国" | "全球";
export type EventType =
  | "融资"
  | "产业投资"
  | "产品发布"
  | "技术突破"
  | "商业进展"
  | "公司动态"
  | "并购"
  | "财报"
  | "政策"
  | "监管文件"
  | "IPO"
  | "论文"
  | "人物观点";

export type IntelligenceSource = {
  name: string;
  url: string;
  level:
    | "官方披露"
    | "原始材料"
    | "监管文件"
    | "媒体报道"
    | "数据库记录"
    | "待交叉验证";
  platform?: string;
};

export type IntelligenceEvent = {
  id: string;
  title: string;
  summary: string;
  type: EventType;
  region: Region;
  sector: string;
  company: string;
  companySlug?: string;
  personSlug?: string;
  sourceId?: string;
  authors?: string[];
  institutions?: string[];
  publishedAt: string;
  importance: number;
  source: IntelligenceSource;
  curated?: boolean;
};

export type RelatedArticleSource = {
  name: string;
  url: string;
  level: string;
  platform: string;
  title: string;
  publishedAt: string;
};

export type LiveIntelligenceEvent = IntelligenceEvent & {
  qualityScore?: number;
  qualityStatus?: "高可信" | "可用" | "低可信";
  qualitySignals?: string[];
  relatedSources?: RelatedArticleSource[];
  duplicateCount?: number;
  eventClusterId?: string;
  wechatAccount?: string;
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  matchedTrackingTerms?: string[];
};

export type ArticleSourceStatus = {
  id: string;
  name: string;
  status: string;
  scanned: number;
  accepted: number;
  failed?: number;
  platform?: string;
  error?: string;
};

export type ArticleQualityGate = {
  passed: boolean;
  checks: Record<string, { actual: number; required: number; passed: boolean }>;
  invalidArticles?: { id: string; errors: string[] }[];
  trackingQuality?: {
    scoredUserArticles: number;
    acceptedUserArticles: number;
    rejectedUserArticles: number;
    clusteredDuplicates: number;
    minimumScore: number;
  };
};

export type ArticlePayload = {
  schemaVersion: number;
  generatedAt: string;
  articleCount: number;
  articles: LiveIntelligenceEvent[];
  sourceStatus?: ArticleSourceStatus[];
  qualityGate?: ArticleQualityGate;
  refreshAudit?: RefreshAudit;
};

const emptyPayload: ArticlePayload = {
  schemaVersion: 1,
  generatedAt: "",
  articleCount: 0,
  articles: [],
  sourceStatus: [],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/**
 * Browser reads only a shallow contract here. The production snapshot is
 * already validated article-by-article by the crawler, Pages build and public
 * artifact gates. Repeating the full Zod walk over ~2.4 MB on every page load
 * created a long synchronous task on the browser main thread.
 */
export function parseArticlePayload(value: unknown): ArticlePayload {
  if (!isRecord(value)) throw new Error("Public article data is not an object");
  if (typeof value.schemaVersion !== "number") {
    throw new Error("Public article data is missing schemaVersion");
  }
  if (typeof value.generatedAt !== "string") {
    throw new Error("Public article data is missing generatedAt");
  }
  if (!Array.isArray(value.articles)) {
    throw new Error("Public article data is missing articles");
  }

  const first = value.articles[0];
  if (
    first !== undefined &&
    (!isRecord(first) ||
      typeof first.id !== "string" ||
      typeof first.title !== "string" ||
      !isRecord(first.source) ||
      typeof first.source.url !== "string")
  ) {
    throw new Error("Public article data has an invalid article contract");
  }

  return value as unknown as ArticlePayload;
}

async function fetchArticles(): Promise<ArticlePayload> {
  const response = await fetch("/data/articles.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Public article data returned ${response.status}`);
  }
  return parseArticlePayload(await response.json());
}

export function useArticles(
  initialPayload: ArticlePayload = emptyPayload,
  options: { enabled?: boolean } = {},
) {
  // With build-time bootstrap data available, wait until the first real user
  // interaction before loading the complete multi-megabyte event archive.
  // Callers can still opt into immediate or fully disabled loading explicitly.
  const [interactionEnabled, setInteractionEnabled] = useState(false);

  useEffect(() => {
    if (options.enabled !== undefined || interactionEnabled) return;
    const activate = () => setInteractionEnabled(true);
    window.addEventListener("pointerdown", activate, { once: true, passive: true });
    window.addEventListener("keydown", activate, { once: true });
    return () => {
      window.removeEventListener("pointerdown", activate);
      window.removeEventListener("keydown", activate);
    };
  }, [interactionEnabled, options.enabled]);

  const enabled = options.enabled ?? interactionEnabled;
  const query = useQuery({
    queryKey: ["public-articles"],
    queryFn: fetchArticles,
    placeholderData: initialPayload,
    enabled,
    staleTime: 20 * 60_000,
    refetchInterval: enabled ? 30 * 60_000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
  });
  const payload = query.data ?? initialPayload;
  return {
    ...query,
    articles: payload.articles,
    generatedAt: payload.generatedAt,
    sourceStatus: payload.sourceStatus ?? [],
    qualityGate: payload.qualityGate,
    refreshAudit: payload.refreshAudit,
    isLive: enabled && query.isSuccess && !query.isPlaceholderData,
  };
}
