import rawCandidates from "@/public/data/company_candidates.json";

export type CompanyCandidateStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "merged"
  | "published";

export type CompanyCandidate = {
  id: string;
  decisionKey: string;
  name: string;
  aliases: string[];
  region: string;
  sector: string;
  score: number;
  status: CompanyCandidateStatus;
  reasons: string[];
  firstSeenAt: string;
  lastSeenAt: string;
  articleCount: number;
  sourceCount: number;
  sourceHosts: string[];
  sourceArticleIds: string[];
  sourceUrls: string[];
  eventTypes: string[];
  note: string;
  mergedSlug: string;
  decidedAt: string;
};

export type CompanyCandidateSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  candidateCount: number;
  pendingCount: number;
  acceptedCount: number;
  rejectedCount: number;
  mergedCount: number;
  publishedCount: number;
  candidates: CompanyCandidate[];
};

const statuses = new Set<CompanyCandidateStatus>([
  "pending",
  "accepted",
  "rejected",
  "merged",
  "published",
]);

function text(value: unknown, limit = 500) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function list(value: unknown, limit = 20) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map((item) => text(item, 1000)).filter(Boolean))].slice(0, limit);
}

function safeUrl(value: unknown) {
  const url = text(value, 1200);
  return /^https?:\/\//iu.test(url) ? url : "";
}

export function normalizeCompanyCandidateSnapshot(value: unknown): CompanyCandidateSnapshot {
  const payload = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const rows = Array.isArray(payload.candidates) ? payload.candidates : [];
  const candidates = rows.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const row = raw as Record<string, unknown>;
    const id = text(row.id, 160);
    const name = text(row.name, 120);
    const rawStatus = text(row.status, 20) as CompanyCandidateStatus;
    if (!id || !name || !statuses.has(rawStatus)) return [];
    return [{
      id,
      decisionKey: text(row.decisionKey, 160),
      name,
      aliases: list(row.aliases, 8),
      region: text(row.region, 40) || "全球",
      sector: text(row.sector, 100) || "待分类",
      score: Math.max(0, Math.min(100, Number(row.score) || 0)),
      status: rawStatus,
      reasons: list(row.reasons, 6),
      firstSeenAt: text(row.firstSeenAt, 60),
      lastSeenAt: text(row.lastSeenAt, 60),
      articleCount: Math.max(0, Number(row.articleCount) || 0),
      sourceCount: Math.max(0, Number(row.sourceCount) || 0),
      sourceHosts: list(row.sourceHosts, 10),
      sourceArticleIds: list(row.sourceArticleIds, 20),
      sourceUrls: list(row.sourceUrls, 10).map(safeUrl).filter(Boolean),
      eventTypes: list(row.eventTypes, 12),
      note: text(row.note, 300),
      mergedSlug: text(row.mergedSlug, 100),
      decidedAt: text(row.decidedAt, 60),
    } satisfies CompanyCandidate];
  });

  return {
    schemaVersion: Math.max(1, Number(payload.schemaVersion) || 1),
    generatedAt: text(payload.generatedAt, 60),
    candidateCount: candidates.length,
    pendingCount: candidates.filter((item) => item.status === "pending").length,
    acceptedCount: candidates.filter((item) => item.status === "accepted").length,
    rejectedCount: candidates.filter((item) => item.status === "rejected").length,
    mergedCount: candidates.filter((item) => item.status === "merged").length,
    publishedCount: candidates.filter((item) => item.status === "published").length,
    candidates,
  };
}

export const companyCandidateSnapshot = normalizeCompanyCandidateSnapshot(rawCandidates);
export const pendingCompanyCandidates = companyCandidateSnapshot.candidates
  .filter((candidate) => candidate.status === "pending")
  .sort((left, right) => right.score - left.score || right.lastSeenAt.localeCompare(left.lastSeenAt));
