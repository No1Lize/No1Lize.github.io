import assert from "node:assert/strict";
import test from "node:test";

import { ipoCompanies } from "../lib/catalog-data";
import { recommendListedCompanies } from "../lib/tracking-listed-recommendations";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const articles: LiveIntelligenceEvent[] = [
  {
    id: "ionq-1",
    sourceId: "ionq-official",
    title: "IonQ announces a new quantum computing system",
    summary: "IonQ published a technical and commercial update.",
    type: "产品发布",
    region: "美国",
    sector: "量子计算",
    company: "IonQ",
    companySlug: "ionq",
    publishedAt: "2099-01-03",
    importance: 90,
    qualityScore: 94,
    source: {
      name: "IonQ",
      url: "https://ionq.com/news/update",
      level: "官方披露",
      platform: "官方网站",
    },
  },
  {
    id: "ionq-2",
    sourceId: "quantum-media",
    title: "IonQ expands its quantum computing roadmap",
    summary: "An independent report covers IonQ's latest roadmap.",
    type: "公司动态",
    region: "美国",
    sector: "量子计算",
    company: "IonQ",
    companySlug: "ionq",
    publishedAt: "2099-01-02",
    importance: 78,
    qualityScore: 82,
    source: {
      name: "Quantum Media",
      url: "https://quantum.example.com/ionq-roadmap",
      level: "媒体报道",
      platform: "网站",
    },
  },
];

test("listed recommendations prioritize active companies in the selected sector", () => {
  const result = recommendListedCompanies(articles, "量子计算", ipoCompanies, []);

  assert.equal(result[0]?.company.slug, "ionq");
  assert.match(result[0]?.reason ?? "", /2 条相关情报/);
  assert.ok(result.every((item) => item.company.sector === "量子计算"));
});

test("already followed market and ticker pairs are removed", () => {
  const result = recommendListedCompanies(articles, "量子计算", ipoCompanies, [
    {
      id: "catalog-ionq",
      name: "IonQ",
      ticker: "IONQ",
      market: "美股",
      sector: "量子计算",
      enabled: true,
      custom: false,
      catalogSlug: "ionq",
    },
  ]);

  assert.ok(!result.some((item) => item.company.ticker === "IONQ"));
  assert.ok(result.some((item) => item.company.ticker === "RGTI"));
});
