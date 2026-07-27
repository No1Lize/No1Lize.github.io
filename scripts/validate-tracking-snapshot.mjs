#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const configPath = path.join(root, "config", "user_tracking.json");
const snapshotPath = path.join(root, "public", "data", "articles.json");
const allowIncompleteCoverage =
  process.env.ALLOW_INCOMPLETE_TRACKING_COVERAGE === "true";

function fail(messages) {
  for (const message of messages) {
    console.error(`TRACKING_SNAPSHOT_ERROR: ${message}`);
  }
  process.exit(1);
}

function clean(value, limit = 500) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function cleanList(value, limit = 80) {
  if (!Array.isArray(value)) return [];
  const result = [];
  const seen = new Set();
  for (const raw of value) {
    const item = clean(raw, 160);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function canonicalTracks(config) {
  return (Array.isArray(config.tracks) ? config.tracks : [])
    .filter((track) => track && typeof track === "object" && track.enabled !== false)
    .map((track) => ({
      slug: clean(track.slug, 80),
      name: clean(track.name, 80),
      keywords: cleanList(track.keywords, 60),
      people: cleanList(track.people, 40),
      sampleCompanies: cleanList(track.sampleCompanies, 40),
    }))
    .filter((track) => track.slug && track.name);
}

if (!fs.existsSync(configPath) || !fs.existsSync(snapshotPath)) {
  fail(["missing config/user_tracking.json or public/data/articles.json"]);
}

let config;
let snapshot;
try {
  config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  snapshot = JSON.parse(fs.readFileSync(snapshotPath, "utf8"));
} catch (error) {
  fail([`invalid tracking JSON: ${error.message}`]);
}

const tracks = canonicalTracks(config);
const expectedHash = crypto
  .createHash("sha256")
  .update(JSON.stringify(tracks), "utf8")
  .digest("hex");
const actualHash = clean(snapshot.trackingConfigHash, 80);
const errors = [];
const coverageWarnings = [];

if (!actualHash) {
  errors.push("article snapshot has no trackingConfigHash; crawler enrichment has not run");
} else if (actualHash !== expectedHash) {
  errors.push(
    "tracking configuration is newer than the article snapshot; wait for Refresh public intelligence",
  );
}

const coverage =
  snapshot.trackCoverage && typeof snapshot.trackCoverage === "object"
    ? snapshot.trackCoverage
    : {};
for (const track of tracks) {
  const row = coverage[track.slug];
  if (!row || typeof row !== "object") {
    errors.push(`${track.name}: missing crawler coverage record`);
    continue;
  }
  const expectedSources = Number(row.expectedSources ?? 0);
  const completedSources = Number(row.completedSources ?? 0);
  if (expectedSources < 3) {
    errors.push(`${track.name}: expectedSources=${expectedSources}; three discovery routes are required`);
  }
  if (completedSources < expectedSources) {
    const message =
      `${track.name}: only ${completedSources}/${expectedSources} discovery routes completed`;
    if (allowIncompleteCoverage) {
      coverageWarnings.push(message);
    } else {
      errors.push(message);
    }
  }
}

if (errors.length) fail(errors);
for (const warning of coverageWarnings) {
  console.warn(`TRACKING_SNAPSHOT_WARNING: ${warning}`);
}
console.log(
  coverageWarnings.length
    ? `Tracking snapshot deployable: ${tracks.length} tracks match ${actualHash.slice(0, 12)}; ${coverageWarnings.length} track(s) still need a full discovery refresh.`
    : `Tracking snapshot valid: ${tracks.length} tracks match ${actualHash.slice(0, 12)} and all discovery routes were attempted.`,
);
