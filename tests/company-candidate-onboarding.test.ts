import assert from "node:assert/strict";
import test from "node:test";

import {
  emptyCompanyOnboardingProfile,
  requestCompanyCandidateOnboarding,
  validateCompanyOnboardingProfile,
} from "../lib/company-candidate-onboarding";
import {
  companyCandidateEvidenceFingerprint,
  normalizeCompanyCandidateDecisionManifest,
} from "../lib/company-candidate-review";
import type { CompanyCandidate } from "../lib/company-candidate-data";

function candidate(overrides: Partial<CompanyCandidate> = {}): CompanyCandidate {
  return {
    id: "candidate-sample",
    decisionKey: "sample",
    name: "Sample",
    aliases: ["Sample"],
    region: "美国",
    sector: "AI / AGI",
    score: 70,
    status: "accepted",
    reasons: ["结构化证据"],
    firstSeenAt: "2026-08-01T00:00:00Z",
    lastSeenAt: "2026-08-04T00:00:00Z",
    articleCount: 3,
    sourceCount: 2,
    sourceHosts: ["example.com"],
    sourceArticleIds: ["a2", "a1"],
    sourceUrls: ["https://example.com/about", "https://example.com/news"],
    eventTypes: ["产品发布"],
    note: "",
    mergedSlug: "",
    decidedAt: "",
    ...overrides,
  };
}

test("default onboarding profile uses candidate identity without fabricating summary", () => {
  const profile = emptyCompanyOnboardingProfile(candidate());
  assert.equal(profile.name, "Sample");
  assert.equal(profile.region, "美国");
  assert.equal(profile.homepage, "https://example.com/");
  assert.equal(profile.summary, "");
});

test("onboarding validation requires a canonical profile", () => {
  const item = candidate();
  const profile = emptyCompanyOnboardingProfile(item);
  const result = validateCompanyOnboardingProfile(profile, item);
  assert.equal(result.valid, false);
  assert.match(result.message, /公司简介/u);
});

test("person-only candidates cannot publish under a person name", () => {
  const item = candidate({
    decisionKey: "某位创始人",
    name: "某位创始人",
    eventTypes: ["人物观点"],
  });
  const profile = {
    ...emptyCompanyOnboardingProfile(item),
    slug: "founder",
    name: "某位创始人",
    region: "美国",
    sector: "AI / AGI",
    summary: "这是一个长度足够但错误地使用人物姓名作为公司名称的档案简介。",
    product: "人工智能产品和服务。",
    homepage: "https://example.com/",
  };
  const result = validateCompanyOnboardingProfile(profile, item);
  assert.equal(result.valid, false);
  assert.match(result.message, /人物姓名/u);
});

test("request stores reviewed evidence fingerprint and profile", () => {
  const item = candidate();
  const manifest = normalizeCompanyCandidateDecisionManifest({
    schemaVersion: 1,
    decisions: {
      sample: {
        status: "accepted",
        note: "确认这是独立公司。",
        mergedSlug: "",
        decidedAt: "2026-08-05T00:00:00Z",
        reviewedBy: "VCIQ",
      },
    },
  });
  const profile = {
    ...emptyCompanyOnboardingProfile(item),
    slug: "sample",
    summary: "为企业客户提供可审计的人工智能软件和数据基础设施服务。",
    product: "企业人工智能平台与数据工具。",
  };
  const next = requestCompanyCandidateOnboarding({
    manifest,
    candidate: item,
    profile,
    requestedBy: "VCIQ",
    requestedAt: "2026-08-05T01:00:00Z",
  });
  const request = next.decisions.sample.onboarding;
  assert.ok(request);
  assert.equal(request.status, "requested");
  assert.equal(request.profile.slug, "sample");
  assert.equal(request.evidenceFingerprint, companyCandidateEvidenceFingerprint(item));
});

test("published decision state is retained by manifest normalization", () => {
  const manifest = normalizeCompanyCandidateDecisionManifest({
    decisions: {
      sample: {
        status: "published",
        note: "已发布",
        mergedSlug: "sample",
        decidedAt: "2026-08-05T00:00:00Z",
        reviewedBy: "VCIQ",
        onboarding: {
          status: "published",
          mode: "create",
          profile: {
            slug: "sample",
            name: "Sample",
            homepage: "https://example.com/",
          },
          publishedSlug: "sample",
        },
      },
    },
  });
  assert.equal(manifest.decisions.sample.status, "published");
  assert.equal(manifest.decisions.sample.onboarding?.publishedSlug, "sample");
});
