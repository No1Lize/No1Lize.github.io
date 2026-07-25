import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboard = readFileSync(new URL("../components/dashboard.tsx", import.meta.url), "utf8");
const eventTitle = dashboard.match(/function EventTitle[\s\S]*?\n}\n\nfunction MarketSummary/)?.[0] ?? "";

test("homepage intelligence titles always open the original source", () => {
  assert.match(eventTitle, /href=\{item\.source\.url\}/);
  assert.match(eventTitle, /target="_blank"/);
  assert.doesNotMatch(eventTitle, /companySlug|personSlug|\/companies\/|\/people\//);
});
