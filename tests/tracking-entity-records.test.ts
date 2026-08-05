import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizeTrackingEntityRecordManifest,
  trackingEntityPriorityLabel,
  trackingEntityPriorityStars,
  updateTrackingEntityRecord,
} from "../lib/tracking-entity-records";

test("record normalization rejects malformed entities and clamps priority", () => {
  const manifest = normalizeTrackingEntityRecordManifest({
    schemaVersion: 9,
    generatedAt: "2026-08-05T06:00:00Z",
    records: {
      "company:polymarket": {
        entityType: "company",
        canonicalName: "Polymarket",
        priority: 99,
        reasons: ["融资机会", "unknown"],
        thesis: "  预测市场研究判断  ",
        notes: [],
      },
      invalid: {
        entityType: "company",
        canonicalName: "Invalid",
      },
    },
  });

  assert.deepEqual(Object.keys(manifest.records), ["company:polymarket"]);
  assert.equal(manifest.records["company:polymarket"].priority, 5);
  assert.deepEqual(manifest.records["company:polymarket"].reasons, ["融资机会"]);
  assert.equal(manifest.schemaVersion, 1);
});

test("record updates preserve audit metadata and append analyst notes", () => {
  const first = updateTrackingEntityRecord(
    normalizeTrackingEntityRecordManifest({}),
    {
      entityId: "company:polymarket",
      entityType: "company",
      canonicalName: "Polymarket",
      priority: 5,
      reasons: ["商业模式创新", "监管变化"],
      thesis: "预测市场的核心变量是监管、流动性和分发效率。",
      noteBody: "继续跟踪与 Kalshi 的竞争。",
      updatedAt: "2026-08-05T06:10:00Z",
      updatedBy: "VCIQ",
    },
  );
  const record = first.records["company:polymarket"];
  assert.equal(record.priority, 5);
  assert.equal(record.createdAt, "2026-08-05T06:10:00Z");
  assert.equal(record.notes.length, 1);
  assert.equal(record.notes[0].createdBy, "VCIQ");

  const second = updateTrackingEntityRecord(first, {
    entityId: "company:polymarket",
    entityType: "company",
    canonicalName: "Polymarket",
    priority: 4,
    reasons: ["市场竞争"],
    thesis: "重点观察监管落地和竞争格局。",
    updatedAt: "2026-08-05T07:00:00Z",
    updatedBy: "VCIQ",
  });
  assert.equal(second.records["company:polymarket"].createdAt, record.createdAt);
  assert.equal(second.records["company:polymarket"].notes.length, 1);
  assert.equal(second.records["company:polymarket"].priority, 4);
});

test("identical note submissions at one audit point are deduplicated", () => {
  const input = {
    entityId: "topic:predictionmarket",
    entityType: "topic" as const,
    canonicalName: "预测市场",
    priority: 4,
    reasons: ["个人研究兴趣"],
    thesis: "持续观察。",
    noteBody: "同一条笔记",
    updatedAt: "2026-08-05T08:00:00Z",
    updatedBy: "VCIQ",
  };
  const first = updateTrackingEntityRecord(
    normalizeTrackingEntityRecordManifest({}),
    input,
  );
  const second = updateTrackingEntityRecord(first, input);
  assert.equal(second.records[input.entityId].notes.length, 1);
});

test("priority labels and stars follow the five-level research model", () => {
  assert.equal(trackingEntityPriorityLabel(5), "核心研究");
  assert.equal(trackingEntityPriorityLabel(4), "重点观察");
  assert.equal(trackingEntityPriorityLabel(0), "未设置等级");
  assert.equal(trackingEntityPriorityStars(3), "★★★☆☆");
});

test("invalid entity ids cannot be written", () => {
  assert.throws(
    () =>
      updateTrackingEntityRecord(normalizeTrackingEntityRecordManifest({}), {
        entityId: "bad-id",
        entityType: "company",
        canonicalName: "Bad",
        priority: 1,
        reasons: [],
        thesis: "",
        updatedAt: "2026-08-05T08:00:00Z",
        updatedBy: "VCIQ",
      }),
    /缺少合法/u,
  );
});
