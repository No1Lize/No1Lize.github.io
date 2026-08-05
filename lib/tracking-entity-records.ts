import {
  stableTrackingCaptureHash,
  type TrackingCaptureEntityType,
} from "@/lib/tracking-capture";

export const TRACKING_ENTITY_RECORDS_PATH = "config/tracking_entity_records.json";
export const TRACKING_ENTITY_RECORDS_CHANGED_EVENT =
  "vciq:tracking-entity-records-changed";

export const TRACKING_RESEARCH_REASON_OPTIONS = [
  "融资机会",
  "技术突破",
  "商业模式创新",
  "市场竞争",
  "IPO可能",
  "监管变化",
  "个人研究兴趣",
] as const;

export type TrackingResearchReason =
  (typeof TRACKING_RESEARCH_REASON_OPTIONS)[number];
export type TrackingEntityPriority = 0 | 1 | 2 | 3 | 4 | 5;

export type TrackingEntityAnalystNote = {
  id: string;
  body: string;
  createdAt: string;
  createdBy: string;
};

export type TrackingEntityResearchRecord = {
  entityId: string;
  entityType: TrackingCaptureEntityType;
  canonicalName: string;
  priority: TrackingEntityPriority;
  reasons: TrackingResearchReason[];
  thesis: string;
  notes: TrackingEntityAnalystNote[];
  createdAt: string;
  updatedAt: string;
  updatedBy: string;
};

export type TrackingEntityRecordManifest = {
  schemaVersion: 1;
  generatedAt: string;
  records: Record<string, TrackingEntityResearchRecord>;
};

export type UpdateTrackingEntityRecordInput = {
  entityId: string;
  entityType: TrackingCaptureEntityType;
  canonicalName: string;
  priority: number;
  reasons: string[];
  thesis: string;
  noteBody?: string;
  updatedAt: string;
  updatedBy: string;
};

const ENTITY_TYPES = new Set<TrackingCaptureEntityType>([
  "company",
  "person",
  "topic",
]);
const REASONS = new Set<string>(TRACKING_RESEARCH_REASON_OPTIONS);

function cleanText(value: unknown, limit = 1_200) {
  return String(value ?? "")
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, limit);
}

function cleanMultiline(value: unknown, limit = 4_000) {
  return String(value ?? "")
    .normalize("NFKC")
    .replace(/\r\n?/gu, "\n")
    .replace(/[ \t]+/gu, " ")
    .replace(/\n{3,}/gu, "\n\n")
    .trim()
    .slice(0, limit);
}

function normalizePriority(value: unknown): TrackingEntityPriority {
  const number = Math.round(Number(value));
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(5, number)) as TrackingEntityPriority;
}

function normalizeReasons(value: unknown): TrackingResearchReason[] {
  if (!Array.isArray(value)) return [];
  const result: TrackingResearchReason[] = [];
  for (const raw of value) {
    const reason = cleanText(raw, 80);
    if (!REASONS.has(reason) || result.includes(reason as TrackingResearchReason)) {
      continue;
    }
    result.push(reason as TrackingResearchReason);
  }
  return result;
}

function normalizeNote(value: unknown): TrackingEntityAnalystNote | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const body = cleanMultiline(row.body, 4_000);
  const createdAt = cleanText(row.createdAt, 80);
  const createdBy = cleanText(row.createdBy, 120);
  if (!body || !createdAt) return null;
  const id =
    cleanText(row.id, 180) ||
    `note-${stableTrackingCaptureHash(`${createdAt}|${createdBy}|${body}`)}`;
  return { id, body, createdAt, createdBy };
}

function normalizeRecord(
  key: string,
  value: unknown,
): TrackingEntityResearchRecord | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const entityType = ENTITY_TYPES.has(row.entityType as TrackingCaptureEntityType)
    ? (row.entityType as TrackingCaptureEntityType)
    : null;
  const canonicalName = cleanText(row.canonicalName, 240);
  const entityId = cleanText(row.entityId || key, 240);
  if (
    !entityType ||
    !canonicalName ||
    !entityId.startsWith(`${entityType}:`)
  ) {
    return null;
  }
  const notes = Array.isArray(row.notes)
    ? row.notes
        .map(normalizeNote)
        .filter((note): note is TrackingEntityAnalystNote => Boolean(note))
    : [];
  const uniqueNotes = notes.filter(
    (note, index) => notes.findIndex((candidate) => candidate.id === note.id) === index,
  );
  uniqueNotes.sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt),
  );
  return {
    entityId,
    entityType,
    canonicalName,
    priority: normalizePriority(row.priority),
    reasons: normalizeReasons(row.reasons),
    thesis: cleanMultiline(row.thesis, 2_000),
    notes: uniqueNotes.slice(0, 200),
    createdAt: cleanText(row.createdAt, 80),
    updatedAt: cleanText(row.updatedAt, 80),
    updatedBy: cleanText(row.updatedBy, 120),
  };
}

export function normalizeTrackingEntityRecordManifest(
  value: unknown,
): TrackingEntityRecordManifest {
  const payload = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  const rawRecords = payload.records && typeof payload.records === "object"
    ? (payload.records as Record<string, unknown>)
    : {};
  const records: Record<string, TrackingEntityResearchRecord> = {};
  for (const [key, raw] of Object.entries(rawRecords)) {
    const record = normalizeRecord(key, raw);
    if (!record) continue;
    records[record.entityId] = record;
  }
  return {
    schemaVersion: 1,
    generatedAt: cleanText(payload.generatedAt, 80),
    records: Object.fromEntries(
      Object.entries(records).sort(([left], [right]) => left.localeCompare(right)),
    ),
  };
}

export function trackingEntityPriorityLabel(priority: number) {
  if (priority >= 5) return "核心研究";
  if (priority >= 4) return "重点观察";
  if (priority >= 3) return "行业跟踪";
  if (priority >= 2) return "新闻关注";
  if (priority >= 1) return "资料收藏";
  return "未设置等级";
}

export function trackingEntityPriorityStars(priority: number) {
  const value = normalizePriority(priority);
  return `${"★".repeat(value)}${"☆".repeat(5 - value)}`;
}

export function updateTrackingEntityRecord(
  manifestValue: TrackingEntityRecordManifest,
  input: UpdateTrackingEntityRecordInput,
): TrackingEntityRecordManifest {
  const manifest = normalizeTrackingEntityRecordManifest(manifestValue);
  const entityType = ENTITY_TYPES.has(input.entityType)
    ? input.entityType
    : null;
  const entityId = cleanText(input.entityId, 240);
  const canonicalName = cleanText(input.canonicalName, 240);
  const updatedAt = cleanText(input.updatedAt, 80);
  const updatedBy = cleanText(input.updatedBy, 120);
  if (
    !entityType ||
    !entityId.startsWith(`${entityType}:`) ||
    !canonicalName ||
    !updatedAt ||
    !updatedBy
  ) {
    throw new Error("追踪对象研究记录缺少合法的实体、时间或管理员信息。");
  }

  const current = manifest.records[entityId];
  const noteBody = cleanMultiline(input.noteBody, 4_000);
  const notes = [...(current?.notes ?? [])];
  if (noteBody) {
    const id = `note-${stableTrackingCaptureHash(
      `${entityId}|${updatedAt}|${updatedBy}|${noteBody}`,
    )}`;
    if (!notes.some((note) => note.id === id)) {
      notes.unshift({ id, body: noteBody, createdAt: updatedAt, createdBy: updatedBy });
    }
  }

  const record: TrackingEntityResearchRecord = {
    entityId,
    entityType,
    canonicalName,
    priority: normalizePriority(input.priority),
    reasons: normalizeReasons(input.reasons),
    thesis: cleanMultiline(input.thesis, 2_000),
    notes: notes.slice(0, 200),
    createdAt: current?.createdAt || updatedAt,
    updatedAt,
    updatedBy,
  };

  return normalizeTrackingEntityRecordManifest({
    schemaVersion: 1,
    generatedAt: updatedAt,
    records: {
      ...manifest.records,
      [entityId]: record,
    },
  });
}
