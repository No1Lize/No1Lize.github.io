import assert from "node:assert/strict";
import test from "node:test";

import type { IntelligenceEvent } from "../lib/intelligence-data";
import {
  generateSectorDefinition,
  resolveSectorDefinition,
  sectorCompleteness,
} from "../lib/sector-profile-generator";
import type { SectorDefinition } from "../lib/sector-definitions";
import type { TrackingTrack } from "../lib/user-tracking";

function track(name: string, keywords: string[] = []): TrackingTrack {
  return {
    slug: `track-${name.length}`,
    name,
    enabled: true,
    custom: true,
    keywords,
    people: [],
    sampleCompanies: [],
  };
}

function event(
  sector: string,
  overrides: Partial<IntelligenceEvent> = {},
): IntelligenceEvent {
  return {
    id: `${sector}-${overrides.type ?? "技术突破"}-${overrides.region ?? "中国"}`,
    title: `${sector}公开进展`,
    summary: `${sector}完成新的工程验证。`,
    type: "技术突破",
    region: "中国",
    sector,
    company: "样本公司",
    publishedAt: "2026-07-25",
    importance: 80,
    source: {
      name: "公开来源",
      url: `https://example.com/${encodeURIComponent(sector)}`,
      level: "媒体报道",
    },
    ...overrides,
  };
}

test("arbitrary empty tracks receive a complete generated profile", () => {
  for (const name of ["可控核聚变", "脑机接口", "低空经济", "合成生物"]) {
    const profile = generateSectorDefinition(track(name), []);
    assert.equal(profile.name, name);
    assert.ok(profile.definition.includes(name));
    assert.ok(profile.subsectors.length >= 4);
    assert.equal(profile.chain.length, 4);
    assert.ok(profile.chain.every((node) => node.title && node.detail));
    assert.ok(profile.researchFocus.length >= 2);
    assert.ok(profile.risks.length >= 4);
    assert.ok(profile.chinaLens.includes(name));
    assert.ok(profile.usLens.includes(name));
  }
});

test("generated profiles incorporate configured terms and observed evidence", () => {
  const configured = track("脑机接口", ["侵入式脑机接口", "神经信号解码"]);
  configured.people = ["研究负责人"];
  configured.sampleCompanies = ["Neuralink"];
  const events = [
    event("脑机接口", { company: "Neuralink", region: "美国", type: "产品发布" }),
    event("脑机接口", { company: "脑虎科技", region: "中国", type: "融资" }),
    event("脑机接口", { company: "脑虎科技", region: "中国", type: "政策" }),
  ];

  const profile = generateSectorDefinition(configured, events);
  assert.ok(profile.definition.includes("侵入式脑机接口"));
  assert.ok(profile.definition.includes("Neuralink"));
  assert.ok(profile.subsectors.includes("融资与产业化"));
  assert.ok(profile.subsectors.includes("政策与监管"));
  assert.ok(profile.chinaLens.includes("2 项"));
  assert.ok(profile.usLens.includes("1 项"));
  assert.ok(profile.researchFocus.some((item) => item.includes("资本开支")));
  assert.ok(profile.researchFocus.some((item) => item.includes("关键人物")));
  assert.ok(sectorCompleteness(configured, events) > 40);
});

test("curated definitions enhance rather than gate arbitrary track generation", () => {
  const configured = track("测试赛道", ["新增关键词"]);
  const curated: SectorDefinition = {
    slug: "curated-old-slug",
    name: "旧名称",
    definition: "人工增强定义。",
    subsectors: ["人工子方向"],
    chain: [{ title: "人工产业链", detail: "人工说明" }],
    chinaLens: "人工中国视角。",
    usLens: "人工美国视角。",
    researchFocus: ["人工研究变量"],
    risks: ["人工风险"],
  };

  const resolved = resolveSectorDefinition(configured, [], curated);
  assert.equal(resolved.slug, configured.slug);
  assert.equal(resolved.name, configured.name);
  assert.equal(resolved.definition, curated.definition);
  assert.ok(resolved.subsectors.includes("新增关键词"));
  assert.ok(resolved.subsectors.includes("人工子方向"));
  assert.equal(resolved.chain[0].title, "人工产业链");
  assert.ok(resolved.risks.includes("人工风险"));
});
