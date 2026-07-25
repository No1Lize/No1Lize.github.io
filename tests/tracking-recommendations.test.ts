import assert from "node:assert/strict";
import test from "node:test";

import { recommendTrackingAdditions } from "../lib/tracking-recommendations";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const articles: LiveIntelligenceEvent[] = [
  {
    id: "openai-mcp-1",
    sourceId: "openai",
    title: "OpenAI expands MCP support for AI Agent workflows",
    summary: "The release connects MCP tools with long-context agent systems.",
    type: "产品发布",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    companySlug: "openai",
    publishedAt: "2099-01-03",
    importance: 88,
    qualityScore: 92,
    source: {
      name: "OpenAI",
      url: "https://openai.com/news/mcp-agent-workflows",
      level: "官方披露",
      platform: "官方网站",
    },
  },
  {
    id: "openai-mcp-2",
    sourceId: "openai",
    title: "MCP tools enter OpenAI developer platform",
    summary: "OpenAI publishes another MCP integration update for developers.",
    type: "产品发布",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    companySlug: "openai",
    publishedAt: "2099-01-02",
    importance: 82,
    qualityScore: 90,
    source: {
      name: "OpenAI",
      url: "https://openai.com/news/mcp-developer-platform",
      level: "官方披露",
      platform: "官方网站",
    },
  },
  {
    id: "sam-x-1",
    sourceId: "user-x-sam-altman",
    title: "Sam Altman：MCP will improve agent interoperability",
    summary: "A public post discussing MCP and AI Agent interoperability.",
    type: "人物观点",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    publishedAt: "2099-01-01",
    importance: 70,
    qualityScore: 72,
    source: {
      name: "Sam Altman on X",
      url: "https://x.com/sama/status/123456789",
      level: "原始材料",
      platform: "X",
    },
  },
];

test("tracking recommendations derive useful additions from sector intelligence", () => {
  const result = recommendTrackingAdditions(articles, "AI / AGI", {
    keywords: ["AI Agent"],
  });

  assert.ok(result.keywords.some((item) => item.value === "MCP"));
  assert.ok(!result.keywords.some((item) => item.value === "AI Agent"));
  assert.ok(result.people.some((item) => item.value.includes("@sama")));
  assert.ok(result.companies.some((item) => item.value === "OpenAI"));
  assert.ok(result.sources.some((item) => new URL(item.source.url).hostname === "openai.com"));
  assert.ok(!result.sources.some((item) => new URL(item.source.url).hostname === "x.com"));
});

test("existing source hosts are removed from recommendations", () => {
  const result = recommendTrackingAdditions(articles, "AI / AGI", {
    sources: ["https://openai.com/news/"],
  });

  assert.equal(result.sources.length, 0);
});
