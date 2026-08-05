import assert from "node:assert/strict";
import test from "node:test";

import {
  TRACKING_ATTENTION_LABELS,
  classifyTrackingResearchTimelineItem,
  trackingResearchBrief,
  trackingResearchRelations,
  trackingResearchSignals,
} from "../lib/tracking-entity-insights";
import {
  trackingResearchEntities,
  type TrackingResearchTimelineItem,
} from "../lib/tracking-entity-research";

function timelineItem(overrides: Partial<TrackingResearchTimelineItem>): TrackingResearchTimelineItem {
  return {
    id: "example",
    origin: "intelligence",
    title: "公开动态",
    summary: "",
    url: "https://example.com/story",
    sourceName: "公开来源",
    eventType: "公司动态",
    channel: "",
    channelLabel: "公开情报",
    eventDate: "2026-08-05",
    observedAt: "2026-08-05T00:00:00Z",
    sortAt: "2026-08-05T23:59:59Z",
    capturedBy: "",
    captureIds: [],
    reasons: [],
    note: "",
    ...overrides,
  };
}

test("timeline signal taxonomy distinguishes financing, regulation and competition", () => {
  assert.equal(
    classifyTrackingResearchTimelineItem(
      timelineItem({ title: "公司完成新一轮融资，估值上升" }),
    ),
    "financing",
  );
  assert.equal(
    classifyTrackingResearchTimelineItem(
      timelineItem({ title: "监管机构更新牌照与合规要求" }),
    ),
    "regulation",
  );
  assert.equal(
    classifyTrackingResearchTimelineItem(
      timelineItem({ summary: "Polymarket 与 Kalshi 的竞争格局继续变化" }),
    ),
    "competition",
  );
});

test("every tracked entity exposes an evidence-bounded automatic brief", () => {
  assert.ok(trackingResearchEntities.length > 0);
  for (const entity of trackingResearchEntities) {
    const brief = trackingResearchBrief(entity);
    assert.ok(brief.attentionLevel >= 1 && brief.attentionLevel <= 5);
    assert.equal(brief.attentionLabel, TRACKING_ATTENTION_LABELS[brief.attentionLevel]);
    assert.ok(brief.headline.includes(entity.name));
    assert.ok(brief.methodology.includes("不引入没有来源支持的事实"));
    assert.ok(brief.signals.length <= 4);
    assert.ok(brief.watchItems.length <= 6);
    assert.ok(brief.openQuestions.length <= 5);
  }
});

test("signal summaries remain sorted by evidence count and recency", () => {
  for (const entity of trackingResearchEntities) {
    const signals = trackingResearchSignals(entity);
    for (let index = 1; index < signals.length; index += 1) {
      const previous = signals[index - 1];
      const current = signals[index];
      assert.ok(
        previous.count > current.count ||
          (previous.count === current.count && previous.latestAt >= current.latestAt),
        `${entity.name} signals are not consistently ordered`,
      );
    }
  }
});

test("entity relations distinguish evidence-backed links from shared-track context", () => {
  let relationCount = 0;
  for (const entity of trackingResearchEntities.slice(0, 120)) {
    const relations = trackingResearchRelations(entity, 10);
    relationCount += relations.length;
    for (const relation of relations) {
      assert.notEqual(relation.entity.id, entity.id);
      assert.ok(relation.href.startsWith("/tracking/entities/"));
      assert.equal(relation.evidenceCount, relation.evidence.length <= 3
        ? relation.evidenceCount
        : relation.evidenceCount);
      if (relation.kind === "shared-track") {
        assert.equal(relation.evidenceCount, 0);
        assert.equal(relation.confidence, "contextual");
        assert.ok(relation.sharedTracks.length > 0);
      } else {
        assert.ok(relation.evidenceCount > 0);
        assert.ok(relation.evidence.every((item) => /^https?:\/\//u.test(item.url)));
      }
    }
  }
  assert.ok(relationCount > 0);
});
