import rawQueue from "@/public/data/company_profile_refresh_queue.json";

export type CompanyProfileRefreshEvidence = {
  fingerprint: string;
  articleId: string;
  title: string;
  eventType: string;
  publishedAt: string;
  importance: number;
  priority: number;
  sourceName: string;
  sourceUrl: string;
  sourceLevel: string;
};

export type CompanyProfileRefreshEntry = {
  companySlug: string;
  companyName: string;
  priority: number;
  status: "selected" | "pending";
  eventCount: number;
  sourceCount: number;
  eventTypes: Record<string, number>;
  newestPublishedAt: string;
  reasons: string[];
  eventFingerprints: string[];
  evidence: CompanyProfileRefreshEvidence[];
};

type QueueSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  lookbackDays: number;
  selectionLimit: number;
  pendingCount: number;
  selectedCount: number;
  selectedSlugs: string[];
  lastProcessedAt: string;
  entries: CompanyProfileRefreshEntry[];
};

const snapshot = rawQueue as QueueSnapshot;

export const companyProfileRefreshQueue = {
  generatedAt: String(snapshot.generatedAt ?? ""),
  lookbackDays: Math.max(1, Number(snapshot.lookbackDays) || 7),
  selectionLimit: Math.max(0, Math.min(10, Number(snapshot.selectionLimit) || 10)),
  pendingCount: Math.max(0, Number(snapshot.pendingCount) || 0),
  selectedCount: Math.max(0, Number(snapshot.selectedCount) || 0),
  selectedSlugs: Array.isArray(snapshot.selectedSlugs) ? snapshot.selectedSlugs : [],
  lastProcessedAt: String(snapshot.lastProcessedAt ?? ""),
  entries: Array.isArray(snapshot.entries) ? snapshot.entries : [],
};

export function formatCompanyProfileQueueTime(value: string) {
  const parsed = new Date(value);
  if (!value || Number.isNaN(parsed.getTime())) return "尚无";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Taipei",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}
