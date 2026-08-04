import assert from "node:assert/strict";
import test from "node:test";

import {
  ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateClassifications,
  countChannelUpdatesFirstSeenForSnapshotDay,
  countChannelUpdatesForSnapshotDay,
  filterAndSortChannelUpdates,
} from "../lib/channel-update-filter";
import type { ChannelUpdateItem } from "../lib/channel-updates";

function item(
  id: string,
  eventDate: string,
  firstSeenAt?: string,
  firstSeenEstimated?: boolean,
): ChannelUpdateItem {
  return {
    id,
    title: id,
    summary: id,
    href: `https://example.com/${id}`,
    source: "example",
    label: "融资",
    context: "example",
    date: eventDate,
    dateOriginal: eventDate,
    datePrecision: "exact",
    sortAt: `${eventDate}T00:00:00.000Z`,
    keywords: ["融资"],
    firstSeenAt,
    firstSeenEstimated,
  };
}

test("event-day count remains independent from ingestion day", () => {
  const items = [
    item("old-event-new-ingestion", "2026-08-01", "2026-08-04T01:00:00Z", false),
    item("new-event-old-ingestion", "2026-08-04", "2026-08-03T01:00:00Z", false),
  ];

  assert.equal(countChannelUpdatesForSnapshotDay(items, "2026-08-04T06:30:00Z"), 1);
  assert.equal(
    countChannelUpdatesFirstSeenForSnapshotDay(items, "2026-08-04T06:30:00Z"),
    1,
  );
});

test("legacy estimated first-seen values are never counted as new ingestion", () => {
  const items = [
    item("legacy", "2026-08-04", "2026-08-04T06:30:00Z", true),
    item("exact", "2026-08-03", "2026-08-04T06:31:00Z", false),
  ];

  assert.equal(
    countChannelUpdatesFirstSeenForSnapshotDay(items, "2026-08-04T07:00:00Z"),
    1,
  );
});

test("missing and invalid snapshot dates return zero", () => {
  const items = [item("sample", "2026-08-04", "2026-08-04T01:00:00Z", false)];
  assert.equal(countChannelUpdatesFirstSeenForSnapshotDay(items, ""), 0);
  assert.equal(countChannelUpdatesForSnapshotDay(items, "not-a-date"), 0);
});

test("source and channel classifications remain independent from event labels", () => {
  const official = {
    ...item("official", "2026-08-04"),
    classifications: ["机构动态", "B级来源"],
  };
  const media = {
    ...item("media", "2026-08-03"),
    classifications: ["资本事件", "C级来源"],
  };
  const items = [official, media];

  assert.ok(items.every((entry) => entry.keywords.length === 1));
  assert.deepEqual(
    collectChannelUpdateClassifications(items).map((option) => option.keyword),
    ["B级来源", "C级来源", "机构动态", "资本事件"],
  );

  const filtered = filterAndSortChannelUpdates({
    items,
    keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
    classification: "B级来源",
    sortOrder: "newest",
  });
  assert.deepEqual(filtered.map((entry) => entry.id), ["official"]);

  const all = filterAndSortChannelUpdates({
    items,
    keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
    classification: ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
    sortOrder: "newest",
  });
  assert.equal(all.length, 2);
});
