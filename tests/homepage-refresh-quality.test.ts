import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboard = readFileSync("components/dashboard-client.tsx", "utf8");
const page = readFileSync("app/page.tsx", "utf8");
const headlines = readFileSync("components/daily-headlines.tsx", "utf8");

test("homepage defaults key events to trusted evidence", () => {
  assert.match(dashboard, /qualityScope === "all" \|\| item\.qualityStatus !== "低可信"/);
  assert.match(dashboard, /<option value="trusted">可信优先<\/option>/);
  assert.match(page, /\.filter\(\(item\) => item\.qualityStatus !== "低可信"\)/);
});

test("homepage distinguishes today's events from current-crawl additions", () => {
  assert.match(dashboard, /今日事件 \{todayArticleCount\} 条/);
  assert.match(dashboard, /本轮新收录/);
  assert.match(dashboard, /refreshAudit\?\.todayArticleCount \?\? bootstrap\.todayArticleCount/);
  assert.match(dashboard, /refreshAudit\?\.newArticleCount \?\? "待刷新"/);
});

test("rolling 200-item column is labeled as latest headlines", () => {
  assert.match(headlines, /02 \/ LATEST HEADLINES/);
  assert.match(headlines, /<h2>最新头条<\/h2>/);
  assert.doesNotMatch(headlines, /<h2>今日头条<\/h2>/);
});
