import assert from "node:assert/strict";
import test from "node:test";

import {
  FAVORITES_STORAGE_KEY,
  FAVORITES_SCHEMA_VERSION,
  normalizeFavorite,
  parseFavoriteItems,
  readFavoriteItems,
  toggleFavorite,
} from "../lib/favorites";

test("favorite payload normalization keeps safe structured recommendation signals", () => {
  const favorite = normalizeFavorite({
    id: "company:openai",
    href: "/companies/openai",
    title: " OpenAI ",
    summary: "  前沿模型与智能体平台。 ",
    channel: "companies",
    channelLabel: "创业案例",
    keywords: ["智能体", " 智能体 ", "推理"],
    sectors: ["AI / AGI"],
    sources: [
      { name: "OpenAI", url: "https://openai.com/about/" },
      { name: "重复域名", url: "https://www.openai.com/news/" },
      { name: "无效", url: "javascript:alert(1)" },
    ],
    region: "美国",
    company: "OpenAI",
    savedAt: "2026-07-27T00:00:00.000Z",
  });

  assert.ok(favorite);
  assert.equal(favorite.href, "/companies/openai/");
  assert.deepEqual(favorite.keywords, ["智能体", "推理"]);
  assert.equal(favorite.sources.length, 1);
  assert.equal(favorite.sources[0]?.name, "OpenAI");
});

test("intelligence favorites retain card metadata and direct source links", () => {
  const favorite = normalizeFavorite({
    id: "homepage:article:abc",
    href: "/read/?url=https%3A%2F%2Fexample.com%2Farticle&title=Test",
    title: "Test",
    summary: "Reader entry",
    channel: "companies",
    channelLabel: "创业案例",
    publishedAt: "2026-07-27",
    importance: 91.4,
    eventType: "融资",
    savedAt: "2026-07-27T00:00:00.000Z",
  });

  assert.ok(favorite);
  assert.equal(favorite.href, "https://example.com/article");
  assert.equal(favorite.publishedAt, "2026-07-27");
  assert.equal(favorite.importance, 91);
  assert.equal(favorite.eventType, "融资");
});

test("favorite payload parser deduplicates ids and rejects invalid records", () => {
  const payload = JSON.stringify({
    schemaVersion: FAVORITES_SCHEMA_VERSION,
    items: [
      {
        id: "report:one",
        href: "/reports/one/",
        title: "报告一",
        summary: "",
        channel: "reports",
        channelLabel: "研究报告",
        keywords: [],
        sectors: ["机器人"],
        sources: [],
        savedAt: "2026-07-27T02:00:00.000Z",
      },
      {
        id: "report:one",
        href: "/reports/one/",
        title: "重复报告",
        channel: "reports",
        channelLabel: "研究报告",
        savedAt: "2026-07-27T01:00:00.000Z",
      },
      {
        id: "",
        href: "https://outside.example/",
        title: "无效记录",
        channel: "reports",
      },
    ],
  });

  const items = parseFavoriteItems(payload);
  assert.equal(items.length, 1);
  assert.equal(items[0]?.title, "报告一");
});

test("favorite toggle persists and removes an item in browser storage", () => {
  const values = new Map<string, string>();
  const previousWindow = globalThis.window;
  const fakeWindow = {
    localStorage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    },
    dispatchEvent: () => true,
  };
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: fakeWindow,
  });

  try {
    const input = {
      id: "technology:ai",
      href: "/technology/ai/",
      title: "AI / AGI",
      summary: "前沿人工智能赛道。",
      channel: "technology" as const,
      channelLabel: "新兴科技",
      keywords: ["智能体"],
      sectors: ["AI / AGI"],
      sources: [{ name: "OpenAI", url: "https://openai.com/" }],
      region: "全球" as const,
    };

    assert.equal(toggleFavorite(input), true);
    assert.equal(readFavoriteItems().length, 1);
    assert.ok(values.has(FAVORITES_STORAGE_KEY));
    assert.equal(toggleFavorite(input), false);
    assert.equal(readFavoriteItems().length, 0);
  } finally {
    if (previousWindow === undefined) {
      Reflect.deleteProperty(globalThis, "window");
    } else {
      Object.defineProperty(globalThis, "window", {
        configurable: true,
        value: previousWindow,
      });
    }
  }
});
