import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Normalize line endings so the extraction below works on CRLF checkouts too.
const dashboard = readFileSync(new URL("../components/dashboard.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
const eventTitle = dashboard.match(/function EventTitle[\s\S]*?\n}\n\nfunction MarketSummary/)?.[0] ?? "";

test("homepage intelligence titles always open the original source", () => {
  assert.match(eventTitle, /href=\{item\.source\.url\}/);
  assert.match(eventTitle, /target="_blank"/);
  assert.doesNotMatch(eventTitle, /companySlug|personSlug|\/companies\/|\/people\//);
});
