import assert from "node:assert/strict";
import test from "node:test";
import {
  listedCompanyIdentity,
  listedCompanySlug,
  normalizeMarketTicker,
} from "../lib/listed-company-identity";

test("normalizes A-share ticker variants", () => {
  assert.equal(normalizeMarketTicker("A股", "600519.SH"), "600519");
  assert.equal(normalizeMarketTicker("A股", "sh600519"), "600519");
  assert.equal(normalizeMarketTicker("A股", "60051"), "");
  assert.deepEqual(listedCompanyIdentity("A股", "600519.SH"), {
    market: "A股",
    ticker: "600519",
    slug: "a-600519",
    thsCode: "600519",
    quoteCode: "sh600519",
  });
});

test("normalizes Hong Kong ticker variants to five digits", () => {
  for (const value of ["700", "0700", "00700", "0700.HK", "HK0700"]) {
    assert.equal(normalizeMarketTicker("港股", value), "00700");
  }
  assert.deepEqual(listedCompanyIdentity("港股", "0700.HK"), {
    market: "港股",
    ticker: "00700",
    slug: "hk-00700",
    thsCode: "HK0700",
    quoteCode: "hk00700",
  });
});

test("normalizes US tickers and preserves catalog routes", () => {
  assert.equal(normalizeMarketTicker("美股", " aapl "), "AAPL");
  assert.equal(normalizeMarketTicker("美股", "BRK.B"), "BRK.B");
  assert.equal(normalizeMarketTicker("美股", "AAPL$"), "");
  assert.equal(listedCompanySlug("美股", "AAPL"), "us-aapl");
  assert.equal(listedCompanySlug("美股", "AAPL", "apple"), "apple");
});
