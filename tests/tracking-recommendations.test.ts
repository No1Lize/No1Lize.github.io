import assert from "node:assert/strict";
import test from "node:test";

import { isAllowedDisplayedKeywordRecommendation } from "../lib/tracking-recommendation-policy";
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
  {
    id: "grpo-paper-1",
    sourceId: "research-lab-a",
    title: "GRPO training algorithm improves reasoning efficiency",
    summary: "The GRPO method changes reinforcement-learning optimization for reasoning models.",
    type: "论文",
    region: "全球",
    sector: "AI / AGI",
    company: "AI 研究",
    publishedAt: "2099-01-05",
    importance: 79,
    qualityScore: 84,
    source: {
      name: "Research Lab A",
      url: "https://lab-a.example.org/research/grpo",
      level: "原始材料",
      platform: "官方网站",
    },
  },
  {
    id: "grpo-paper-2",
    sourceId: "research-media-b",
    title: "GRPO benchmark compares reinforcement-learning algorithms",
    summary: "Independent results evaluate GRPO training across reasoning model benchmarks.",
    type: "论文",
    region: "全球",
    sector: "AI / AGI",
    company: "AI 研究",
    publishedAt: "2099-01-06",
    importance: 75,
    qualityScore: 78,
    source: {
      name: "Research Media B",
      url: "https://research-b.example.com/analysis/grpo",
      level: "媒体报道",
      platform: "网站",
    },
  },
  {
    id: "noise-1",
    sourceId: "noise-media",
    title: "US CEO discusses UK STEM AI AGI LLM RT K3 outlook",
    summary: "A generic roundup with country codes, job titles and isolated abbreviations.",
    type: "公司动态",
    region: "全球",
    sector: "AI / AGI",
    company: "科技产业",
    publishedAt: "2099-01-04",
    importance: 40,
    qualityScore: 45,
    authors: ["CEO", "US", "AI"],
    source: {
      name: "Noise Media",
      url: "https://noise.example.com/roundup",
      level: "媒体报道",
      platform: "网站",
    },
  },
];

const forbiddenNoise = ["US", "UK", "AI", "AGI", "LLM", "STEM", "RT", "K3", "CEO"];

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

test("unseen technical entities emerge from independent multi-source evidence", () => {
  const result = recommendTrackingAdditions(articles, "AI / AGI");
  const grpo = result.keywords.find((item) => item.value === "GRPO");

  assert.ok(grpo, "GRPO should be dynamically discovered without seed configuration");
  assert.match(grpo.reason, /动态发现/);
});

test("country codes, roles and isolated acronyms are never recommended as entities", () => {
  const result = recommendTrackingAdditions(articles, "AI / AGI");
  const keywordValues = new Set(result.keywords.map((item) => item.value));
  const peopleValues = new Set(result.people.map((item) => item.value));

  for (const noise of forbiddenNoise) {
    assert.ok(!keywordValues.has(noise), `${noise} should not be a keyword recommendation`);
    assert.ok(!peopleValues.has(noise), `${noise} should not be a person recommendation`);
  }
});

test("common technical nouns are hidden while named entities remain visible", () => {
  for (const value of ["Inference", "Rocket", "Agent", "Training", "Model"]) {
    assert.equal(
      isAllowedDisplayedKeywordRecommendation({
        value,
        label: value,
        reason: "动态发现：4 条情报、2 个独立来源",
        score: 80,
      }),
      false,
      `${value} is a generic concept, not a named entity`,
    );
  }

  for (const value of ["GRPO", "GPT-5", "DeepSeek-R1", "Llama Model"]) {
    assert.equal(
      isAllowedDisplayedKeywordRecommendation({
        value,
        label: value,
        reason: "动态发现：2 条情报、2 个独立来源",
        score: 90,
      }),
      true,
      `${value} should remain as a named technical entity`,
    );
  }
});

test("existing source hosts are removed from recommendations", () => {
  const result = recommendTrackingAdditions(articles, "AI / AGI", {
    sources: ["https://openai.com/news/"],
  });

  assert.ok(!result.sources.some((item) => new URL(item.source.url).hostname === "openai.com"));
});
