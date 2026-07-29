export const HOTNESS_STORAGE_KEY = "vciq:hotness:v1";
export const HOTNESS_CHANGED_EVENT = "vciq:hotness-changed";
export const HOTNESS_SCHEMA_VERSION = 1;

export const HOTNESS_WEIGHTS = {
  open: 1,
  favorite: 5,
  share: 8,
} as const;

export type HotnessInput = {
  id?: string;
  href: string;
  title: string;
  summary?: string;
  publishedAt?: string;
  importance?: number;
  sourceName?: string;
  channelLabel?: string;
};

export type HotnessItem = {
  key: string;
  id: string;
  href: string;
  title: string;
  summary: string;
  publishedAt?: string;
  importance?: number;
  sourceName?: string;
  channelLabel?: string;
  opens: number;
  favorite: boolean;
  shares: number;
  firstSeenAt: string;
  updatedAt: string;
  lastOpenedAt?: string;
  lastSharedAt?: string;
};

type HotnessPayload = {
  schemaVersion: 1;
  items: HotnessItem[];
};

const MAX_ITEMS = 500;
const TRACKING_PARAMETERS = new Set([
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "ref",
  "source",
  "spm",
]);

function cleanText(value: unknown, maxLength: number): string {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function safeCount(value: unknown): number {
  const count = typeof value === "number" ? value : Number(value);
  return Number.isFinite(count) ? Math.max(0, Math.min(1_000_000, Math.floor(count))) : 0;
}

function safeTimestamp(value: unknown, fallback = ""): string {
  const text = cleanText(value, 40);
  return text && !Number.isNaN(Date.parse(text)) ? text : fallback;
}

function safePublishedAt(value: unknown): string | undefined {
  const text = cleanText(value, 20);
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : undefined;
}

function safeImportance(value: unknown): number | undefined {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : undefined;
}

export function canonicalHotnessKey(value: string): string {
  const raw = cleanText(value, 2000);
  if (!raw) return "";

  try {
    let url = new URL(raw, "https://vciq.local");
    if (url.hostname === "vciq.local" && (url.pathname === "/read" || url.pathname === "/read/")) {
      const original = url.searchParams.get("url");
      if (original) url = new URL(original);
    }

    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (TRACKING_PARAMETERS.has(key.toLocaleLowerCase("en-US"))) {
        url.searchParams.delete(key);
      }
    }
    url.searchParams.sort();
    url.pathname = url.pathname.replace(/\/+$/, "") || "/";

    if (url.hostname === "vciq.local") {
      return `${url.pathname}${url.search}`;
    }
    return url.href;
  } catch {
    return "";
  }
}

function normalizeInput(input: HotnessInput, now: string): HotnessItem | null {
  const href = cleanText(input.href, 2000);
  const key = canonicalHotnessKey(href);
  const title = cleanText(input.title, 240);
  if (!key || !title) return null;

  const publishedAt = safePublishedAt(input.publishedAt);
  const importance = safeImportance(input.importance);
  const sourceName = cleanText(input.sourceName, 120);
  const channelLabel = cleanText(input.channelLabel, 40);

  return {
    key,
    id: cleanText(input.id, 180) || key,
    href,
    title,
    summary: cleanText(input.summary, 1200),
    ...(publishedAt ? { publishedAt } : {}),
    ...(importance !== undefined ? { importance } : {}),
    ...(sourceName ? { sourceName } : {}),
    ...(channelLabel ? { channelLabel } : {}),
    opens: 0,
    favorite: false,
    shares: 0,
    firstSeenAt: now,
    updatedAt: now,
  };
}

function normalizeStoredItem(value: unknown): HotnessItem | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const now = new Date().toISOString();
  const base = normalizeInput(
    {
      id: cleanText(raw.id, 180),
      href: cleanText(raw.href, 2000),
      title: cleanText(raw.title, 240),
      summary: cleanText(raw.summary, 1200),
      publishedAt: cleanText(raw.publishedAt, 20),
      importance: safeImportance(raw.importance),
      sourceName: cleanText(raw.sourceName, 120),
      channelLabel: cleanText(raw.channelLabel, 40),
    },
    now,
  );
  if (!base) return null;

  const firstSeenAt = safeTimestamp(raw.firstSeenAt, now);
  const updatedAt = safeTimestamp(raw.updatedAt, firstSeenAt);
  const lastOpenedAt = safeTimestamp(raw.lastOpenedAt);
  const lastSharedAt = safeTimestamp(raw.lastSharedAt);

  return {
    ...base,
    key: canonicalHotnessKey(cleanText(raw.key, 2000)) || base.key,
    opens: safeCount(raw.opens),
    favorite: raw.favorite === true,
    shares: safeCount(raw.shares),
    firstSeenAt,
    updatedAt,
    ...(lastOpenedAt ? { lastOpenedAt } : {}),
    ...(lastSharedAt ? { lastSharedAt } : {}),
  };
}

export function parseHotnessItems(value: string | null): HotnessItem[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    const rawItems = Array.isArray(parsed)
      ? parsed
      : parsed && typeof parsed === "object" && Array.isArray((parsed as Record<string, unknown>).items)
        ? ((parsed as Record<string, unknown>).items as unknown[])
        : [];
    const seen = new Set<string>();
    const items: HotnessItem[] = [];
    for (const raw of rawItems) {
      const item = normalizeStoredItem(raw);
      if (!item || seen.has(item.key)) continue;
      seen.add(item.key);
      items.push(item);
      if (items.length >= MAX_ITEMS) break;
    }
    return items.sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  } catch {
    return [];
  }
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readHotnessItems(): HotnessItem[] {
  const storage = browserStorage();
  return storage ? parseHotnessItems(storage.getItem(HOTNESS_STORAGE_KEY)) : [];
}

function writeHotnessItems(items: HotnessItem[]): void {
  const storage = browserStorage();
  if (!storage) return;
  const payload: HotnessPayload = {
    schemaVersion: HOTNESS_SCHEMA_VERSION,
    items: items
      .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
      .slice(0, MAX_ITEMS),
  };
  storage.setItem(HOTNESS_STORAGE_KEY, JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent(HOTNESS_CHANGED_EVENT));
}

function updateItem(
  input: HotnessInput,
  mutate: (item: HotnessItem, now: string) => HotnessItem,
): HotnessItem | null {
  const now = new Date().toISOString();
  const incoming = normalizeInput(input, now);
  if (!incoming) return null;
  const current = readHotnessItems();
  const existing = current.find((item) => item.key === incoming.key);
  const merged: HotnessItem = existing
    ? {
        ...existing,
        ...incoming,
        opens: existing.opens,
        favorite: existing.favorite,
        shares: existing.shares,
        firstSeenAt: existing.firstSeenAt,
        updatedAt: now,
        ...(existing.lastOpenedAt ? { lastOpenedAt: existing.lastOpenedAt } : {}),
        ...(existing.lastSharedAt ? { lastSharedAt: existing.lastSharedAt } : {}),
      }
    : incoming;
  const next = mutate(merged, now);
  writeHotnessItems([next, ...current.filter((item) => item.key !== next.key)]);
  return next;
}

export function recordArticleOpen(input: HotnessInput): HotnessItem | null {
  return updateItem(input, (item, now) => ({
    ...item,
    opens: item.opens + 1,
    lastOpenedAt: now,
    updatedAt: now,
  }));
}

export function setArticleFavorite(input: HotnessInput, favorite: boolean): HotnessItem | null {
  return updateItem(input, (item, now) => ({
    ...item,
    favorite,
    updatedAt: now,
  }));
}

export function recordArticleShare(input: HotnessInput): HotnessItem | null {
  return updateItem(input, (item, now) => ({
    ...item,
    shares: item.shares + 1,
    lastSharedAt: now,
    updatedAt: now,
  }));
}

export function calculateHotnessScore(
  metrics: Pick<HotnessItem, "opens" | "favorite" | "shares">,
): number {
  return (
    metrics.opens * HOTNESS_WEIGHTS.open +
    (metrics.favorite ? HOTNESS_WEIGHTS.favorite : 0) +
    metrics.shares * HOTNESS_WEIGHTS.share
  );
}

export function metricsByHref(items: HotnessItem[]): Map<string, HotnessItem> {
  return new Map(items.map((item) => [item.key, item]));
}
