import type {
  CompanyCandidate,
  CompanyCandidateStatus,
} from "@/lib/company-candidate-data";
import type { CompanyCandidateOnboarding } from "@/lib/company-candidate-onboarding";

export type CompanyCandidateDecision = {
  status: CompanyCandidateStatus;
  note: string;
  mergedSlug: string;
  decidedAt: string;
  reviewedBy: string;
  onboarding?: CompanyCandidateOnboarding;
};

export type CompanyCandidateDecisionManifest = {
  schemaVersion: number;
  decisions: Record<string, CompanyCandidateDecision>;
};

export type ReviewedCompanyCandidate = CompanyCandidate & {
  reviewedBy: string;
  onboarding?: CompanyCandidateOnboarding;
};

export type CompanyCandidateReviewCounts = Record<CompanyCandidateStatus, number>;

const VALID_STATUSES = new Set<CompanyCandidateStatus>([
  "pending",
  "accepted",
  "rejected",
  "merged",
  "published",
]);

function text(value: unknown, limit: number) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function list(value: unknown, limit: number) {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = text(raw, 500);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function decisionKey(value: unknown) {
  return text(value, 160).normalize("NFKC").toLocaleLowerCase("zh-CN");
}

function onboarding(value: unknown): CompanyCandidateOnboarding | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const profile = row.profile && typeof row.profile === "object"
    ? (row.profile as Record<string, unknown>)
    : {};
  const rawStatus = text(row.status, 40) as CompanyCandidateOnboarding["status"];
  const statuses = new Set<CompanyCandidateOnboarding["status"]>([
    "awaiting_profile",
    "requested",
    "published",
    "failed",
    "merged",
  ]);
  return {
    status: statuses.has(rawStatus) ? rawStatus : "awaiting_profile",
    mode: row.mode === "merge" ? "merge" : "create",
    profile: {
      slug: text(profile.slug, 120).toLocaleLowerCase("en-US"),
      name: text(profile.name, 240),
      englishName: text(profile.englishName, 240),
      region: text(profile.region, 80),
      sector: text(profile.sector, 120),
      stage: text(profile.stage, 80),
      status: profile.status === "已上市" ? "已上市" : "运营中",
      founded: text(profile.founded, 40),
      headquarters: text(profile.headquarters, 160),
      summary: text(profile.summary, 1_200),
      product: text(profile.product, 1_200),
      homepage: text(profile.homepage, 2_000),
      newsUrls: list(profile.newsUrls, 20),
      aliases: list(profile.aliases, 30),
      confidence: Math.max(0.5, Math.min(1, Number(profile.confidence) || 0.9)),
    },
    evidenceFingerprint: text(row.evidenceFingerprint, 10_000),
    requestedAt: text(row.requestedAt, 80),
    requestedBy: text(row.requestedBy, 120),
    publishedAt: text(row.publishedAt, 80),
    publishedSlug: text(row.publishedSlug, 120),
    error: text(row.error, 1_000),
  };
}

export function normalizeCompanyCandidateDecisionManifest(
  value: unknown,
): CompanyCandidateDecisionManifest {
  const payload = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  const rawDecisions = payload.decisions && typeof payload.decisions === "object"
    ? (payload.decisions as Record<string, unknown>)
    : {};
  const decisions: Record<string, CompanyCandidateDecision> = {};

  for (const [rawKey, rawDecision] of Object.entries(rawDecisions)) {
    if (!rawDecision || typeof rawDecision !== "object") continue;
    const row = rawDecision as Record<string, unknown>;
    const key = decisionKey(rawKey);
    const status = text(row.status, 20) as CompanyCandidateStatus;
    if (!key || !VALID_STATUSES.has(status) || status === "pending") continue;
    const normalizedOnboarding = onboarding(row.onboarding);
    decisions[key] = {
      status,
      note: text(row.note, 500),
      mergedSlug: text(row.mergedSlug, 100),
      decidedAt: text(row.decidedAt, 60),
      reviewedBy: text(row.reviewedBy, 100),
      onboarding: normalizedOnboarding,
    };
  }

  return {
    schemaVersion: Math.max(1, Number(payload.schemaVersion) || 1),
    decisions,
  };
}

export function decisionForCompanyCandidate(
  candidate: Pick<CompanyCandidate, "decisionKey">,
  manifest: CompanyCandidateDecisionManifest,
) {
  return manifest.decisions[decisionKey(candidate.decisionKey)];
}

export function applyCompanyCandidateDecisions(
  candidates: CompanyCandidate[],
  manifest: CompanyCandidateDecisionManifest,
): ReviewedCompanyCandidate[] {
  return candidates.map((candidate) => {
    const decision = decisionForCompanyCandidate(candidate, manifest);
    if (!decision) return { ...candidate, reviewedBy: "" };
    return {
      ...candidate,
      status: decision.status,
      note: decision.note,
      mergedSlug: decision.mergedSlug,
      decidedAt: decision.decidedAt,
      reviewedBy: decision.reviewedBy,
      onboarding: decision.onboarding,
    };
  });
}

export function countCompanyCandidateReviews(
  candidates: Pick<CompanyCandidate, "status">[],
): CompanyCandidateReviewCounts {
  const counts: CompanyCandidateReviewCounts = {
    pending: 0,
    accepted: 0,
    rejected: 0,
    merged: 0,
    published: 0,
  };
  for (const candidate of candidates) counts[candidate.status] += 1;
  return counts;
}

export function setCompanyCandidateDecision(
  manifest: CompanyCandidateDecisionManifest,
  candidateKey: string,
  decision: CompanyCandidateDecision,
): CompanyCandidateDecisionManifest {
  const key = decisionKey(candidateKey);
  if (!key) throw new Error("候选审核键不能为空。");
  const decisions = { ...manifest.decisions };
  if (decision.status === "pending") delete decisions[key];
  else {
    decisions[key] = {
      status: decision.status,
      note: text(decision.note, 500),
      mergedSlug: text(decision.mergedSlug, 100),
      decidedAt: text(decision.decidedAt, 60),
      reviewedBy: text(decision.reviewedBy, 100),
      onboarding: onboarding(decision.onboarding),
    };
  }
  return {
    schemaVersion: Math.max(1, manifest.schemaVersion || 1),
    decisions,
  };
}

export function validateCompanyCandidateDecision({
  status,
  note,
  mergedSlug,
}: Pick<CompanyCandidateDecision, "status" | "note" | "mergedSlug">) {
  if (!VALID_STATUSES.has(status) || status === "published") {
    return { valid: false, message: "未知或不可手工设置的审核状态。" };
  }
  if (status === "pending") return { valid: true, message: "" };

  const cleanNote = text(note, 500);
  if (cleanNote.length < 4) {
    return { valid: false, message: "请填写至少 4 个字符的审核说明。" };
  }
  if (status === "merged") {
    const slug = text(mergedSlug, 100);
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(slug)) {
      return {
        valid: false,
        message: "合并状态必须填写已有公司档案 slug，例如 shopify。",
      };
    }
  }
  return { valid: true, message: "" };
}

export function companyCandidateEvidenceFingerprint(
  candidate: Pick<
    CompanyCandidate,
    | "decisionKey"
    | "score"
    | "sourceArticleIds"
    | "sourceUrls"
    | "articleCount"
    | "sourceCount"
  >,
) {
  return JSON.stringify({
    decisionKey: decisionKey(candidate.decisionKey),
    score: candidate.score,
    articleCount: candidate.articleCount,
    sourceCount: candidate.sourceCount,
    sourceArticleIds: [...candidate.sourceArticleIds].sort(),
    sourceUrls: [...candidate.sourceUrls].sort(),
  });
}
