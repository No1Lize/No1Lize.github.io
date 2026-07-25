import assert from "node:assert/strict";
import test from "node:test";

import { companies, institutionCatalog } from "../lib/catalog-data";
import {
  companyVentureProfiles,
  getCompanyVentureProfile,
  getInstitutionVentureProfile,
  institutionVentureProfiles,
  ventureProfileQualityGate,
  ventureProfileSourceStatus,
  ventureResearchModelVersion,
} from "../lib/venture-profile-data";

const companySlugs = new Set(companies.map((item) => item.slug));
const institutionSlugs = new Set(institutionCatalog.map((item) => item.slug));

test("venture profile snapshot only contains catalog entities", () => {
  for (const slug of Object.keys(companyVentureProfiles)) {
    assert.ok(companySlugs.has(slug), `unknown company venture profile: ${slug}`);
  }
  for (const slug of Object.keys(institutionVentureProfiles)) {
    assert.ok(institutionSlugs.has(slug), `unknown institution venture profile: ${slug}`);
  }
});

test("venture profile getters are safe before and after the first crawl", () => {
  assert.equal(getCompanyVentureProfile("missing-company"), undefined);
  assert.equal(getInstitutionVentureProfile("missing-institution"), undefined);
  for (const [slug, profile] of Object.entries(companyVentureProfiles)) {
    assert.equal(getCompanyVentureProfile(slug), profile);
  }
  for (const [slug, profile] of Object.entries(institutionVentureProfiles)) {
    assert.equal(getInstitutionVentureProfile(slug), profile);
  }
});

test("venture profile sources are traceable public URLs", () => {
  const profiles = [
    ...Object.values(companyVentureProfiles),
    ...Object.values(institutionVentureProfiles),
  ];
  for (const profile of profiles) {
    assert.ok(["ok", "partial", "retained", "fallback"].includes(profile.status));
    assert.ok(Number(profile.evidenceScore ?? 0) >= 0);
    assert.ok(Number(profile.evidenceScore ?? 0) <= 100);
    for (const source of profile.sources) {
      assert.match(source.url, /^https?:\/\//u);
      assert.ok(source.name.length > 0);
    }
  }
});

test("research model v2 exposes the same structured fields for every entity", () => {
  if (ventureResearchModelVersion < 2) return;
  for (const profile of Object.values(companyVentureProfiles)) {
    assert.ok(profile.projectBackground?.summary);
    assert.ok(Array.isArray(profile.technologyProducts));
    assert.ok(profile.capitalSummary);
    assert.ok(profile.exitPerformance);
    for (const product of profile.technologyProducts ?? []) {
      assert.ok(product.name);
      assert.ok(product.description);
    }
  }
  for (const profile of Object.values(institutionVentureProfiles)) {
    assert.ok(profile.recentYearSummary);
    assert.match(profile.recentYearSummary!.periodStart, /^20\d{2}-\d{2}-\d{2}$/u);
    assert.match(profile.recentYearSummary!.periodEnd, /^20\d{2}-\d{2}-\d{2}$/u);
    for (const item of profile.classicCases) {
      assert.ok(item.analysis);
    }
  }
});

test("venture profile runtime statuses use unique entity keys", () => {
  const keys = ventureProfileSourceStatus.map((item) => `${item.kind}:${item.slug}`);
  assert.equal(new Set(keys).size, keys.length);
  for (const item of ventureProfileSourceStatus) {
    assert.ok(item.kind === "company" || item.kind === "institution");
    assert.ok(item.slug.length > 0);
  }
});

test("venture profile quality gate has internally consistent checks", () => {
  if (!ventureProfileQualityGate) return;
  const checks = Object.values(ventureProfileQualityGate.checks ?? {});
  assert.equal(
    ventureProfileQualityGate.passed,
    checks.every((check) => check.passed),
  );
});
