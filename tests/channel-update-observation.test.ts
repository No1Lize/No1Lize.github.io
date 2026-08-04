import assert from "node:assert/strict";
import test from "node:test";

import {
  countChannelUpdatesFirstSeenForSnapshotDay,
  countChannelUpdatesForSnapshotDay,
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
