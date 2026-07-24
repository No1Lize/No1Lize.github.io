import rawTrackingConfig from "@/config/user_tracking.json";

export const TRACKING_REPOSITORY = "No1Lize/No1Lize.github.io";
export const TRACKING_BRANCH = "main";
export const TRACKING_CONFIG_PATH = "config/user_tracking.json";

export type TrackingRegion = "中国" | "美国" | "全球";
export type TrackingSourceType = "rss" | "listing-search";

export type TrackingTrack = {
  slug: string;
  name: string;
  enabled: boolean;
  custom: boolean;
  keywords: string[];
  people: string[];
  sampleCompanies: string[];
};

export type TrackingSource = {
  id: string;
  name: string;
  url: string;
  sourceType: TrackingSourceType;
  region: TrackingRegion;
  sector: string;
  company: string;
  ticker: string;
  keywords: string[];
  enabled: boolean;
};

export type UserTrackingConfig = {
  schemaVersion: 1;
  tracks: TrackingTrack[];
  sources: TrackingSource[];
};

const REGIONS: TrackingRegion[] = ["中国", "美国", "全球"];
const SOURCE_TYPES: TrackingSourceType[] = ["rss", "listing-search"];

function cleanText(value: unknown, maxLength = 120): string {
  return typeof value === "string"
    ? value.replace(/\s+/g, " ").trim().slice(0, maxLength)
    : "";
}

function uniqueStrings(value: unknown, maxItems = 80): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map((item) => cleanText(item)).filter(Boolean))].slice(
    0,
    maxItems,
  );
}

export function slugifyTrack(value: string): string {
  const ascii = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  if (ascii) return ascii;
  return `track-${Date.now().toString(36)}`;
}

function normalizeTrack(value: unknown, index: number): TrackingTrack | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 60);
  if (!name) return null;
  return {
    slug: cleanText(raw.slug, 60) || `${slugifyTrack(name)}-${index + 1}`,
    name,
    enabled: raw.enabled !== false,
    custom: raw.custom === true,
    keywords: uniqueStrings(raw.keywords),
    people: uniqueStrings(raw.people),
    sampleCompanies: uniqueStrings(raw.sampleCompanies),
  };
}

function normalizeSource(value: unknown, index: number): TrackingSource | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 80);
  const url = cleanText(raw.url, 500);
  if (!name || !/^https?:\/\//i.test(url)) return null;
  const sourceType = SOURCE_TYPES.includes(raw.sourceType as TrackingSourceType)
    ? (raw.sourceType as TrackingSourceType)
    : "listing-search";
  const region = REGIONS.includes(raw.region as TrackingRegion)
    ? (raw.region as TrackingRegion)
    : "全球";
  return {
    id:
      cleanText(raw.id, 80) ||
      `user-source-${slugifyTrack(name)}-${index + 1}`,
    name,
    url,
    sourceType,
    region,
    sector: cleanText(raw.sector, 60) || "AI / AGI",
    company: cleanText(raw.company, 80),
    ticker: cleanText(raw.ticker, 30).toUpperCase(),
    keywords: uniqueStrings(raw.keywords),
    enabled: raw.enabled !== false,
  };
}

export function normalizeTrackingConfig(value: unknown): UserTrackingConfig {
  const raw = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const tracks = Array.isArray(raw.tracks)
    ? raw.tracks
        .map(normalizeTrack)
        .filter((item): item is TrackingTrack => Boolean(item))
    : [];
  const sources = Array.isArray(raw.sources)
    ? raw.sources
        .map(normalizeSource)
        .filter((item): item is TrackingSource => Boolean(item))
    : [];

  const uniqueTracks = tracks.filter(
    (track, index) =>
      tracks.findIndex((candidate) => candidate.slug === track.slug) === index,
  );
  const uniqueSources = sources.filter(
    (source, index) =>
      sources.findIndex((candidate) => candidate.id === source.id) === index,
  );

  return {
    schemaVersion: 1,
    tracks: uniqueTracks,
    sources: uniqueSources,
  };
}

export function cloneTrackingConfig(config: UserTrackingConfig): UserTrackingConfig {
  return JSON.parse(JSON.stringify(config)) as UserTrackingConfig;
}

export const userTrackingConfig = normalizeTrackingConfig(rawTrackingConfig);
