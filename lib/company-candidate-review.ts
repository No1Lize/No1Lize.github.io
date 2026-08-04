import type {
  CompanyCandidate,
  CompanyCandidateStatus,
} from "@/lib/company-candidate-data";

export type CompanyCandidateDecision = {
  status: CompanyCandidateStatus;
  note: string;
  mergedSlug: string;
  decidedAt: string;
  reviewedBy: string;
};

export type CompanyCandidateDecisionManifest = {
  schemaVersion: number;
  decisions: Record<string, CompanyCandidateDecision>;
};

export type ReviewedCompanyCandidate = CompanyCandidate & {
  reviewedBy: string;
};

export type CompanyCandidateReviewCounts = Record<CompanyCandidateStatus, number>;

const VALID_STATUSES = new Set<CompanyCandidateStatus>([
  "pending",
  "accepted",
  "rejected",
  "merged",
]);

function text(value: unknown, limit: number) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function decisionKey(value: unknown) {
  return text(value, 160).normalize("NFKC").toLocaleLowerCase("zh-CN");
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
    decisions[key] = {
      status,
      note: text(row.note, 500),
      mergedSlug: text(row.mergedSlug, 100),
      decidedAt: text(row.decidedAt, 60),
      reviewedBy: text(row.reviewedBy, 100),
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
  if (!VALID_STATUSES.has(status)) {
    return { valid: false, message: "未知审核状态。" };
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
