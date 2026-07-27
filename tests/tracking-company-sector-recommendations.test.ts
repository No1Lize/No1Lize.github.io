import assert from "node:assert/strict";
import test from "node:test";

import { recommendTrackingAdditions } from "../lib/tracking-recommendations";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const base = {
  type: "公司动态" as const,
  region: "美国" as const,
  publishedAt: "2099-01-03",
  importance: 82,
  qualityScore: 88,
};

test("known AI companies cannot be recommended to commercial space even when an article is misclassified", () => {
  const articles: LiveIntelligenceEvent[] = [
    {
      ...base,
      id: "misclassified-anthropic-space",
      sourceId: "anthropic-official",
      title: "Anthropic publishes a new model update",
      summary: "Claude model and agent capabilities update.",
      sector: "商业航天",
      company: "Anthropic",
      companySlug: "anthropic",
      source: {
        name: "Anthropic 官方来源",
        url: "https://www.anthropic.com/news/model-update",
        level: "官方披露",
        platform: "官方网站",
      },
    },
  ];

  const result = recommendTrackingAdditions(articles, "商业航天");
  assert.ok(!result.companies.some((item) => item.value === "Anthropic"));
  assert.ok(!result.sources.some((item) => item.label.includes("Anthropic")));
});

test("known commercial-space companies remain eligible in commercial space", () => {
  const articles: LiveIntelligenceEvent[] = [
    {
      ...base,
      id: "spacex-space",
      sourceId: "spacex-official",
      title: "SpaceX announces a Starship flight update",
      summary: "The company published a commercial launch and Starship mission update.",
      sector: "商业航天",
      company: "SpaceX",
      companySlug: "spacex",
      source: {
        name: "SpaceX 官方来源",
        url: "https://www.spacex.com/updates/starship",
        level: "官方披露",
        platform: "官方网站",
      },
    },
  ];

  const result = recommendTrackingAdditions(articles, "商业航天");
  assert.ok(result.companies.some((item) => item.value === "SpaceX"));
});
