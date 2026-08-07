import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const layout = readFileSync("app/layout.tsx", "utf8");
const header = readFileSync("components/site-header.tsx", "utf8");

test("public layout renders directly in the fixed light theme", () => {
  assert.match(layout, /<html lang="zh-CN" data-theme="light">/);
  assert.doesNotMatch(layout, /suppressHydrationWarning/);
});

test("site header exposes no runtime light-dark theme switch", () => {
  assert.doesNotMatch(header, /lize-theme/);
  assert.doesNotMatch(header, /localStorage/);
  assert.doesNotMatch(header, /useSyncExternalStore/);
  assert.doesNotMatch(header, /dataset\.theme/);
  assert.doesNotMatch(header, /Moon|Sun/);
  assert.doesNotMatch(header, /切换浅色主题|切换深色主题/);
});
