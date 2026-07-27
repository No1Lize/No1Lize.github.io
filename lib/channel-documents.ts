import rawChannelDocuments from "@/public/data/channel_documents.json";
import { normalizeChannelUpdateDate } from "@/lib/channel-update-date";
import type { ChannelUpdateItem } from "@/lib/channel-updates";

export const CHANNEL_DOCUMENTS_PATH = "public/data/channel_documents.json";
export const CHANNEL_DOCUMENT_UPLOAD_ROOT = "public/data/uploads";
export const CHANNEL_DOCUMENT_MAX_BYTES = 25 * 1024 * 1024;
export const CHANNEL_DOCUMENT_SOURCE = "手动导入";

export const CHANNEL_DOCUMENT_CHANNELS = [
  "technology",
  "companies",
  "institutions",
  "reports",
  "people",
] as const;

export type ChannelDocumentChannel = (typeof CHANNEL_DOCUMENT_CHANNELS)[number];

export const CHANNEL_DOCUMENT_FILE_TYPES = [
  "pdf",
  "docx",
  "doc",
  "pptx",
  "ppt",
  "text",
  "image",
] as const;

export type ChannelDocumentFileType =
  (typeof CHANNEL_DOCUMENT_FILE_TYPES)[number];

export type ChannelDocumentRecord = {
  id: string;
  channel: ChannelDocumentChannel;
  title: string;
  summary: string;
  fileName: string;
  filePath: string;
  fileType: ChannelDocumentFileType;
  fileSize: number;
  pageCount?: number;
  textChars?: number;
  uploadedAt: string;
  uploadedBy?: string;
};

export type ChannelDocumentsPayload = {
  schemaVersion: 1;
  generatedAt: string;
  documents: ChannelDocumentRecord[];
};

const FILE_TYPE_LABELS: Record<ChannelDocumentFileType, string> = {
  pdf: "PDF文档",
  docx: "Word文档",
  doc: "Word文档",
  pptx: "PPT文档",
  ppt: "PPT文档",
  text: "文本文档",
  image: "图片文件",
};

const FALLBACK_SUMMARY = "已归档文件，未提取正文摘要。";
const MAX_TITLE_LENGTH = 200;
const MAX_SUMMARY_LENGTH = 600;

const channelSet = new Set<string>(CHANNEL_DOCUMENT_CHANNELS);
const fileTypeSet = new Set<string>(CHANNEL_DOCUMENT_FILE_TYPES);

export function channelDocumentTypeLabel(
  fileType: ChannelDocumentFileType,
): string {
  return FILE_TYPE_LABELS[fileType];
}

function asTrimmedString(value: unknown, maxLength: number): string {
  if (typeof value !== "string") return "";
  const trimmed = value.trim();
  return trimmed.length > maxLength
    ? `${trimmed.slice(0, maxLength - 1)}…`
    : trimmed;
}

function isValidUploadPath(filePath: string): boolean {
  if (!filePath.startsWith("data/uploads/")) return false;
  if (filePath.includes("..") || filePath.includes("\\")) return false;
  const segments = filePath.split("/");
  if (segments.length < 4) return false;
  if (!channelSet.has(segments[2])) return false;
  return segments.every((segment) => segment.length > 0);
}

function normalizeRecord(value: unknown): ChannelDocumentRecord | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const id = asTrimmedString(raw.id, 120);
  const channel = typeof raw.channel === "string" ? raw.channel : "";
  const title = asTrimmedString(raw.title, MAX_TITLE_LENGTH);
  const fileName = asTrimmedString(raw.fileName, 200);
  const filePath = typeof raw.filePath === "string" ? raw.filePath.trim() : "";
  const fileType = typeof raw.fileType === "string" ? raw.fileType : "";
  if (!id || !title || !filePath) return null;
  if (!channelSet.has(channel) || !fileTypeSet.has(fileType)) return null;
  if (!isValidUploadPath(filePath)) return null;

  const fileSize =
    typeof raw.fileSize === "number" && Number.isFinite(raw.fileSize)
      ? Math.max(0, Math.round(raw.fileSize))
      : 0;
  const pageCount =
    typeof raw.pageCount === "number" &&
    Number.isFinite(raw.pageCount) &&
    raw.pageCount > 0
      ? Math.round(raw.pageCount)
      : undefined;
  const textChars =
    typeof raw.textChars === "number" &&
    Number.isFinite(raw.textChars) &&
    raw.textChars > 0
      ? Math.round(raw.textChars)
      : undefined;
  const uploadedAtRaw =
    typeof raw.uploadedAt === "string" ? raw.uploadedAt.trim() : "";
  const uploadedAt = Number.isNaN(Date.parse(uploadedAtRaw))
    ? ""
    : uploadedAtRaw;
  const uploadedBy = asTrimmedString(raw.uploadedBy, 80) || undefined;

  return {
    id,
    channel: channel as ChannelDocumentChannel,
    title,
    summary: asTrimmedString(raw.summary, MAX_SUMMARY_LENGTH),
    fileName: fileName || title,
    filePath,
    fileType: fileType as ChannelDocumentFileType,
    fileSize,
    ...(pageCount ? { pageCount } : {}),
    ...(textChars ? { textChars } : {}),
    uploadedAt,
    ...(uploadedBy ? { uploadedBy } : {}),
  };
}

export function normalizeChannelDocuments(
  input: unknown,
): ChannelDocumentsPayload {
  const raw =
    input && typeof input === "object"
      ? (input as Record<string, unknown>)
      : {};
  const generatedAt =
    typeof raw.generatedAt === "string" &&
    !Number.isNaN(Date.parse(raw.generatedAt))
      ? raw.generatedAt
      : "";
  const documentsRaw = Array.isArray(raw.documents) ? raw.documents : [];
  const seen = new Set<string>();
  const documents: ChannelDocumentRecord[] = [];
  for (const value of documentsRaw) {
    const record = normalizeRecord(value);
    if (!record || seen.has(record.id)) continue;
    seen.add(record.id);
    documents.push(record);
  }
  return { schemaVersion: 1, generatedAt, documents };
}

export function channelDocumentToUpdateItem(
  record: ChannelDocumentRecord,
  fallbackGeneratedAt: string,
): ChannelUpdateItem {
  const normalizedDate = normalizeChannelUpdateDate(
    record.uploadedAt,
    fallbackGeneratedAt,
  );
  const label = channelDocumentTypeLabel(record.fileType);
  const context = record.pageCount
    ? `${record.fileName} · ${record.pageCount} 页`
    : record.fileName;
  return {
    id: record.id,
    title: record.title,
    summary: record.summary || FALLBACK_SUMMARY,
    // Land on the in-site reader (summary on top, inline preview, explicit
    // download button) instead of the raw file, which browsers may download.
    href: `/documents/${record.id}/`,
    source: CHANNEL_DOCUMENT_SOURCE,
    label,
    context,
    date: normalizedDate.displayDate,
    dateOriginal: normalizedDate.originalDate,
    datePrecision: normalizedDate.precision,
    sortAt: normalizedDate.sortAt,
    keywords: [label],
  };
}

const channelDocumentsPayload = normalizeChannelDocuments(rawChannelDocuments);

export function getAllChannelDocuments(): ChannelDocumentRecord[] {
  return channelDocumentsPayload.documents;
}

export function getChannelDocumentById(
  id: string,
): ChannelDocumentRecord | undefined {
  return channelDocumentsPayload.documents.find((record) => record.id === id);
}

export function getChannelDocumentUpdateItems(
  channel: ChannelDocumentChannel,
): ChannelUpdateItem[] {
  return channelDocumentsPayload.documents
    .filter((record) => record.channel === channel)
    .map((record) =>
      channelDocumentToUpdateItem(record, channelDocumentsPayload.generatedAt),
    );
}

export function detectChannelDocumentFileType(
  fileName: string,
  mimeType?: string,
): ChannelDocumentFileType | null {
  const extension = fileName.toLowerCase().split(".").pop() ?? "";
  if (extension === "pdf" || mimeType === "application/pdf") return "pdf";
  if (
    extension === "docx" ||
    mimeType ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  ) {
    return "docx";
  }
  if (extension === "doc" || mimeType === "application/msword") return "doc";
  if (
    extension === "pptx" ||
    mimeType ===
      "application/vnd.openxmlformats-officedocument.presentationml.presentation"
  ) {
    return "pptx";
  }
  if (extension === "ppt" || mimeType === "application/vnd.ms-powerpoint") {
    return "ppt";
  }
  if (
    ["txt", "md", "markdown", "csv"].includes(extension) ||
    mimeType?.startsWith("text/")
  ) {
    return "text";
  }
  if (
    ["png", "jpg", "jpeg", "webp", "gif"].includes(extension) ||
    mimeType?.startsWith("image/")
  ) {
    return "image";
  }
  return null;
}

export function safeChannelDocumentFileName(fileName: string): string {
  const normalized = fileName.normalize("NFC").trim();
  const lastDot = normalized.lastIndexOf(".");
  const hasExtension =
    lastDot > 0 &&
    lastDot < normalized.length - 1 &&
    /^[a-zA-Z0-9]{1,10}$/.test(normalized.slice(lastDot + 1));
  const base = hasExtension ? normalized.slice(0, lastDot) : normalized;
  const extension = hasExtension
    ? `.${normalized.slice(lastDot + 1).toLowerCase()}`
    : "";
  const cleanedBase = base
    .replace(/[\\/:*?"<>|#%&{}$!'@+`=[\]^~()\s、，。；：？！（）【】]+/gu, "-")
    .replace(/\.+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[-_.]+|[-_.]+$/g, "");
  const safeBase = (cleanedBase || "document").slice(0, 80);
  return `${safeBase}${extension}`;
}

export function createChannelDocumentId(
  now: Date = new Date(),
  randomValue: number = Math.random(),
): string {
  const stamp = now
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\..+$/, "")
    .replace("T", "-");
  const random = Math.floor(randomValue * 36 ** 4)
    .toString(36)
    .padStart(4, "0");
  return `doc-${stamp}-${random}`;
}

export function buildChannelDocumentPath(
  channel: ChannelDocumentChannel,
  id: string,
  safeFileName: string,
): string {
  return `data/uploads/${channel}/${id}-${safeFileName}`;
}
