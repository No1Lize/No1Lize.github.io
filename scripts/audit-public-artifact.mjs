#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const outputRoot = path.join(root, "out");
const textExtensions = new Set([".html", ".js", ".json", ".txt", ".xml"]);
const forbiddenMarkers = [
  "GitHub Token",
  "ANALYST WORKSPACE",
  "保存后会触发 Pages 自动重建",
  "外部文章采集 | VCIQ",
];
const publicPageMarkers = ["上市跟踪", "PUBLIC MARKETS"];
const forbiddenCompanyReviewFiles = new Set([
  "data/company_candidates.json",
  "data/company_candidate_onboarding.json",
  "company_candidate_review_queue.json",
  "company_candidate_onboarding_state.json",
]);

function fail(messages) {
  for (const message of messages) {
    console.error(`PUBLIC_ARTIFACT_ERROR: ${message}`);
  }
  process.exit(1);
}

function filesUnder(directory) {
  const result = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...filesUnder(fullPath));
    else if (entry.isFile()) result.push(fullPath);
  }
  return result;
}

if (!fs.existsSync(outputRoot)) {
  fail(["out/ is missing; run the Pages build before auditing the artifact"]);
}

const files = filesUnder(outputRoot);
const errors = [];
let totalBytes = 0;
for (const filePath of files) {
  const relativePath = path.relative(outputRoot, filePath).split(path.sep).join("/");
  const size = fs.statSync(filePath).size;
  totalBytes += size;

  if (forbiddenCompanyReviewFiles.has(relativePath)) {
    errors.push(`private company review artifact leaked into out/${relativePath}`);
  }

  if (
    relativePath === "tracking/capture.html" ||
    relativePath === "tracking/capture/index.html" ||
    relativePath.startsWith("tracking/capture/")
  ) {
    errors.push(`private capture route leaked into out/${relativePath}`);
  }

  if (
    relativePath === "ipo.html" ||
    relativePath === "ipo/index.html" ||
    relativePath.startsWith("ipo/")
  ) {
    errors.push(`retired listed-market route leaked into out/${relativePath}`);
  }

  if (!textExtensions.has(path.extname(filePath))) continue;
  const content = fs.readFileSync(filePath, "utf8");
  for (const marker of forbiddenMarkers) {
    if (content.includes(marker)) {
      errors.push(`forbidden marker ${JSON.stringify(marker)} leaked into out/${relativePath}`);
    }
  }

  if ([".html", ".xml"].includes(path.extname(filePath))) {
    for (const marker of publicPageMarkers) {
      if (content.includes(marker)) {
        errors.push(
          `retired public-channel marker ${JSON.stringify(marker)} leaked into out/${relativePath}`,
        );
      }
    }
  }
}

if (errors.length) fail(errors);
console.log(
  `Public artifact audit passed: ${files.length} files, ${(totalBytes / 1024 / 1024).toFixed(2)} MiB, no admin, private company-review, or retired listed-market routes.`,
);
