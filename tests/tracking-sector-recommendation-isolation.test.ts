import assert from "node:assert/strict";
import test from "node:test";

import { recommendTrackingAdditions } from "../lib/tracking-recommendations";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const renewableArticles: LiveIntelligenceEvent[] = [
  {
    id: "energy-rag-1",
    sourceId: "energy-official-a",
    title: "固态电池研发平台使用 RAG 检索实验记录",
    summary: "RAG 只是研发知识管理工具，核心进展是固态电池材料与储能性能。",
    type: "技术突破",
    region: "中国",
    sector: "新能源",
    company: "新能源实验室甲",
    publishedAt: "2099-01-03",
    importance: 86,
    qualityScore: 91,
    source: {
      name: "新能源实验室甲",
      url: "https://energy-a.example.com/solid-state-rag",
      level: "官方披露",
      platform: "官方网站",
    },
  },
  {
    id: "energy-rag-2",
    sourceId: "energy-media-b",
    title: "RAG 辅助固态电池研发资料检索",
    summary: "报道重点仍是固态电池与储能路线，RAG 仅为通用软件工具。",
    type: "公司动态",
    region: "全球",
    sector: "新能源",
    company: "新能源实验室乙",
    publishedAt: "2099-01-02",
    importance: 78,
    qualityScore: 82,
    source: {
      name: "Energy Media B",
      url: "https://energy-b.example.com/battery-rag",
      level: "媒体报道",
      platform: "网站",
    },
  },
];

const aiArticles: LiveIntelligenceEvent[] = [
  {
    id: "ai-rag-1",
    sourceId: "ai-official-a",
    title: "RAG architecture improves enterprise AI retrieval",
    summary: "The RAG system combines retrieval and generation for AI applications.",
    type: "产品发布",
    region: "美国",
    sector: "AI / AGI",
    company: "AI Platform A",
    publishedAt: "2099-01-03",
    importance: 88,
    qualityScore: 92,
    source: {
      name: "AI Platform A",
      url: "https://ai-a.example.com/rag",
      level: "官方披露",
      platform: "官方网站",
    },
  },
];

test("known AI entities do not leak into renewable-energy recommendations", () => {
  const result = recommendTrackingAdditions(renewableArticles, "新能源");
  const values = new Set(result.keywords.map((item) => item.value));

  assert.ok(!values.has("RAG"));
  assert.ok(values.has("固态电池"));
});

test("sector-owned AI entities remain available in the AI track", () => {
  const result = recommendTrackingAdditions(aiArticles, "AI / AGI");
  assert.ok(result.keywords.some((item) => item.value === "RAG"));
});
