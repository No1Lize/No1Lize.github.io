import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveStarInvestorReview,
  starMarketInvestorAllRecords,
  starMarketInvestorRecords,
  starMarketInvestorStats,
} from "../lib/star-market-investor-data";
import { extractStarInvestorHoldingFromEvidence } from "../lib/star-market-investor-review";

test("strong automatic extraction remains pending instead of being auto-verified", () => {
  const review = deriveStarInvestorReview({
    name: "北京示例创业投资基金（有限合伙）",
    companyName: "示例科技",
    evidence: "北京示例创业投资基金（有限合伙） 1,250万股 12.50%",
    preIpoShares: 12_500_000,
    preIpoOwnershipPct: 12.5,
  });

  assert.equal(review.reviewStatus, "needs_review");
  assert.ok(review.reviewReasons.includes("awaiting-human-review"));
});

test("narrative fragments and generic legal forms are rejected", () => {
  const narrative = deriveStarInvestorReview({
    name: "事务合伙人为知己行远（天津）科技有限公司",
    companyName: "示例科技",
    evidence: "事务合伙人为知己行远（天津）科技有限公司，宋某担任执行事务合伙人。",
  });
  const generic = deriveStarInvestorReview({
    name: "管理有限公司",
    companyName: "示例科技",
    evidence: "管理有限公司",
  });

  assert.equal(narrative.reviewStatus, "rejected");
  assert.ok(narrative.reviewReasons.includes("narrative-name-fragment"));
  assert.equal(generic.reviewStatus, "rejected");
  assert.ok(generic.reviewReasons.includes("generic-legal-form"));
});

test("listed issuer legal name is rejected as its own investor candidate", () => {
  const review = deriveStarInvestorReview({
    name: "中科寒武纪科技股份有限公司",
    companyName: "寒武纪",
    evidence: "中科寒武纪科技股份有限公司首次公开发行股票并在科创板上市招股说明书",
    preIpoOwnershipPct: 33.19,
  });

  assert.equal(review.reviewStatus, "rejected");
  assert.ok(review.reviewReasons.includes("issuer-name"));
});

test("explicit human review status is preserved when evidence is consistent", () => {
  const review = deriveStarInvestorReview({
    name: "北京示例投资有限公司",
    companyName: "示例科技",
    evidence: "北京示例投资有限公司 100万股 1.00%",
    preIpoOwnershipPct: 1,
    reviewStatus: "verified",
    reviewReasons: [],
  });

  assert.equal(review.reviewStatus, "verified");
  assert.deepEqual(review.reviewReasons, []);
});

test("same-line holding extraction ignores values before the candidate name", () => {
  const holding = extractStarInvestorHoldingFromEvidence(
    "其他主体 33.19% 北京示例投资有限公司 100万股 1.00%",
    "北京示例投资有限公司",
  );

  assert.equal(holding.shares, 1_000_000);
  assert.equal(holding.ownershipPct, 1);
  assert.deepEqual(holding.reasons, []);
});

test("recorded holding value that conflicts with the evidence line is rejected", () => {
  const review = deriveStarInvestorReview({
    name: "北京示例投资有限公司",
    companyName: "示例科技",
    evidence: "北京示例投资有限公司 100万股 1.00%",
    preIpoOwnershipPct: 33.19,
  });

  assert.equal(review.reviewStatus, "rejected");
  assert.ok(review.reviewReasons.includes("holding-value-mismatch"));
});

test("multiple percentages after one candidate are treated as ambiguous", () => {
  const review = deriveStarInvestorReview({
    name: "北京示例投资有限公司",
    companyName: "示例科技",
    evidence: "北京示例投资有限公司 5.00% 10.00%",
    preIpoOwnershipPct: 5,
  });

  assert.equal(review.reviewStatus, "rejected");
  assert.ok(review.reviewReasons.includes("ambiguous-holding-row"));
});

test("public directory excludes rejected audit records and preserves count identity", () => {
  assert.ok(
    starMarketInvestorRecords.every(
      (record) => record.investor.reviewStatus !== "rejected",
    ),
  );
  assert.equal(starMarketInvestorStats.extracted, starMarketInvestorAllRecords.length);
  assert.equal(
    starMarketInvestorStats.extracted,
    starMarketInvestorStats.investors + starMarketInvestorStats.rejected,
  );
});

test("unverified candidates never expose prospectus contact fields", () => {
  assert.ok(
    starMarketInvestorRecords.every(
      (record) =>
        record.investor.reviewStatus === "verified" ||
        record.investor.publicContact === undefined,
    ),
  );
  assert.ok(
    starMarketInvestorRecords.every(
      (record) =>
        record.investor.contactStatus !== "prospectus-public" ||
        record.investor.reviewStatus === "verified",
    ),
  );
});
