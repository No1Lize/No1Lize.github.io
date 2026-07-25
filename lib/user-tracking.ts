import rawTrackingConfig from "@/config/user_tracking.json";
import { ipoCompanies } from "@/lib/catalog-data";

export const TRACKING_REPOSITORY = "No1Lize/No1Lize.github.io";
export const TRACKING_BRANCH = "main";
export const TRACKING_CONFIG_PATH = "config/user_tracking.json";
export const TRACKING_OWNER = "No1Lize";

export type TrackingRegion = "中国" | "美国" | "全球";
export type TrackingSourceType = "rss" | "listing-search" | "sec";
export type TrackingMarket = "A股" | "港股" | "美股";

export type TrackingTrack = {
  slug: string;
  name: string;
  enabled: boolean;
  custom: boolean;
  keywords: string[];
  people: string[];
  sampleCompanies: string[];
};

export type TrackingListedCompany = {
  id: string;
  name: string;
  ticker: string;
  market: TrackingMarket;
  sector: string;
  enabled: boolean;
  custom: boolean;
  catalogSlug?: string;
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
  listedCompanyId?: string;
};

export type UserTrackingConfig = {
  schemaVersion: 1;
  tracks: TrackingTrack[];
  listedCompanies: TrackingListedCompany[];
  sources: TrackingSource[];
};

const REGIONS: TrackingRegion[] = ["中国", "美国", "全球"];
const MARKETS: TrackingMarket[] = ["A股", "港股", "美股"];
const SOURCE_TYPES: TrackingSourceType[] = ["rss", "listing-search", "sec"];

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

function stableHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

export function slugifyTrack(value: string): string {
  const ascii = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return ascii || `track-${stableHash(value)}`;
}

function normalizeTrack(value: unknown, index: number): TrackingTrack | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 60);
  if (!name) return null;
  const custom = raw.custom === true;
  const suppliedSlug = cleanText(raw.slug, 60);
  return {
    slug: custom
      ? slugifyTrack(suppliedSlug || name)
      : suppliedSlug || `${slugifyTrack(name)}-${index + 1}`,
    name,
    enabled: raw.enabled !== false,
    custom,
    keywords: uniqueStrings(raw.keywords),
    people: uniqueStrings(raw.people),
    sampleCompanies: uniqueStrings(raw.sampleCompanies),
  };
}

function normalizeListedCompany(
  value: unknown,
  index: number,
): TrackingListedCompany | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 80);
  const ticker = cleanText(raw.ticker, 30).toUpperCase().replace(/\s+/g, "");
  const market = MARKETS.includes(raw.market as TrackingMarket)
    ? (raw.market as TrackingMarket)
    : null;
  if (!name || !ticker || !market) return null;
  const catalogSlug = cleanText(raw.catalogSlug, 80);
  return {
    id:
      cleanText(raw.id, 100) ||
      `listed-${market}-${slugifyTrack(ticker || name)}-${index + 1}`,
    name,
    ticker,
    market,
    sector: cleanText(raw.sector, 60) || "未分类",
    enabled: raw.enabled !== false,
    custom: raw.custom === true || !catalogSlug,
    ...(catalogSlug ? { catalogSlug } : {}),
  };
}

function normalizeSource(value: unknown, index: number): TrackingSource | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 80);
  const sourceType = SOURCE_TYPES.includes(raw.sourceType as TrackingSourceType)
    ? (raw.sourceType as TrackingSourceType)
    : "listing-search";
  const ticker = cleanText(raw.ticker, 30).toUpperCase();
  const suppliedUrl = cleanText(raw.url, 500);
  const url =
    sourceType === "sec" && !suppliedUrl
      ? "https://www.sec.gov/edgar/search/"
      : suppliedUrl;
  if (
    !name ||
    !/^https?:\/\//i.test(url) ||
    (sourceType === "sec" && !ticker)
  ) {
    return null;
  }
  const region = REGIONS.includes(raw.region as TrackingRegion)
    ? (raw.region as TrackingRegion)
    : "全球";
  const listedCompanyId = cleanText(raw.listedCompanyId, 100);
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
    ticker,
    keywords: uniqueStrings(raw.keywords),
    enabled: raw.enabled !== false,
    ...(listedCompanyId ? { listedCompanyId } : {}),
  };
}

function defaultListedCompanies(): TrackingListedCompany[] {
  return ipoCompanies.map((company) => ({
    id: `catalog-${company.slug}`,
    name: company.name,
    ticker: company.ticker,
    market: company.market,
    sector: company.sector,
    enabled: true,
    custom: false,
    catalogSlug: company.slug,
  }));
}

export function normalizeTrackingConfig(value: unknown): UserTrackingConfig {
  const raw =
    value && typeof value === "object"
      ? (value as Record<string, unknown>)
      : {};
  const tracks = Array.isArray(raw.tracks)
    ? raw.tracks
        .map(normalizeTrack)
        .filter((item): item is TrackingTrack => Boolean(item))
    : [];
  const listedCompanies = Array.isArray(raw.listedCompanies)
    ? raw.listedCompanies
        .map(normalizeListedCompany)
        .filter((item): item is TrackingListedCompany => Boolean(item))
    : defaultListedCompanies();
  const sources = Array.isArray(raw.sources)
    ? raw.sources
        .map(normalizeSource)
        .filter((item): item is TrackingSource => Boolean(item))
    : [];

  const uniqueTracks = tracks.filter((track, index) => {
    const normalizedName = track.name.toLocaleLowerCase("zh-CN");
    return (
      tracks.findIndex(
        (candidate) =>
          candidate.slug === track.slug ||
          candidate.name.toLocaleLowerCase("zh-CN") === normalizedName,
      ) === index
    );
  });
  const uniqueListedCompanies = listedCompanies.filter(
    (company, index) =>
      listedCompanies.findIndex(
        (candidate) =>
          candidate.id === company.id ||
          (candidate.market === company.market &&
            candidate.ticker === company.ticker),
      ) === index,
  );
  const uniqueSources = sources.filter(
    (source, index) =>
      sources.findIndex((candidate) => candidate.id === source.id) === index,
  );

  return {
    schemaVersion: 1,
    tracks: uniqueTracks,
    listedCompanies: uniqueListedCompanies,
    sources: uniqueSources,
  };
}

export function cloneTrackingConfig(
  config: UserTrackingConfig,
): UserTrackingConfig {
  return JSON.parse(JSON.stringify(config)) as UserTrackingConfig;
}

export const userTrackingConfig = normalizeTrackingConfig(rawTrackingConfig);
