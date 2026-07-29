import assert from "node:assert/strict";
import test from "node:test";

import { institutionDirectory } from "../lib/institution-ranking-data";
import { syncInstitutionDirectory } from "../scripts/sync-tracking-institution-directory";

function ventureTrack(sampleCompanies: string[] = []) {
  return {
    slug: "venture-capital",
    name: "风险投资",
    enabled: true,
    keywords: ["私人股权投资", "天使轮"],
    people: [],
    sampleCompanies,
  };
}

test("directory sync covers every non-tombstoned institution", () => {
  const retained = institutionDirectory[0].name;
  const blocked = institutionDirectory.slice(1).map((entry) => ({
    track: "venture-capital",
    kind: "sampleCompanies",
    value: entry.name,
    removedAt: "2026-07-29T00:00:00+00:00",
  }));
  const config = { tracks: [ventureTrack([retained])] };
  const ledger = {
    schemaVersion: 1,
    updatedAt: "",
    tracks: {},
    added: [],
    removed: blocked,
  };

  const result = syncInstitutionDirectory(config, ledger, { institutions: {} });

  assert.equal(result.changed, false);
  assert.equal(result.tracks[0].eligibleInstitutionCount, 1);
  assert.equal(result.tracks[0].blockedInstitutionCount, institutionDirectory.length - 1);
  assert.equal(result.tracks[0].sampleInstitutionCount, 1);
  assert.deepEqual(config.tracks[0].sampleCompanies, [retained]);
});

test("directory sync never restores an owner-deleted institution", () => {
  const blockedName = institutionDirectory[0].name;
  const config = { tracks: [ventureTrack([])] };
  const ledger = {
    schemaVersion: 1,
    updatedAt: "",
    tracks: {},
    added: [],
    removed: [
      {
        track: "venture-capital",
        kind: "sampleCompanies",
        value: blockedName,
        removedAt: "2026-07-29T00:00:00+00:00",
      },
    ],
  };

  const result = syncInstitutionDirectory(config, ledger, { institutions: {} });

  assert.equal(result.changed, true);
  assert.equal(result.tracks[0].eligibleInstitutionCount, institutionDirectory.length - 1);
  assert.equal(result.tracks[0].blockedInstitutionCount, 1);
  assert.equal(config.tracks[0].sampleCompanies.includes(blockedName), false);
  assert.equal(config.tracks[0].sampleCompanies.length, institutionDirectory.length - 1);
});

test("directory sync still rejects missing eligible coverage", () => {
  const config = { tracks: [ventureTrack([])] };
  const ledger = {
    schemaVersion: 1,
    updatedAt: "",
    tracks: {},
    added: [],
    removed: [],
  };

  const result = syncInstitutionDirectory(config, ledger, { institutions: {} });

  assert.equal(result.tracks[0].eligibleInstitutionCount, institutionDirectory.length);
  assert.equal(result.tracks[0].sampleInstitutionCount, institutionDirectory.length);
  assert.equal(config.tracks[0].sampleCompanies.length, institutionDirectory.length);
});
