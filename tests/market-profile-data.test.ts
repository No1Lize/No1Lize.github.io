import assert from "node:assert/strict";
import test from "node:test";
import { latestQuoteView, marketProfiles } from "../lib/market-profile-data";

function metricValue(slug: string, id: string) {
  return marketProfiles[slug]?.metrics.find((metric) => metric.id === id)?.value ?? "";
}

test("cambricon renders numeric market cap and normalized region", () => {
  const profile = marketProfiles.cambricon;
  assert.ok(profile);
  assert.match(metricValue("cambricon", "marketCap"), /\d/u);
  assert.ok(profile.company.region);
  assert.doesNotMatch(profile.company.description ?? "", /多项荣誉/u);
  assert.ok((profile.company.description ?? "").length <= 420);
});

test("navigation labels cannot replace CATL industry or company introduction", () => {
  const profile = marketProfiles.catl;
  assert.ok(profile);
  assert.doesNotMatch(profile.company.industry ?? "", /总市值|所属地域|经营分析/u);
  assert.doesNotMatch(profile.company.description ?? "", /^所属地域|经营分析/u);
  assert.ok((profile.company.description ?? "").length >= 40);
});

test("all enabled snapshot profiles have a display region and readable market cap when available", () => {
  for (const profile of Object.values(marketProfiles)) {
    assert.ok(profile.company.region, `${profile.slug}: missing region`);
    const marketCap = profile.metrics.find((metric) => metric.id === "marketCap")?.value;
    if (marketCap) assert.match(marketCap, /\d/u, `${profile.slug}: non-numeric market cap`);
  }
});

test("quote and news normalization keeps optional double-source fields safe", () => {
  for (const profile of Object.values(marketProfiles)) {
    assert.ok(Array.isArray(profile.news), `${profile.slug}: news must normalize to an array`);
    for (const item of profile.news ?? []) {
      assert.ok(item.title.trim(), `${profile.slug}: empty news title`);
      assert.match(item.url, /^https?:\/\//u, `${profile.slug}: invalid news link`);
      assert.ok(item.publishedAt.trim(), `${profile.slug}: missing news time`);
    }
    if (profile.quote) {
      assert.ok(
        Number.isFinite(profile.quote.price) && profile.quote.price > 0,
        `${profile.slug}: quote price must be positive`,
      );
    }
    const view = latestQuoteView(profile);
    if (view) {
      assert.match(view.price, /\d/u, `${profile.slug}: quote view lacks numeric price`);
      assert.ok(Number.isFinite(view.changePercent), `${profile.slug}: invalid change percent`);
    }
  }
});
