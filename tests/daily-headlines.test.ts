import assert from "node:assert/strict";
import test from "node:test";

import {
  DAILY_HEADLINES_LIMIT,
  getDailyHeadlines,
  selectDailyHeadlines,
} from "../lib/daily-headlines";

function article(overrides: Record<string, unknown> = {}) {
  return {
    id: `a-${Math.random().toString(36).slice(2, 8)}`,
    title: "某公司完成新一轮融资",
    type: "融资",
    publishedAt: "2026-07-26",
    importance: 50,
    source: {
      name: "投资界",
      platform: "专业媒体",
      url: `https://example.com/${Math.random().toString(36).slice(2, 8)}`,
    },
    ...overrides,
  };
}

test("each source contributes at most five headlines per day", () => {
  const articles = Array.from({ length: 9 }, (_, index) =>
    article({ id: `wx-${index}`, importance: 90 - index }),
  );
  const headlines = selectDailyHeadlines(articles);
  assert.equal(headlines.length, 5);
  assert.ok(headlines.every((item) => item.source === "投资界"));
  assert.equal(headlines[0].importance, 90);
});

test("search proxies and regulators are excluded from headlines", () => {
  const headlines = selectDailyHeadlines([
    article({ source: { name: "Google News", platform: "Google News", url: "https://news.google.com/x" } }),
    article({ source: { name: "SEC EDGAR", platform: "SEC", url: "https://sec.gov/x" } }),
    article({ source: { name: "腾讯科技", platform: "微信", url: "https://mp.weixin.qq.com/x" } }),
  ]);
  assert.deepEqual(
    headlines.map((item) => item.source),
    ["腾讯科技"],
  );
});

test("headlines cap at the rolling limit sorted by freshest day first", () => {
  const articles = Array.from({ length: 120 }, (_, index) =>
    article({
      id: `m-${index}`,
      publishedAt: index % 2 === 0 ? "2026-07-26" : "2026-07-25",
      source: {
        name: `来源${index}`,
        platform: "专业媒体",
        url: `https://media-${index}.example/a`,
      },
    }),
  );
  const headlines = selectDailyHeadlines(articles);
  assert.equal(headlines.length, DAILY_HEADLINES_LIMIT);
  const dates = headlines.map((item) => item.date);
  assert.deepEqual(dates, [...dates].sort().reverse());
});

test("undated or unlinked records never become headlines", () => {
  const headlines = selectDailyHeadlines([
    article({ publishedAt: "持续更新" }),
    article({ source: { name: "投资界", platform: "专业媒体", url: "" } }),
    article({ title: "" }),
  ]);
  assert.equal(headlines.length, 0);
});

test("live payload selection stays within contract", () => {
  const { headlines } = getDailyHeadlines();
  assert.ok(headlines.length <= DAILY_HEADLINES_LIMIT);
  for (const headline of headlines) {
    assert.ok(headline.title);
    assert.ok(/^https?:\/\//.test(headline.href));
    assert.notEqual(headline.platform, "Google News");
  }
});
