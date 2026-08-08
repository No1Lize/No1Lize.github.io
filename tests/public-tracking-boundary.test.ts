import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath: string) =>
  fs.readFileSync(path.join(root, relativePath), "utf8");

test("public tracking landing is build-based and contains no admin loader", () => {
  const source = read("app/tracking/page.tsx");
  assert.match(source, /coreResearchObjectStats/u);
  assert.match(source, /FOUR RESEARCH OBJECTS/u);
  assert.match(source, /PRIVATE REVIEW BOUNDARY/u);
  assert.doesNotMatch(source, /UserTrackingLoader/u);
  assert.doesNotMatch(source, /fetch\s*\(/u);
  assert.doesNotMatch(source, /tracking-capture-inbox-github/u);
});

test("public source tree has no tracking capture route", () => {
  assert.equal(
    fs.existsSync(path.join(root, "app/tracking/capture/page.tsx")),
    false,
  );
});

test("public research detail compatibility component contains no write client", () => {
  const source = read("components/tracking-entity-research-editor.tsx");
  assert.doesNotMatch(source, /["']use client["']/u);
  assert.doesNotMatch(source, /GitHub Token/u);
  assert.doesNotMatch(source, /commitTrackingEntityRecordManifest/u);
  assert.doesNotMatch(source, /sessionStorage/u);
  assert.match(source, /return null/u);
});

test("public companies page contains formal profiles only", () => {
  const page = read("app/companies/page.tsx");
  assert.match(page, /CompanyDirectory/u);
  assert.match(page, /CompanyProfileRefreshStatus/u);
  assert.doesNotMatch(page, /CompanyCandidateDirectory/u);
  assert.equal(
    fs.existsSync(path.join(root, "components/company-candidate-directory.tsx")),
    false,
  );
});

test("company review queue is not statically imported into the public frontend", () => {
  const dataBoundary = read("lib/company-candidate-data.ts");
  assert.doesNotMatch(dataBoundary, /public\/data\/company_candidates\.json/u);
  assert.match(dataBoundary, /candidates:\s*\[\]/u);

  const adminOnboarding = read("components/tracking-company-onboarding.tsx");
  assert.match(
    adminOnboarding,
    /config\/company_candidate_review_queue\.json/u,
  );
  assert.doesNotMatch(
    adminOnboarding,
    /public\/data\/company_candidates\.json/u,
  );
});

test("tracking snapshot coverage has no environment bypass", () => {
  const validator = read("scripts/validate-tracking-snapshot.mjs");
  assert.doesNotMatch(validator, /ALLOW_INCOMPLETE_TRACKING_COVERAGE/u);
  assert.doesNotMatch(validator, /TRACKING_SNAPSHOT_WARNING/u);
  assert.match(validator, /completedSources < expectedSources/u);
  assert.match(validator, /errors\.push/u);
});

test("Pages build audits the final public artifact and rejects private review files", () => {
  const packageJson = JSON.parse(read("package.json")) as {
    scripts: Record<string, string>;
  };
  assert.equal(
    packageJson.scripts["audit:public-artifact"],
    "node scripts/audit-public-artifact.mjs",
  );
  assert.match(packageJson.scripts["build:pages"], /audit:public-artifact/u);

  const audit = read("scripts/audit-public-artifact.mjs");
  assert.match(audit, /tracking\/capture/u);
  assert.match(audit, /GitHub Token/u);
  assert.match(audit, /totalBytes/u);
  assert.match(audit, /data\/company_candidates\.json/u);
  assert.match(audit, /data\/company_candidate_onboarding\.json/u);
  assert.match(audit, /company_candidate_review_queue\.json/u);
  assert.match(audit, /company_candidate_onboarding_state\.json/u);
});
