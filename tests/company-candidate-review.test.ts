import assert from "node:assert/strict";
import test from "node:test";

import type { CompanyCandidate } from "../lib/company-candidate-data";
import {
  applyCompanyCandidateDecisions,
  companyCandidateEvidenceFingerprint,
  countCompanyCandidateReviews,
  normalizeCompanyCandidateDecisionManifest,
  setCompanyCandidateDecision,
  validateCompanyCandidateDecision,
} from "../lib/company-candidate-review";

function candidate(overrides: Partial<CompanyCandidate> = {}): CompanyCandidate {
  return {
    id: "candidate-nova",
    decisionKey: "novarobotics",
    name: "Nova Robotics",
    aliases: ["Nova Robotics"],
    region: "全球",
    sector: "机器人",
    score: 70,
    status: "pending",
    reasons: ["至少两个独立公开来源"],
    firstSeenAt: "2026-08-01T00:00:00Z",
    lastSeenAt: "2026-08-04T00:00:00Z",
    articleCount: 2,
    sourceCount: 2,
    sourceHosts: ["a.example", "b.example"],
    sourceArticleIds: ["a", "b"],
    sourceUrls: ["https://a.example/nova", "https://b.example/nova"],
    eventTypes: ["融资"],
    note: "",
    mergedSlug: "",
    decidedAt: "",
    ...overrides,
  };
}

test("decision manifest normalizes valid audited decisions", () => {
  const manifest = normalizeCompanyCandidateDecisionManifest({
    schemaVersion: 1,
    decisions: {
      " NovaRobotics ": {
        status: "accepted",
        note: "确认是独立公司",
        decidedAt: "2026-08-05T00:00:00Z",
        reviewedBy: "VCIQ",
      },
      invalid: { status: "unknown" },
      pending: { status: "pending" },
    },
  });

  assert.deepEqual(Object.keys(manifest.decisions), ["novarobotics"]);
  assert.equal(manifest.decisions.novarobotics.reviewedBy, "VCIQ");
});

test("manifest decisions override stale candidate snapshot status", () => {
  const manifest = normalizeCompanyCandidateDecisionManifest({
    decisions: {
      novarobotics: {
        status: "rejected",
        note: "名称对应人物而不是公司",
        decidedAt: "2026-08-05T00:00:00Z",
        reviewedBy: "VCIQ",
      },
    },
  });
  const reviewed = applyCompanyCandidateDecisions([candidate()], manifest);

  assert.equal(reviewed[0].status, "rejected");
  assert.equal(reviewed[0].note, "名称对应人物而不是公司");
  assert.equal(reviewed[0].reviewedBy, "VCIQ");
  assert.deepEqual(countCompanyCandidateReviews(reviewed), {
    pending: 0,
    accepted: 0,
    rejected: 1,
    merged: 0,
    published: 0,
  });
});

test("restoring pending removes the versioned decision", () => {
  const manifest = normalizeCompanyCandidateDecisionManifest({
    decisions: {
      novarobotics: {
        status: "accepted",
        note: "确认是独立公司",
      },
    },
  });
  const next = setCompanyCandidateDecision(manifest, "novarobotics", {
    status: "pending",
    note: "",
    mergedSlug: "",
    decidedAt: "",
    reviewedBy: "",
  });

  assert.deepEqual(next.decisions, {});
});

test("non-pending decisions require an audit note", () => {
  assert.deepEqual(
    validateCompanyCandidateDecision({
      status: "accepted",
      note: "",
      mergedSlug: "",
    }),
    { valid: false, message: "请填写至少 4 个字符的审核说明。" },
  );
  assert.equal(
    validateCompanyCandidateDecision({
      status: "rejected",
      note: "这是人物，不是公司",
      mergedSlug: "",
    }).valid,
    true,
  );
});

test("merged decisions require a valid existing profile slug", () => {
  assert.equal(
    validateCompanyCandidateDecision({
      status: "merged",
      note: "已经存在正式公司档案",
      mergedSlug: "Bad Slug",
    }).valid,
    false,
  );
  assert.equal(
    validateCompanyCandidateDecision({
      status: "merged",
      note: "已经存在正式公司档案",
      mergedSlug: "nova-robotics",
    }).valid,
    true,
  );
});

test("evidence fingerprint changes when review evidence changes", () => {
  const original = companyCandidateEvidenceFingerprint(candidate());
  const changed = companyCandidateEvidenceFingerprint(
    candidate({
      articleCount: 3,
      sourceArticleIds: ["a", "b", "c"],
      sourceUrls: [
        "https://a.example/nova",
        "https://b.example/nova",
        "https://c.example/nova",
      ],
    }),
  );

  assert.notEqual(original, changed);
  assert.equal(
    original,
    companyCandidateEvidenceFingerprint(
      candidate({ sourceArticleIds: ["b", "a"], sourceUrls: ["https://b.example/nova", "https://a.example/nova"] }),
    ),
  );
});
