import assert from "node:assert/strict";
import test from "node:test";

import {
  companyCandidateSnapshot,
  normalizeCompanyCandidateSnapshot,
} from "../lib/company-candidate-data";

test("current company candidate snapshot is safe at the frontend boundary", () => {
  assert.equal(companyCandidateSnapshot.candidateCount, companyCandidateSnapshot.candidates.length);
  assert.ok(companyCandidateSnapshot.candidates.every((candidate) => candidate.score >= 0 && candidate.score <= 100));
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
