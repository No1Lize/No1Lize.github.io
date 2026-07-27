import assert from "node:assert/strict";
import test from "node:test";
import { normalizeTrackingConfig } from "../lib/user-tracking";

test("normalizes and deduplicates listed companies before GitHub persistence", () => {
  const config = normalizeTrackingConfig({
    schemaVersion: 1,
    tracks: [],
    sources: [],
    listedCompanies: [
      {
        id: "moutai",
        name: "贵州茅台",
        ticker: "600519.SH",
        market: "A股",
        sector: "消费",
        enabled: true,
        custom: true,
      },
      {
        id: "tencent-one",
        name: "腾信控股",
        ticker: "HK0700",
        market: "港股",
        sector: "AI / AGI",
        enabled: true,
        custom: true,
      },
      {
        id: "tencent-two",
        name: "腾讯控股",
        ticker: "0700.HK",
        market: "港股",
        sector: "AI / AGI",
        enabled: true,
        custom: true,
      },
      {
        id: "apple",
        name: "苹果公司",
        ticker: "aapl",
        market: "美股",
        sector: "消费电子",
        enabled: true,
        custom: true,
      },
      {
        id: "invalid-a",
        name: "非法A股",
        ticker: "12345",
        market: "A股",
        sector: "未分类",
        enabled: true,
        custom: true,
      },
    ],
  });

  assert.deepEqual(
    config.listedCompanies.map(({ name, ticker, market }) => ({
      name,
      ticker,
      market,
    })),
    [
      { name: "贵州茅台", ticker: "600519", market: "A股" },
      { name: "腾信控股", ticker: "00700", market: "港股" },
      { name: "苹果公司", ticker: "AAPL", market: "美股" },
    ],
  );
});

test("retains enabled flags and catalog slugs while normalizing tickers", () => {
  const config = normalizeTrackingConfig({
    listedCompanies: [
      {
        id: "catalog-cambricon",
        name: "寒武纪",
        ticker: "688256.SH",
        market: "A股",
        sector: "半导体",
        enabled: false,
        custom: false,
        catalogSlug: "cambricon",
      },
    ],
    tracks: [],
    sources: [],
  });

  assert.equal(config.listedCompanies[0].ticker, "688256");
  assert.equal(config.listedCompanies[0].enabled, false);
  assert.equal(config.listedCompanies[0].catalogSlug, "cambricon");
  assert.equal(config.listedCompanies[0].custom, false);
});
