"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import {
  intelligenceEvents,
  snapshotDate,
  type IntelligenceEvent,
} from "@/lib/intelligence-data";

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
};

const eventTypeSchema = z.enum([
  "融资",
  "产业投资",
  "产品发布",
  "技术突破",
  "商业进展",
  "公司动态",
  "并购",
  "财报",
  "政策",
  "监管文件",
  "IPO",
  "论文",
  "人物观点",
]);

const relatedSourceSchema = z.object({
  name: z.string(),
  url: z.url(),
  level: z.string(),
  platform: z.string(),
  title: z.string(),
  publishedAt: z.string(),
});

const articleSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  type: eventTypeSchema,
  region: z.enum(["中国", "美国", "全球"]),
  sector: z.string(),
  company: z.string(),
  companySlug: z.string().optional(),
  personSlug: z.string().optional(),
  sourceId: z.string().optional(),
  authors: z.array(z.string()).optional(),
  institutions: z.array(z.string()).optional(),
  publishedAt: z.string(),
  importance: z.number().min(0).max(100),
  source: z.object({
    name: z.string(),
    url: z.url(),
    level: z.enum([
      "官方披露",
      "原始材料",
      "监管文件",
      "媒体报道",
      "数据库记录",
      "待交叉验证",
    ]),
    platform: z.string().optional(),
  }),
  curated: z.boolean().optional(),
  qualityScore: z.number().min(0).max(100).optional(),
  qualityStatus: z.enum(["高可信", "可用", "低可信"]).optional(),
  qualitySignals: z.array(z.string()).optional(),
  relatedSources: z.array(relatedSourceSchema).optional(),
  duplicateCount: z.number().int().nonnegative().optional(),
  eventClusterId: z.string().optional(),
});

const payloadSchema = z.object({
  schemaVersion: z.number(),
  generatedAt: z.string(),
  articleCount: z.number(),
  articles: z.array(articleSchema),
  companyFacts: z.record(z.string(), z.unknown()).optional(),
  sourceStatus: z.array(z.object({
    id: z.string(),
    name: z.string(),
    status: z.string(),
    scanned: z.number(),
    accepted: z.number(),
    failed: z.number().optional(),
    platform: z.string().optional(),
    error: z.string().optional(),
  })).optional(),
  qualityGate: z.object({
    passed: z.boolean(),
    checks: z.record(z.string(), z.object({
      actual: z.number(),
      required: z.number(),
      passed: z.boolean(),
    })),
    invalidArticles: z.array(z.object({
      id: z.string(),
      errors: z.array(z.string()),
    })).optional(),
    trackingQuality: z.object({
      scoredUserArticles: z.number().int().nonnegative(),
      acceptedUserArticles: z.number().int().nonnegative(),
      rejectedUserArticles: z.number().int().nonnegative(),
      clusteredDuplicates: z.number().int().nonnegative(),
      minimumScore: z.number().min(0).max(100),
    }).optional(),
  }).optional(),
});

type ArticlePayload = z.infer<typeof payloadSchema>;

const fallbackPayload: ArticlePayload = {
  schemaVersion: 1,
  generatedAt: `${snapshotDate}T00:00:00Z`,
  articleCount: intelligenceEvents.length,
  articles: intelligenceEvents,
  companyFacts: {},
  sourceStatus: [],
  qualityGate: undefined,
};

async function fetchArticles(): Promise<ArticlePayload> {
  const response = await fetch("/data/articles.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Public article data returned ${response.status}`);
  }
  return payloadSchema.parse(await response.json());
}

export function useArticles() {
  const query = useQuery({
    queryKey: ["public-articles"],
    queryFn: fetchArticles,
    placeholderData: fallbackPayload,
  });
  const payload = query.data ?? fallbackPayload;
  return {
    ...query,
    articles: payload.articles as LiveIntelligenceEvent[],
    generatedAt: payload.generatedAt,
    sourceStatus: payload.sourceStatus ?? [],
    qualityGate: payload.qualityGate,
    isLive: query.isSuccess && !query.isPlaceholderData,
  };
}
