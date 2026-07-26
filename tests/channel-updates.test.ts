import assert from "node:assert/strict";
import test from "node:test";

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
