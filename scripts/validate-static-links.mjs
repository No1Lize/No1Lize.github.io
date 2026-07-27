#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT_DIR = path.join(ROOT, "out");
const REPORT_PATH = path.join(OUT_DIR, "link-check-report.json");
const MAX_REPORTED_FAILURES = 100;

function fail(messages) {
  console.error("STATIC_LINK_ERROR:");
  for (const message of messages.slice(0, MAX_REPORTED_FAILURES)) {
    console.error(`- ${message}`);
  }
  if (messages.length > MAX_REPORTED_FAILURES) {
    console.error(`- ...另有 ${messages.length - MAX_REPORTED_FAILURES} 个错误未显示`);
  }
  process.exit(1);
}

function walkFiles(directory) {
  const result = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      result.push(...walkFiles(absolute));
    } else if (entry.isFile()) {
      result.push(absolute);
    }
  }
  return result;
}

function toPosix(value) {
  return value.split(path.sep).join("/");
}

function decodeHtmlAttribute(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .trim();
}

function isIgnoredHref(href) {
  const lowered = href.toLowerCase();
  return (
    !href ||
    href.startsWith("#") ||
    href.startsWith("//") ||
    lowered.startsWith("http://") ||
    lowered.startsWith("https://") ||
    lowered.startsWith("mailto:") ||
    lowered.startsWith("tel:") ||
    lowered.startsWith("javascript:") ||
    lowered.startsWith("data:") ||
    lowered.startsWith("blob:")
  );
}

function hrefPathname(href, htmlRelativePath) {
  const base = new URL(`https://static.invalid/${htmlRelativePath}`);
  const resolved = new URL(href, base);
  let pathname = resolved.pathname;
  try {
    pathname = decodeURIComponent(pathname);
  } catch {
    // Keep the encoded pathname so it is still checked and reported.
  }
  return pathname.replace(/^\/+/, "");
}

function candidateTargets(pathname) {
  if (!pathname) return ["index.html"];

  const normalized = pathname.replace(/\/+$/, "");
  const extension = path.posix.extname(normalized);
  if (extension) return [normalized];

  return [
    normalized,
    `${normalized}.html`,
    `${normalized}/index.html`,
  ];
}

if (!fs.existsSync(OUT_DIR)) {
  fail(["缺少 out 目录；请先执行 GitHub Pages 静态构建。"]);
}

const absoluteFiles = walkFiles(OUT_DIR);
const relativeFiles = new Set(
  absoluteFiles.map((file) => toPosix(path.relative(OUT_DIR, file))),
);
const htmlFiles = absoluteFiles.filter((file) => file.endsWith(".html"));
const failures = [];
let checkedLinks = 0;

for (const htmlFile of htmlFiles) {
  const htmlRelativePath = toPosix(path.relative(OUT_DIR, htmlFile));
  const html = fs.readFileSync(htmlFile, "utf8");
  const hrefPattern = /\bhref\s*=\s*(["'])(.*?)\1/gi;

  for (const match of html.matchAll(hrefPattern)) {
    const href = decodeHtmlAttribute(match[2]);
    if (isIgnoredHref(href)) continue;

    checkedLinks += 1;
    let pathname;
    try {
      pathname = hrefPathname(href, htmlRelativePath);
    } catch {
      failures.push(`${htmlRelativePath}: 无法解析 href=${JSON.stringify(href)}`);
      continue;
    }

    const candidates = candidateTargets(pathname);
    if (!candidates.some((candidate) => relativeFiles.has(candidate))) {
      failures.push(
        `${htmlRelativePath}: href=${JSON.stringify(href)} 未找到静态目标（检查了 ${candidates.join(", ")}）`,
      );
    }
  }
}

if (failures.length) fail(failures);

const report = {
  generatedAt: new Date().toISOString(),
  htmlPages: htmlFiles.length,
  checkedInternalLinks: checkedLinks,
  brokenInternalLinks: 0,
};
fs.writeFileSync(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(
  `Static link validation passed: ${report.htmlPages} HTML pages, ${report.checkedInternalLinks} internal links.`,
);
