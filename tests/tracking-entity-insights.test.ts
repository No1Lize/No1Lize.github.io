import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTrackingResearchRelations,
  classifyTrackingResearchTimelineItem,
  trackingResearchBrief,
  trackingResearchSignals,
} from "../lib/tracking-entity-insights";
import type {
  TrackingResearchEntity,
  TrackingResearchTimelineItem,
} from "../lib/tracking-entity-research";

function timeline(
  overrides: Partial<TrackingResearchTimelineItem> = {},
): TrackingResearchTimelineItem {
  return {
    id: "event-1",
    origin: "intelligence",
    title: "Sample 发布新产品",
    summary: "公司宣布新产品和客户计划。",
    url: "https://example.com/story",
    sourceName: "Example",
    eventType: "产品发布",
    channel: "companies",
    channelLabel: "创业案例",
    eventDate: "2026-08-05",
    observedAt: "2026-08-05T02:00:00Z",
    sortAt: "2026-08-05T23:59:59Z",
    capturedBy: "",
    captureIds: [],
    reasons: [],
    note: "",
    ...overrides,
  };
}

function entity(
  overrides: Partial<TrackingResearchEntity> = {},
): TrackingResearchEntity {
  return {
    id: "company:sample",
    entityType: "company",
    slug: "sample",
    name: "Sample",
    aliases: ["Sample"],
    trackSlugs: ["prediction-market"],
    trackNames: ["预测市场"],
    state: "tracked",
    formalHref: "",
    formalLabel: "",
    candidateStatus: "",
    summary: "Sample 是一个追踪中的创业公司。",
    firstTrackedAt: "2026-08-05T02:00:00Z",
    lastActivityAt: "2026-08-05T23:59:59Z",
    captureCount: 1,
    articleCount: 1,
    reasons: ["市场竞争"],
    notes: [],
    priority: 4,
    priorityLabel: "重点观察",
    priorityStars: "★★★★☆",
    researchThesis: "需要持续核对竞争格局和监管边界。",
    analystNotes: [],
    timeline: [timeline()],
    ...overrides,
  };
}

test("timeline classification separates financing and regulation signals", () => {
  assert.equal(
    classifyTrackingResearchTimelineItem(
      timeline({
        title: "Sample 完成新一轮融资",
        summary: "估值和投资方尚待披露。",
        eventType: "融资",
      }),
    ),
    "financing",
  );
  assert.equal(
    classifyTrackingResearchTimelineItem(
      timeline({
        title: "监管机构更新牌照规则",
        summary: "新的合规要求开始生效。",
        eventType: "监管文件",
      }),
    ),
    "regulation",
  );
});

test("signals aggregate counts and keep the latest evidence title", () => {
  const signals = trackingResearchSignals(
    entity({
      timeline: [
        timeline({
          id: "funding-2",
          title: "Sample 新融资",
          eventType: "融资",
          sortAt: "2026-08-06T23:59:59Z",
        }),
        timeline({
          id: "funding-1",
          title: "Sample 早期融资",
          eventType: "融资",
          sortAt: "2026-08-01T23:59:59Z",
        }),
      ],
    }),
  );
  assert.equal(signals[0].category, "financing");
  assert.equal(signals[0].count, 2);
  assert.equal(signals[0].latestTitle, "Sample 新融资");
});

test("automatic brief uses the persisted analyst priority and thesis", () => {
  const brief = trackingResearchBrief(
    entity({
      priority: 5,
      priorityLabel: "核心研究",
      priorityStars: "★★★★★",
      state: "candidate",
      candidateStatus: "pending",
      timeline: [
        timeline({
          title: "Sample 洽谈融资",
          summary: "该公司正在讨论新一轮融资。",
          eventType: "融资",
        }),
      ],
    }),
  );
  assert.equal(brief.priority, 5);
  assert.equal(brief.priorityLabel, "核心研究");
  assert.match(brief.summary, /当前人工研究判断/u);
  assert.ok(brief.watchItems.some((item) => item.includes("融资")));
  assert.ok(brief.openQuestions.some((item) => item.includes("官方来源")));
  assert.match(brief.methodology, /可追溯/u);
});

test("analyst notes are excluded from evidence signals and latest evidence", () => {
  const item = entity({
    timeline: [
      timeline({
        id: "note-new",
        origin: "analyst-note",
        title: "Sample 研究笔记",
        summary: "内部假设认为公司可能面临监管风险。",
        url: "",
        sourceName: "VCIQ 研究记录",
        eventType: "研究笔记",
        sortAt: "2026-08-07T12:00:00Z",
      }),
      timeline({
        id: "funding-old",
        title: "Sample 完成融资",
        summary: "公司公布新一轮融资。",
        eventType: "融资",
        sortAt: "2026-08-06T23:59:59Z",
      }),
    ],
  });
  const signals = trackingResearchSignals(item);
  const brief = trackingResearchBrief(item);
  assert.equal(signals.length, 1);
  assert.equal(signals[0].category, "financing");
  assert.doesNotMatch(brief.summary, /研究笔记/u);
  assert.match(brief.summary, /Sample 完成融资/u);
  assert.match(brief.methodology, /人工笔记不参与事实信号/u);
});

test("shared original evidence creates a competition relation", () => {
  const sourceUrl = "https://finance.example/prediction-market";
  const polymarket = entity({
    id: "company:polymarket",
    slug: "polymarket",
    name: "Polymarket",
    aliases: ["Polymarket"],
    timeline: [
      timeline({
        id: "poly-1",
        origin: "manual-capture",
        title: "Polymarket 融资，竞争对手 Kalshi 扩张",
        summary: "两家预测市场公司正在争夺美国市场。",
        url: sourceUrl,
        eventType: "融资",
        captureIds: ["capture-poly"],
      }),
    ],
  });
  const kalshi = entity({
    id: "company:kalshi",
    slug: "kalshi",
    name: "Kalshi",
    aliases: ["Kalshi"],
    timeline: [
      timeline({
        id: "kalshi-1",
        origin: "manual-capture",
        title: "Polymarket 融资，竞争对手 Kalshi 扩张",
        summary: "两家预测市场公司正在争夺美国市场。",
        url: sourceUrl,
        eventType: "竞争动态",
        captureIds: ["capture-kalshi"],
      }),
    ],
  });

  const relations = buildTrackingResearchRelations(
    polymarket,
    [polymarket, kalshi],
  );
  assert.equal(relations.length, 1);
  assert.equal(relations[0].entity.id, "company:kalshi");
  assert.equal(relations[0].kind, "competition");
  assert.equal(relations[0].confidence, "high");
  assert.equal(relations[0].evidenceCount, 1);
  assert.equal(relations[0].evidence[0].url, sourceUrl);
});

test("same track without shared evidence remains contextual", () => {
  const left = entity({
    id: "company:left",
    slug: "left",
    name: "Left",
    timeline: [timeline({ url: "https://example.com/left" })],
  });
  const right = entity({
    id: "company:right",
    slug: "right",
    name: "Right",
    timeline: [timeline({ url: "https://example.com/right" })],
  });
  const relations = buildTrackingResearchRelations(left, [left, right]);
  assert.equal(relations.length, 1);
  assert.equal(relations[0].kind, "shared-track");
  assert.equal(relations[0].confidence, "contextual");
  assert.equal(relations[0].evidenceCount, 0);
});

test("analyst notes without public URLs never create factual relations", () => {
  const left = entity({
    id: "company:left",
    slug: "left",
    name: "Left",
    trackSlugs: [],
    trackNames: [],
    timeline: [
      timeline({
        id: "note-left",
        origin: "analyst-note",
        title: "Left 研究笔记",
        summary: "可能与 Right 存在竞争关系，尚未核验。",
        url: "",
        eventType: "研究笔记",
      }),
    ],
  });
  const right = entity({
    id: "company:right",
    slug: "right",
    name: "Right",
    trackSlugs: [],
    trackNames: [],
    timeline: [
      timeline({
        id: "note-right",
        origin: "analyst-note",
        title: "Right 研究笔记",
        summary: "内部假设。",
        url: "",
        eventType: "研究笔记",
      }),
    ],
  });
  assert.deepEqual(buildTrackingResearchRelations(left, [left, right]), []);
});
