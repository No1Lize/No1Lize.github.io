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

export type CompanyProfileRefreshQueue = {
  generatedAt: string;
  lookbackDays: number;
  selectionLimit: number;
  pendingCount: number;
  selectedCount: number;
  selectedSlugs: string[];
  lastProcessedAt: string;
  entries: CompanyProfileRefreshEntry[];
};

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function asString(value: unknown, limit = 2_000): string {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function asNonNegativeInteger(value: unknown, fallback = 0): number {
  return Math.max(0, Math.trunc(asNumber(value, fallback)));
}

function asStringArray(value: unknown, limit = 100): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    const text = asString(item, 500);
    if (!text || seen.has(text)) continue;
    result.push(text);
    seen.add(text);
    if (result.length >= limit) break;
  }
  return result;
}

function isPublicHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function normalizeEventTypes(value: unknown): Record<string, number> {
  const result: Record<string, number> = {};
  for (const [rawKey, rawCount] of Object.entries(asRecord(value))) {
    const key = asString(rawKey, 120);
    const count = asNonNegativeInteger(rawCount);
    if (!key || count <= 0) continue;
    result[key] = count;
  }
  return result;
}

function normalizeEvidence(value: unknown): CompanyProfileRefreshEvidence[] {
  if (!Array.isArray(value)) return [];
  const result: CompanyProfileRefreshEvidence[] = [];
  const seen = new Set<string>();
  for (const rawItem of value) {
    const item = asRecord(rawItem);
    const fingerprint = asString(item.fingerprint, 240);
    const sourceUrl = asString(item.sourceUrl, 2_000);
    if (!fingerprint || seen.has(fingerprint) || !isPublicHttpUrl(sourceUrl)) continue;
    result.push({
      fingerprint,
      articleId: asString(item.articleId, 300),
      title: asString(item.title, 500),
      eventType: asString(item.eventType, 120),
      publishedAt: asString(item.publishedAt, 80),
      importance: asNonNegativeInteger(item.importance),
      priority: asNonNegativeInteger(item.priority),
      sourceName: asString(item.sourceName, 240),
      sourceUrl,
      sourceLevel: asString(item.sourceLevel, 80),
    });
    seen.add(fingerprint);
    if (result.length >= 50) break;
  }
  return result;
}

function normalizeEntry(value: unknown): CompanyProfileRefreshEntry | null {
  const entry = asRecord(value);
  const companySlug = asString(entry.companySlug, 120);
  const companyName = asString(entry.companyName, 240);
  const priority = asNonNegativeInteger(entry.priority);
  if (!companySlug || !companyName || priority <= 0) return null;

  return {
    companySlug,
    companyName,
    priority,
    status: entry.status === "selected" ? "selected" : "pending",
    eventCount: asNonNegativeInteger(entry.eventCount),
    sourceCount: asNonNegativeInteger(entry.sourceCount),
    eventTypes: normalizeEventTypes(entry.eventTypes),
    newestPublishedAt: asString(entry.newestPublishedAt, 80),
    reasons: asStringArray(entry.reasons, 30),
    eventFingerprints: asStringArray(entry.eventFingerprints, 100),
    evidence: normalizeEvidence(entry.evidence),
  };
}

export function normalizeCompanyProfileRefreshQueue(
  value: unknown,
): CompanyProfileRefreshQueue {
  const snapshot = asRecord(value);
  const selectedSlugs = asStringArray(snapshot.selectedSlugs, 10);
  const entries = Array.isArray(snapshot.entries)
    ? snapshot.entries
        .map(normalizeEntry)
        .filter((entry): entry is CompanyProfileRefreshEntry => entry !== null)
        .slice(0, 100)
    : [];

  return {
    generatedAt: asString(snapshot.generatedAt, 80),
    lookbackDays: Math.max(1, asNonNegativeInteger(snapshot.lookbackDays, 7)),
    selectionLimit: Math.min(
      10,
      asNonNegativeInteger(snapshot.selectionLimit, 10),
    ),
    pendingCount: asNonNegativeInteger(snapshot.pendingCount),
    selectedCount: selectedSlugs.length,
    selectedSlugs,
    lastProcessedAt: asString(snapshot.lastProcessedAt, 80),
    entries,
  };
}

export const companyProfileRefreshQueue =
  normalizeCompanyProfileRefreshQueue(rawQueue);

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
