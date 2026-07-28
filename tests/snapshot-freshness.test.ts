import assert from "node:assert/strict";
import test from "node:test";
import {
  formatTaipeiDateTime,
  getSnapshotFreshness,
} from "../lib/snapshot-freshness";

const now = new Date("2026-07-27T12:00:00+08:00");

test("formats the last successful publication to Taipei minutes", () => {
  assert.equal(
    formatTaipeiDateTime("2026-07-28T01:15:17Z"),
    "2026-07-28 09:15",
  );
});

test("a completed current-day refresh is not marked stale when latest news is older", () => {
  const result = getSnapshotFreshness({
    isLive: true,
    generatedAt: "2026-07-27T03:30:00Z",
    latestPublishedAt: "2026-07-26",
    qualityPassed: true,
    refreshAudit: {
      pipelineCompleted: true,
      localDate: "2026-07-27",
      completedAt: "2026-07-27T03:42:00Z",
    },
    now,
  });

  assert.equal(result.label, "本轮抓取已完成");
  assert.equal(result.stale, false);
  assert.equal(result.processedAt, "2026-07-27 11:42");
  assert.match(result.description, /2026-07-26/);
});

test("same-day published intelligence keeps the stronger updated label", () => {
  const result = getSnapshotFreshness({
    isLive: true,
    generatedAt: "2026-07-27T03:30:00Z",
    latestPublishedAt: "2026-07-27",
    qualityPassed: true,
    now,
  });

  assert.equal(result.label, "当日情报已更新");
  assert.equal(result.stale, false);
});

test("an older uncompleted snapshot is marked stale", () => {
  const result = getSnapshotFreshness({
    isLive: true,
    generatedAt: "2026-07-26T03:30:00Z",
    latestPublishedAt: "2026-07-26",
    qualityPassed: true,
    now,
  });

  assert.equal(result.label, "内容待刷新");
  assert.equal(result.stale, true);
});

test("quality failure takes precedence over publication dates", () => {
  const result = getSnapshotFreshness({
    isLive: true,
    generatedAt: "2026-07-27T03:30:00Z",
    latestPublishedAt: "2026-07-27",
    qualityPassed: false,
    now,
  });

  assert.equal(result.label, "数据异常");
  assert.equal(result.description, "数据质量门未通过");
  assert.equal(result.stale, true);
});
