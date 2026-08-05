import assert from "node:assert/strict";
import test from "node:test";

import {
  externalTrackingCaptureBookmarklet,
  parseExternalTrackingCaptureParams,
  recommendExternalTrackingCaptureTracks,
} from "../lib/external-tracking-capture";
import type { UserTrackingConfig } from "../lib/user-tracking";

function config(): UserTrackingConfig {
  return {
    schemaVersion: 1,
    tracks: [
      {
        slug: "prediction-market",
        name: "预测市场",
        enabled: true,
        custom: true,
        keywords: ["prediction market", "事件合约"],
        people: [],
        sampleCompanies: ["Polymarket", "Kalshi"],
      },
      {
        slug: "ai-agi",
        name: "AI / AGI",
        enabled: true,
        custom: false,
        keywords: ["大模型"],
        people: [],
        sampleCompanies: ["OpenAI"],
      },
    ],
    listedCompanies: [],
    sources: [],
  };
}

test("selected company text becomes a canonical external capture prefill", () => {
  const params = new URLSearchParams({
    url: "https://finance.example/story?utm_source=test",
    title: "Polymarket 洽谈融资，Kalshi 扩张",
    selection: "Polymarket 公司",
    type: "company",
    source: "新浪财经",
  });
  const prefill = parseExternalTrackingCaptureParams(params);
  assert.equal(prefill.source.url, "https://finance.example/story?utm_source=test");
  assert.equal(prefill.source.title, "Polymarket 洽谈融资,Kalshi 扩张");
  assert.equal(prefill.source.sourceName, "新浪财经");
  assert.equal(prefill.source.channel, "external");
  assert.match(prefill.source.summary, /Polymarket 公司/u);
  assert.deepEqual(prefill.entities, [
    { entityType: "company", name: "Polymarket" },
  ]);
});

test("explicit entity prefixes support multiple entity types", () => {
  const params = new URLSearchParams({
    url: "https://example.com/prediction-market",
    title: "预测市场竞争格局",
  });
  params.append("entity", "company:Polymarket");
  params.append("entity", "company:Kalshi");
  params.append("entity", "topic:预测市场");
  const prefill = parseExternalTrackingCaptureParams(params);
  assert.deepEqual(prefill.entities, [
    { entityType: "company", name: "Polymarket" },
    { entityType: "company", name: "Kalshi" },
    { entityType: "topic", name: "预测市场" },
  ]);
});

test("unsafe source urls are not accepted", () => {
  const prefill = parseExternalTrackingCaptureParams(
    new URLSearchParams({
      url: "javascript:alert(1)",
      title: "Unsafe",
      selection: "Example",
    }),
  );
  assert.equal(prefill.source.url, "");
});

test("track recommendations use names, keywords and known companies", () => {
  const prefill = parseExternalTrackingCaptureParams(
    new URLSearchParams({
      url: "https://example.com/story",
      title: "Polymarket and Kalshi compete in prediction markets",
      selection: "Polymarket",
      type: "company",
    }),
  );
  assert.deepEqual(
    recommendExternalTrackingCaptureTracks(prefill, config()),
    ["prediction-market"],
  );
});

test("explicit track query parameters take precedence", () => {
  const params = new URLSearchParams({
    url: "https://example.com/story",
    title: "External article",
    track: "ai-agi",
  });
  const prefill = parseExternalTrackingCaptureParams(params);
  assert.deepEqual(
    recommendExternalTrackingCaptureTracks(prefill, config()),
    ["ai-agi"],
  );
});

test("bookmarklet only forwards the current URL, title and selected text", () => {
  const script = externalTrackingCaptureBookmarklet();
  assert.match(script, /^javascript:/u);
  assert.match(script, /location\.href/u);
  assert.match(script, /document\.title/u);
  assert.match(script, /getSelection/u);
  assert.doesNotMatch(script, /searchParams\.set\(['"](?:token|github)/iu);
});
