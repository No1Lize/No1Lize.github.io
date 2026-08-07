import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();
const read = (relativePath: string) => readFileSync(path.join(ROOT, relativePath), "utf8");

const page = read("app/page.tsx");
const dashboard = read("components/dashboard-client.tsx");
const articles = read("lib/use-articles.ts");
const domRuntime = read("lib/intelligence-dom-runtime.ts");

test("homepage client does not import full build-time research datasets", () => {
  assert.doesNotMatch(dashboard, /@\/lib\/intelligence-data/);
  assert.doesNotMatch(dashboard, /@\/lib\/tracked-sectors/);
  assert.doesNotMatch(dashboard, /@\/lib\/core-research-objects/);
  assert.match(page, /DashboardClient/);
  assert.match(page, /initialPayload/);
  assert.match(page, /bootstrap/);
});

test("browser article refresh avoids a second full validation walk", () => {
  assert.doesNotMatch(articles, /from "zod"/);
  assert.doesNotMatch(articles, /@\/lib\/intelligence-data/);
  assert.doesNotMatch(articles, /payloadSchema\.parse/);
  assert.match(articles, /parseArticlePayload/);
  assert.match(articles, /refetchIntervalInBackground: false/);
  assert.match(articles, /refetchOnWindowFocus: false/);
});

test("intelligence controls mount progressively after hydration", () => {
  assert.match(domRuntime, /new IntersectionObserver/);
  assert.match(domRuntime, /rootMargin: "1200px 0px"/);
  assert.match(domRuntime, /requestIdleCallback/);
  assert.match(domRuntime, /activeRows/);
  assert.match(domRuntime, /scheduleCandidateRefresh/);
});
