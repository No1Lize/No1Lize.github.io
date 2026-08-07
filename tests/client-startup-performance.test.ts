import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();
const read = (relativePath: string) => readFileSync(path.join(ROOT, relativePath), "utf8");

const page = read("app/page.tsx");
const layout = read("app/layout.tsx");
const dashboard = read("components/dashboard-client.tsx");
const liveStatus = read("components/live-status.tsx");
const siteHeader = read("components/site-header.tsx");
const articles = read("lib/use-articles.ts");
const domRuntime = read("lib/intelligence-dom-runtime.ts");
const packageJson = read("package.json");

test("homepage client does not import full build-time research datasets", () => {
  assert.doesNotMatch(dashboard, /@\/lib\/intelligence-data/);
  assert.doesNotMatch(dashboard, /@\/lib\/tracked-sectors/);
  assert.doesNotMatch(dashboard, /@\/lib\/core-research-objects/);
  assert.match(page, /DashboardClient/);
  assert.match(page, /initialPayload/);
  assert.match(page, /bootstrap/);
});

test("global header status is build-time and cannot trigger the article archive fetch", () => {
  assert.doesNotMatch(liveStatus, /"use client"/);
  assert.doesNotMatch(liveStatus, /useArticles/);
  assert.match(liveStatus, /@\/public\/data\/articles\.json/);
  assert.doesNotMatch(siteHeader, /@\/components\/live-status/);
  assert.match(siteHeader, /status: ReactNode/);
  assert.match(layout, /<SiteHeader status={<LiveStatus \/>} \/>/);
});

test("browser article archive avoids startup fetch and a second full validation walk", () => {
  assert.doesNotMatch(articles, /from "zod"/);
  assert.doesNotMatch(articles, /@\/lib\/intelligence-data/);
  assert.doesNotMatch(articles, /payloadSchema\.parse/);
  assert.match(articles, /parseArticlePayload/);
  assert.match(articles, /pointerdown/);
  assert.match(articles, /keydown/);
  assert.match(articles, /enabled: enabled/);
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

test("Pages build enforces a homepage client asset budget", () => {
  assert.match(packageJson, /check:homepage-performance/);
  assert.match(packageJson, /scripts\/check-homepage-performance-budget\.mjs/);
});
