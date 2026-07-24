"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import {
  intelligenceEvents,
  snapshotDate,
  type IntelligenceEvent,
} from "@/lib/intelligence-data";

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
]);

const articleSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  type: eventTypeSchema,
  region: z.enum(["中国", "美国", "全球"]),
  sector: z.string(),
  company: z.string(),
  companySlug: z.string().optional(),
  institutions: z.array(z.string()).optional(),
  publishedAt: z.string(),
  importance: z.number().min(0).max(100),
  source: z.object({
    name: z.string(),
    url: z.url(),
    level: z.enum(["官方披露", "原始材料", "监管文件"]),
  }),
  curated: z.boolean().optional(),
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
  })).optional(),
});

type ArticlePayload = z.infer<typeof payloadSchema>;

const fallbackPayload: ArticlePayload = {
  schemaVersion: 1,
  generatedAt: `${snapshotDate}T00:00:00Z`,
  articleCount: intelligenceEvents.length,
  articles: intelligenceEvents,
  companyFacts: {},
  sourceStatus: [],
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
    articles: payload.articles as IntelligenceEvent[],
    generatedAt: payload.generatedAt,
    sourceStatus: payload.sourceStatus ?? [],
    isLive: query.isSuccess && !query.isPlaceholderData,
  };
}
