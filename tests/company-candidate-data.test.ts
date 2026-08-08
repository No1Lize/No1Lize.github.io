import assert from "node:assert/strict";
import test from "node:test";

import {
  companyCandidateSnapshot,
  normalizeCompanyCandidateSnapshot,
  pendingCompanyCandidates,
} from "../lib/company-candidate-data";

test("public company candidate snapshot is intentionally empty", () => {
  assert.equal(companyCandidateSnapshot.candidateCount, 0);
  assert.equal(companyCandidateSnapshot.pendingCount, 0);
  assert.equal(companyCandidateSnapshot.acceptedCount, 0);
  assert.equal(companyCandidateSnapshot.publishedCount, 0);
  assert.deepEqual(companyCandidateSnapshot.candidates, []);
  assert.deepEqual(pendingCompanyCandidates, []);
});

test("candidate normalization rejects malformed records and unsafe urls", () => {
  const snapshot = normalizeCompanyCandidateSnapshot({
    schemaVersion: 1,
    generatedAt: "2026-08-03T00:00:00Z",
    candidates: [
      {
        id: "candidate-nova",
        name: "Nova Robotics",
        status: "pending",
        score: 82,
        sourceUrls: ["https://example.com/nova", "javascript:alert(1)"],
      },
      { id: "", name: "Broken", status: "pending" },
    ],
  });
  assert.equal(snapshot.candidateCount, 1);
  assert.deepEqual(snapshot.candidates[0].sourceUrls, ["https://example.com/nova"]);
});
