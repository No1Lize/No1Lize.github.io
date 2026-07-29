#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const ALLOWED_DEV_ADVISORIES = new Set([
  "GHSA-mh99-v99m-4gvg",
]);
const SAFE_BRACE_EXPANSION_BACKPORTS = new Set([
  "1.1.16",
  "2.1.2",
  "3.0.2",
  "5.0.8",
]);

function runAudit(args) {
  const result = spawnSync("npm", ["audit", "--json", ...args], {
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024,
  });
  let payload;
  try {
    payload = JSON.parse(result.stdout || "{}");
  } catch (error) {
    console.error(result.stdout);
    console.error(result.stderr);
    throw new Error(`npm audit did not return valid JSON: ${error.message}`);
  }
  return { result, payload };
}

function advisoryId(entry) {
  if (!entry || typeof entry !== "object") return "";
  const url = String(entry.url || "");
  const match = url.match(/GHSA-[a-z0-9-]+/i);
  return match ? match[0].toUpperCase() : "";
}

function directAdvisories(payload) {
  const advisories = [];
  for (const [packageName, detail] of Object.entries(payload.vulnerabilities || {})) {
    for (const via of detail.via || []) {
      if (via && typeof via === "object") {
        advisories.push({ packageName, id: advisoryId(via), via });
      }
    }
  }
  return advisories;
}

function validateBraceExpansionBackports() {
  const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
  const installed = [];
  for (const [path, detail] of Object.entries(lock.packages || {})) {
    if (path === "node_modules/brace-expansion" || path.endsWith("/node_modules/brace-expansion")) {
      installed.push({ path, version: String(detail.version || "") });
    }
  }
  if (installed.length === 0) {
    throw new Error("package-lock.json contains no brace-expansion installation to validate");
  }
  const unsafe = installed.filter(({ version }) => !SAFE_BRACE_EXPANSION_BACKPORTS.has(version));
  if (unsafe.length > 0) {
    throw new Error(`unsafe brace-expansion versions in lockfile: ${JSON.stringify(unsafe)}`);
  }
  console.log(
    `Validated official brace-expansion maintenance releases: ${installed
      .map(({ version }) => version)
      .join(", ")}`,
  );
}

const production = runAudit(["--omit=dev", "--audit-level=high"]);
if (production.result.status !== 0) {
  console.error(JSON.stringify(production.payload, null, 2));
  throw new Error("high or critical production dependency vulnerability detected");
}
console.log("Production dependency audit passed with no high or critical vulnerabilities.");

const full = runAudit(["--audit-level=high"]);
if (full.result.status === 0) {
  console.log("Full dependency audit passed with no high or critical vulnerabilities.");
  process.exit(0);
}

const advisories = directAdvisories(full.payload);
const unapproved = advisories.filter(
  ({ id }) => !id || !ALLOWED_DEV_ADVISORIES.has(id),
);
if (unapproved.length > 0) {
  console.error(JSON.stringify(full.payload, null, 2));
  throw new Error(
    `unapproved high or critical development advisory detected: ${JSON.stringify(
      unapproved.map(({ packageName, id }) => ({ packageName, id })),
    )}`,
  );
}

validateBraceExpansionBackports();
console.log(
  "The only remaining npm audit finding is the brace-expansion advisory whose " +
    "maintenance fixes are pinned in package-lock.json. No other high or critical " +
    "development advisory is accepted.",
);
