import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizeEntityResolutionManifest,
  resolveTrackingEntity,
} from "../lib/entity-resolution";
import {
  applyTrackingCapture,
  normalizeTrackingCaptureInbox,
  type TrackingCaptureSource,
} from "../lib/tracking-capture";
import type { UserTrackingConfig } from "../lib/user-tracking";

const articleSource = {
  title: "20万星里程碑达成！GitHub 技能包走红",
  summary:
    "TypeScript 圈大佬、AI 工程化先锋 Matt Pocock 宣布开源项目在 GitHub 达到 20 万颗星。",
  sourceName: "专业媒体",
  channel: "technology",
  channelLabel: "新兴科技",
  eventType: "公司动态",
  url: "https://example.com/article",
};

test("versioned decisions reclassify known technology names", () => {
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "TypeScript",
    source: articleSource,
  });
  assert.equal(resolution.status, "resolved");
  assert.equal(resolution.entityType, "topic");
  assert.equal(resolution.canonicalName, "TypeScript");
  assert.equal(resolution.source, "human-decision");
  assert.equal(resolution.reclassified, true);
});

test("ambiguous short names are held for review", () => {
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "Matt",
    source: articleSource,
  });
  assert.equal(resolution.status, "review");
  assert.equal(resolution.source, "human-decision");
  assert.equal(resolution.confidence, "low");
});

test("reviewed company decisions remain eligible for company tracking", () => {
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "GitHub",
    source: articleSource,
  });
  assert.equal(resolution.status, "resolved");
  assert.equal(resolution.entityType, "company");
  assert.equal(resolution.targetId, "company:github");
});

test("formal people override an incorrect requested company type", () => {
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "Sam Altman",
    source: {
      title: "Sam Altman discusses OpenAI",
      summary: "OpenAI CEO Sam Altman spoke at the event.",
    },
  });
  assert.equal(resolution.status, "resolved");
  assert.equal(resolution.entityType, "person");
  assert.match(resolution.targetId, /^person:/u);
  assert.equal(resolution.reclassified, true);
});

test("clear local company context admits an unknown company candidate", () => {
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "Polymarket",
    source: {
      title: "预测市场平台 Polymarket 洽谈新一轮融资",
      summary: "Polymarket 与 Kalshi 是预测市场的重要创业公司。",
      eventType: "融资",
    },
  });
  assert.equal(resolution.status, "resolved");
  assert.equal(resolution.entityType, "company");
  assert.equal(resolution.source, "source-context");
});

test("a technology cue prevents direct company publication", () => {
  const manifest = normalizeEntityResolutionManifest({ decisions: {} });
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "Rust",
    manifest,
    source: {
      title: "Rust 编程语言发布新版",
      summary: "这门编程语言改进了工具链。",
    },
  });
  assert.equal(resolution.status, "review");
  assert.equal(resolution.source, "source-context");
});

test("decision aliases reuse the reviewed canonical entity", () => {
  const manifest = normalizeEntityResolutionManifest({
    decisions: {
      "matt pocock": {
        status: "resolved",
        requestedType: "person",
        entityType: "person",
        canonicalName: "Matt Pocock",
        targetId: "person:matt-pocock",
        aliases: ["Matt"],
        confidence: "verified",
        note: "人工确认完整姓名。",
      },
    },
  });
  const resolution = resolveTrackingEntity({
    requestedType: "company",
    name: "Matt",
    manifest,
    source: articleSource,
  });
  assert.equal(resolution.status, "resolved");
  assert.equal(resolution.entityType, "person");
  assert.equal(resolution.canonicalName, "Matt Pocock");
  assert.equal(resolution.source, "human-decision");
});


function captureConfig(): UserTrackingConfig {
  return {
    schemaVersion: 1,
    tracks: [
      {
        slug: "ai",
        name: "AI / AGI",
        enabled: true,
        custom: false,
        keywords: [],
        people: [],
        sampleCompanies: [],
      },
    ],
    listedCompanies: [],
    sources: [],
  };
}

test("capture applies resolved types but queues unresolved company names", () => {
  const source: TrackingCaptureSource = {
    articleId: "article-skills",
    title: articleSource.title,
    url: articleSource.url,
    summary: articleSource.summary,
    sourceName: articleSource.sourceName,
    channel: articleSource.channel,
    channelLabel: articleSource.channelLabel,
    eventType: articleSource.eventType,
  };
  const result = applyTrackingCapture({
    config: captureConfig(),
    inbox: normalizeTrackingCaptureInbox({}),
    entities: [
      { entityType: "company", name: "GitHub" },
      { entityType: "company", name: "TypeScript" },
      { entityType: "company", name: "Matt" },
    ],
    selectedTrackSlugs: ["ai"],
    source,
    capturedAt: "2026-08-06T02:00:00Z",
    capturedBy: "VCIQ",
  });
  assert.deepEqual(result.config.tracks[0].sampleCompanies, ["GitHub"]);
  assert.deepEqual(result.config.tracks[0].keywords, ["TypeScript"]);
  assert.deepEqual(result.config.tracks[0].people, []);
  assert.equal(result.reviewCount, 1);
  assert.equal(result.reclassifiedCount, 2);
  const byRawName = new Map(result.records.map((record) => [record.rawSelection, record]));
  assert.equal(byRawName.get("TypeScript")?.entityType, "topic");
  assert.equal(byRawName.get("TypeScript")?.status, "applied");
  assert.equal(byRawName.get("Matt")?.status, "queued");
  assert.deepEqual(byRawName.get("Matt")?.appliedTo, []);
});
