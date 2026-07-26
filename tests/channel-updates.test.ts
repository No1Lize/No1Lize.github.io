import assert from "node:assert/strict";
import test from "node:test";

import {
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateKeywords,
  filterAndSortChannelUpdates,
} from "../lib/channel-update-filter";
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
    assert.ok(items.every((item) => /^https?:\/\//u.test(item.href)));
    assert.ok(items.every((item) => item.title && item.source && item.date));
    assert.ok(items.every((item) => item.keywords.length > 0));
    for (let index = 1; index < items.length; index += 1) {
      assert.ok(
        items[index - 1].sortAt.localeCompare(items[index].sortAt) >= 0,
        `${channel} is not sorted newest-first at index ${index}`,
      );
    }
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

test("keyword options classify every channel and report accurate counts", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const options = collectChannelUpdateKeywords(items);
    assert.ok(options.length > 0, `${channel} has no keyword options`);

    for (const option of options) {
      const actual = items.filter((item) => item.keywords.includes(option.keyword)).length;
      assert.equal(option.count, actual, `${channel} keyword count is wrong for ${option.keyword}`);
    }
  }
});

test("keyword-filtered updates remain time ordered", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const keyword = collectChannelUpdateKeywords(items)[0]?.keyword;
    assert.ok(keyword, `${channel} has no keyword to test`);

    const newest = filterAndSortChannelUpdates({ items, keyword, sortOrder: "newest" });
    assert.ok(newest.length > 0);
    assert.ok(newest.every((item) => item.keywords.includes(keyword)));
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
