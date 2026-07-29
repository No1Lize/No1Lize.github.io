import assert from "node:assert/strict";
import test from "node:test";
import {
  HOTNESS_WEIGHTS,
  calculateHotnessScore,
  canonicalHotnessKey,
  parseHotnessItems,
} from "../lib/hotness";

test("canonicalHotnessKey removes tracking noise and fragments", () => {
  assert.equal(
    canonicalHotnessKey(
      "HTTPS://Example.com/article/?utm_source=feed&b=2&a=1#comments",
    ),
    "https://example.com/article?a=1&b=2",
  );
});

test("canonicalHotnessKey unwraps the internal read route", () => {
  assert.equal(
    canonicalHotnessKey(
      "/read?url=https%3A%2F%2Fexample.com%2Fnews%2F%3Futm_medium%3Dsocial",
    ),
    "https://example.com/news",
  );
});

test("hotness score gives share and favorite stronger weights than opens", () => {
  assert.deepEqual(HOTNESS_WEIGHTS, { open: 1, favorite: 5, share: 8 });
  assert.equal(
    calculateHotnessScore({ opens: 3, favorite: true, shares: 2 }),
    24,
  );
  assert.ok(
    calculateHotnessScore({ opens: 0, favorite: false, shares: 1 }) >
      calculateHotnessScore({ opens: 1, favorite: true, shares: 0 }),
  );
});

test("parseHotnessItems validates counts and deduplicates canonical URLs", () => {
  const items = parseHotnessItems(
    JSON.stringify({
      schemaVersion: 1,
      items: [
        {
          id: "first",
          href: "https://example.com/news?utm_source=a",
          title: "First",
          opens: 4,
          favorite: true,
          shares: 1,
          firstSeenAt: "2026-07-29T00:00:00Z",
          updatedAt: "2026-07-29T01:00:00Z",
        },
        {
          id: "duplicate",
          href: "https://example.com/news#top",
          title: "Duplicate",
          opens: 99,
          favorite: false,
          shares: 99,
          firstSeenAt: "2026-07-29T00:00:00Z",
          updatedAt: "2026-07-29T00:30:00Z",
        },
      ],
    }),
  );

  assert.equal(items.length, 1);
  assert.equal(items[0]?.opens, 4);
  assert.equal(items[0]?.favorite, true);
  assert.equal(items[0]?.shares, 1);
});
