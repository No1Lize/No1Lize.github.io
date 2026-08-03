import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizeChannelUpdateDate,
  UNDATED_CHANNEL_UPDATE_SORT_AT,
} from "../lib/channel-update-date";
import {
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateKeywords,
  countChannelUpdatesForSnapshotDay,
  filterAndSortChannelUpdates,
} from "../lib/channel-update-filter";
import { HOMEPAGE_CHANNEL_UPDATE_LIMIT } from "../lib/homepage-channel-update-config";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "../lib/channel-updates";

const channels: ChannelUpdateKey[] = [
  "technology",
  "companies",
  "institutions",
  "reports",
  "people",
];

const snapshotTime = "2026-07-26T02:10:42.000Z";

test("homepage channel update directory displays up to 200 deduplicated items", () => {
  assert.equal(HOMEPAGE_CHANNEL_UPDATE_LIMIT, 200);
});

test("channel snapshot counts exact and relative updates on the generated day", () => {
      const sample = getChannelUpdateDirectory("technology").items[0];
      assert.ok(sample);
      const items = [
        { ...sample, id: "today-exact", sortAt: "2026-08-03T10:00:00.000Z", datePrecision: "exact" as const },
        { ...sample, id: "today-relative", sortAt: "2026-08-03T00:00:00.000Z", datePrecision: "approximate" as const },
        { ...sample, id: "yesterday", sortAt: "2026-08-02T23:59:59.000Z", datePrecision: "exact" as const },
        { ...sample, id: "undated", sortAt: UNDATED_CHANNEL_UPDATE_SORT_AT, datePrecision: "undated" as const },
      ];

      assert.equal(
        countChannelUpdatesForSnapshotDay(items, "2026-08-03T12:17:00.000Z"),
        2,
      );
      assert.equal(countChannelUpdatesForSnapshotDay(items, "等待更新"), 0);
    });

    test("normalizes exact, relative and undated source labels", () => {
  const exact = normalizeChannelUpdateDate("2020-05-29", snapshotTime);
  assert.equal(exact.displayDate, "2020-05-29");
  assert.equal(exact.precision, "exact");

  const years = normalizeChannelUpdateDate("4年前", snapshotTime);
  assert.equal(years.displayDate, "约 2022-07-26");
  assert.equal(years.precision, "approximate");

  const months = normalizeChannelUpdateDate("8个月前", snapshotTime);
  assert.equal(months.displayDate, "约 2025-11-26");
  assert.ok(months.sortAt > years.sortAt);

  const ongoing = normalizeChannelUpdateDate("持续更新", snapshotTime);
  assert.equal(ongoing.displayDate, "持续更新");
  assert.equal(ongoing.precision, "undated");
  assert.equal(ongoing.sortAt, UNDATED_CHANNEL_UPDATE_SORT_AT);
});

test("mixed person time labels sort by their normalized calendar dates", () => {
  const rows = ["4年前", "8个月前", "7年前", "6年前", "2020-05-29"].map(
    (label) => ({ label, ...normalizeChannelUpdateDate(label, snapshotTime) }),
  );
  rows.sort((left, right) => right.sortAt.localeCompare(left.sortAt));
  assert.deepEqual(
    rows.map((row) => row.label),
    ["8个月前", "4年前", "6年前", "2020-05-29", "7年前"],
  );
});

test("all requested channels expose a non-empty update directory", () => {
  for (const channel of channels) {
    const directory = getChannelUpdateDirectory(channel);
    assert.ok(directory.title.length > 0, `${channel} is missing a title`);
    assert.ok(directory.generatedAt.length >= 10, `${channel} is missing snapshot time`);
    assert.ok(directory.items.length > 0, `${channel} has no update items`);
  }
});

test("channel updates are newest-first and link to original public sources", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    // Crawled records link to their original public source; manually imported
    // documents link to the in-site reader page.
    assert.ok(
      items.every((item) =>
        /^https?:\/\//u.test(item.href) || item.href.startsWith("/documents/"),
      ),
    );
    assert.ok(items.every((item) => item.title && item.source && item.date));
    assert.ok(
      items.every((item) =>
        item.datePrecision === "undated"
          ? item.sortAt === UNDATED_CHANNEL_UPDATE_SORT_AT
          : /^\d{4}-\d{2}-\d{2}T/u.test(item.sortAt),
      ),
    );
    for (let index = 1; index < items.length; index += 1) {
      assert.ok(
        items[index - 1].sortAt.localeCompare(items[index].sortAt) >= 0,
        `${channel} is not sorted newest-first at index ${index}`,
      );
    }
  }
});

test("person dates use one visible calendar format without treating ongoing pages as new", () => {
  const items = getChannelUpdateDirectory("people").items;
  for (const item of items) {
    if (item.datePrecision === "exact") {
      assert.match(item.date, /^\d{4}-\d{2}-\d{2}$/u);
    } else if (item.datePrecision === "approximate") {
      assert.match(item.date, /^约 \d{4}-\d{2}-\d{2}$/u);
      assert.notEqual(item.date, item.dateOriginal);
    } else {
      assert.ok(item.date === "持续更新" || item.date === "日期未标明");
      assert.equal(item.sortAt, UNDATED_CHANNEL_UPDATE_SORT_AT);
    }
  }

  const relativeSortDates = new Map(
    items
      .filter((item) => item.datePrecision === "approximate")
      .map((item) => [item.dateOriginal, item.sortAt]),
  );
  if (relativeSortDates.has("8个月前") && relativeSortDates.has("4年前")) {
    assert.ok(relativeSortDates.get("8个月前")! > relativeSortDates.get("4年前")!);
  }
});

test("channel directories deduplicate repeated original links", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const keys = items.map(
      (item) => `${item.href.toLocaleLowerCase("en-US")}|${item.title.toLocaleLowerCase("zh-CN")}`,
    );
    assert.equal(new Set(keys).size, keys.length, `${channel} contains duplicate entries`);
  }
});

test("filter options are exactly the visible green event labels", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    assert.ok(items.every((item) => item.keywords.length === 1));
    assert.ok(items.every((item) => item.keywords[0] === item.label));

    const optionLabels = collectChannelUpdateKeywords(items).map((option) => option.keyword);
    const visibleLabels = [...new Set(items.map((item) => item.label))];
    assert.deepEqual(
      [...optionLabels].sort((left, right) => left.localeCompare(right, "zh-CN")),
      [...visibleLabels].sort((left, right) => left.localeCompare(right, "zh-CN")),
      `${channel} exposes filters that are not visible event labels`,
    );
  }
});

test("event label options classify every channel and report accurate counts", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const options = collectChannelUpdateKeywords(items);
    assert.ok(options.length > 0, `${channel} has no event label options`);

    for (const option of options) {
      const actual = items.filter((item) => item.label === option.keyword).length;
      assert.equal(option.count, actual, `${channel} event count is wrong for ${option.keyword}`);
    }
  }
});

test("event-filtered updates remain time ordered", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const keyword = collectChannelUpdateKeywords(items)[0]?.keyword;
    assert.ok(keyword, `${channel} has no event label to test`);

    const newest = filterAndSortChannelUpdates({ items, keyword, sortOrder: "newest" });
    assert.ok(newest.length > 0);
    assert.ok(newest.every((item) => item.label === keyword));
    for (let index = 1; index < newest.length; index += 1) {
      assert.ok(newest[index - 1].sortAt.localeCompare(newest[index].sortAt) >= 0);
    }

    const oldest = filterAndSortChannelUpdates({ items, keyword, sortOrder: "oldest" });
    for (let index = 1; index < oldest.length; index += 1) {
      assert.ok(oldest[index - 1].sortAt.localeCompare(oldest[index].sortAt) <= 0);
    }

    const all = filterAndSortChannelUpdates({
      items,
      keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
      sortOrder: "newest",
    });
    assert.equal(all.length, items.length);
  }
});
