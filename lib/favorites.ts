export const FAVORITES_STORAGE_KEY = "vciq:favorites:v1";
export const FAVORITES_CHANGED_EVENT = "vciq:favorites-changed";
export const FAVORITES_SCHEMA_VERSION = 1;

export type FavoriteChannel =
  | "technology"
  | "companies"
  | "institutions"
  | "ipo"
  | "reports"
  | "people";

export type FavoriteSource = {
  name: string;
  url: string;
  level?: string;
};

export type FavoriteInput = {
  id: string;
  href: string;
  title: string;
  summary: string;
  channel: FavoriteChannel;
  channelLabel: string;
  keywords?: string[];
  sectors?: string[];
  sources?: FavoriteSource[];
  region?: "中国" | "美国" | "全球";
  company?: string;
};

export type FavoriteItem = Omit<
  FavoriteInput,
  "keywords" | "sectors" | "sources"
> & {
  keywords: string[];
  sectors: string[];
  sources: FavoriteSource[];
  savedAt: string;
};

type FavoritePayload = {
  schemaVersion: 1;
  items: FavoriteItem[];
};

const MAX_FAVORITES = 300;
const MAX_KEYWORDS = 40;
const MAX_SOURCES = 20;

function cleanText(value: unknown, maxLength: number): string {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function uniqueStrings(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of value) {
    const item = cleanText(raw, 100);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function validHttpUrl(value: unknown): string {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function normalizeSources(value: unknown): FavoriteSource[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: FavoriteSource[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== "object") continue;
    const source = raw as Record<string, unknown>;
    const url = validHttpUrl(source.url);
    let host = "";
    try {
      host = new URL(url).hostname.replace(/^www\./, "").toLocaleLowerCase("en-US");
    } catch {
      continue;
    }
    if (!host || seen.has(host)) continue;
    seen.add(host);
    result.push({
      name: cleanText(source.name, 120) || host,
      url,
      ...(cleanText(source.level, 40)
        ? { level: cleanText(source.level, 40) }
        : {}),
    });
    if (result.length >= MAX_SOURCES) break;
  }
  return result;
}

function normalizeHref(value: unknown): string {
  const href = cleanText(value, 500);
  if (!href || !href.startsWith("/") || href.startsWith("//")) return "";
  return href.endsWith("/") ? href : `${href}/`;
}

const CHANNELS = new Set<FavoriteChannel>([
  "technology",
  "companies",
  "institutions",
  "ipo",
  "reports",
  "people",
]);

export function normalizeFavorite(
  value: unknown,
  fallbackSavedAt = new Date().toISOString(),
): FavoriteItem | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const channel =
    typeof raw.channel === "string" && CHANNELS.has(raw.channel as FavoriteChannel)
      ? (raw.channel as FavoriteChannel)
      : null;
  const id = cleanText(raw.id, 180);
  const href = normalizeHref(raw.href);
  const title = cleanText(raw.title, 240);
  if (!channel || !id || !href || !title) return null;

  const savedAtRaw = cleanText(raw.savedAt, 40);
  const savedAt = Number.isNaN(Date.parse(savedAtRaw))
    ? fallbackSavedAt
    : savedAtRaw;
  const region =
    raw.region === "中国" || raw.region === "美国" || raw.region === "全球"
      ? raw.region
      : undefined;

  return {
    id,
    href,
    title,
    summary: cleanText(raw.summary, 1200),
    channel,
    channelLabel: cleanText(raw.channelLabel, 40) || channel,
    keywords: uniqueStrings(raw.keywords, MAX_KEYWORDS),
    sectors: uniqueStrings(raw.sectors, 20),
    sources: normalizeSources(raw.sources),
    ...(region ? { region } : {}),
    ...(cleanText(raw.company, 120)
      ? { company: cleanText(raw.company, 120) }
      : {}),
    savedAt,
  };
}

export function parseFavoriteItems(value: string | null): FavoriteItem[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    const rawItems = Array.isArray(parsed)
      ? parsed
      : parsed &&
          typeof parsed === "object" &&
          Array.isArray((parsed as Record<string, unknown>).items)
        ? ((parsed as Record<string, unknown>).items as unknown[])
        : [];
    const seen = new Set<string>();
    const items: FavoriteItem[] = [];
    for (const raw of rawItems) {
      const item = normalizeFavorite(raw);
      if (!item || seen.has(item.id)) continue;
      seen.add(item.id);
      items.push(item);
      if (items.length >= MAX_FAVORITES) break;
    }
    return items.sort((left, right) => right.savedAt.localeCompare(left.savedAt));
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

export function readFavoriteItems(): FavoriteItem[] {
  const storage = browserStorage();
  return storage ? parseFavoriteItems(storage.getItem(FAVORITES_STORAGE_KEY)) : [];
}

function writeFavoriteItems(items: FavoriteItem[]): void {
  const storage = browserStorage();
  if (!storage) return;
  const payload: FavoritePayload = {
    schemaVersion: FAVORITES_SCHEMA_VERSION,
    items: items.slice(0, MAX_FAVORITES),
  };
  storage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent(FAVORITES_CHANGED_EVENT));
}

export function isFavorite(id: string): boolean {
  return readFavoriteItems().some((item) => item.id === id);
}

export function toggleFavorite(input: FavoriteInput): boolean {
  const current = readFavoriteItems();
  const existing = current.find((item) => item.id === input.id);
  if (existing) {
    writeFavoriteItems(current.filter((item) => item.id !== input.id));
    return false;
  }
  const item = normalizeFavorite({
    ...input,
    savedAt: new Date().toISOString(),
  });
  if (!item) return false;
  writeFavoriteItems([item, ...current.filter((entry) => entry.id !== item.id)]);
  return true;
}

export function removeFavorite(id: string): void {
  writeFavoriteItems(readFavoriteItems().filter((item) => item.id !== id));
}
