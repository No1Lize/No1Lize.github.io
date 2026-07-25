import rawVentureProfiles from "@/public/data/venture_profiles.json";

export type VentureSource = {
  name: string;
  url: string;
  level: "官方披露" | "监管文件" | "媒体报道" | "数据库记录" | "待交叉验证";
  section?: string;
  title?: string;
  publishedAt?: string;
};

export type VentureTeamMember = {
  name: string;
  role?: string;
  summary?: string;
  sourceUrl?: string;
};

export type VentureCapitalEvent = {
  date?: string;
  type: string;
  title: string;
  summary: string;
  amount?: string;
  round?: string;
  investors?: string[];
  sourceUrl?: string;
};

export type VenturePortfolioCase = {
  name: string;
  companySlug?: string;
  date?: string;
  round?: string;
  summary: string;
  sourceUrl?: string;
};

export type VentureClassicCase = {
  name: string;
  companySlug?: string;
  analysis: string;
  sourceUrl?: string;
};

export type CompanyVentureProfile = {
  slug: string;
  name: string;
  updatedAt: string;
  status: "ok" | "partial" | "retained" | "fallback";
  background: string;
  technology: string;
  products: string[];
  team: VentureTeamMember[];
  financing: VentureCapitalEvent[];
  capitalMarkets: VentureCapitalEvent[];
  sources: VentureSource[];
  warnings?: string[];
  evidenceScore?: number;
};

export type InstitutionVentureProfile = {
  slug: string;
  name: string;
  updatedAt: string;
  status: "ok" | "partial" | "retained" | "fallback";
  overview: string;
  strategy: string;
  team: VentureTeamMember[];
  recentInvestments: VenturePortfolioCase[];
  portfolio: VenturePortfolioCase[];
  classicCases: VentureClassicCase[];
  sources: VentureSource[];
  warnings?: string[];
  evidenceScore?: number;
};

type VentureProfileSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  companies?: Record<string, CompanyVentureProfile>;
  institutions?: Record<string, InstitutionVentureProfile>;
  sourceStatus?: {
    kind: "company" | "institution";
    slug: string;
    name: string;
    status: string;
    fetchedPages: number;
    acceptedSections: number;
    retainedPrevious?: boolean;
    error?: string;
  }[];
  qualityGate?: {
    passed: boolean;
    checks: Record<string, { actual: number; required: number; passed: boolean }>;
  };
};

const VALID_SOURCE_LEVELS = new Set([
  "官方披露",
  "监管文件",
  "媒体报道",
  "数据库记录",
  "待交叉验证",
]);

function clean(value: unknown, limit = 600) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function cleanList(values: unknown, limit = 20, itemLimit = 220) {
  if (!Array.isArray(values)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const item = clean(value, itemLimit);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function validUrl(value: unknown) {
  const text = clean(value, 1000);
  return /^https?:\/\//iu.test(text) ? text : "";
}

function normalizeSources(values: unknown): VentureSource[] {
  if (!Array.isArray(values)) return [];
  const result: VentureSource[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const url = validUrl(row.url);
    if (!url || seen.has(url)) continue;
    const level = clean(row.level, 20);
    result.push({
      name: clean(row.name, 120) || new URL(url).hostname,
      url,
      level: VALID_SOURCE_LEVELS.has(level)
        ? (level as VentureSource["level"])
        : "官方披露",
      section: clean(row.section, 60) || undefined,
      title: clean(row.title, 200) || undefined,
      publishedAt: clean(row.publishedAt, 20) || undefined,
    });
    seen.add(url);
    if (result.length >= 30) break;
  }
  return result;
}

function normalizeTeam(values: unknown): VentureTeamMember[] {
  if (!Array.isArray(values)) return [];
  const result: VentureTeamMember[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 100);
    if (!name || seen.has(name.toLocaleLowerCase("zh-CN"))) continue;
    result.push({
      name,
      role: clean(row.role, 120) || undefined,
      summary: clean(row.summary, 280) || undefined,
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(name.toLocaleLowerCase("zh-CN"));
    if (result.length >= 20) break;
  }
  return result;
}

function normalizeCapitalEvents(values: unknown): VentureCapitalEvent[] {
  if (!Array.isArray(values)) return [];
  const result: VentureCapitalEvent[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const title = clean(row.title, 220);
    const summary = clean(row.summary, 420);
    if (!title && !summary) continue;
    const key = `${clean(row.date, 20)}|${title}|${summary}`.toLocaleLowerCase("zh-CN");
    if (seen.has(key)) continue;
    result.push({
      date: clean(row.date, 20) || undefined,
      type: clean(row.type, 60) || "资本事件",
      title: title || summary.slice(0, 80),
      summary: summary || title,
      amount: clean(row.amount, 80) || undefined,
      round: clean(row.round, 80) || undefined,
      investors: cleanList(row.investors, 12, 100),
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 16) break;
  }
  return result;
}

function normalizePortfolio(values: unknown): VenturePortfolioCase[] {
  if (!Array.isArray(values)) return [];
  const result: VenturePortfolioCase[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 120);
    if (!name || seen.has(name.toLocaleLowerCase("zh-CN"))) continue;
    result.push({
      name,
      companySlug: clean(row.companySlug, 100) || undefined,
      date: clean(row.date, 20) || undefined,
      round: clean(row.round, 80) || undefined,
      summary: clean(row.summary, 360) || "公开组合记录。",
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(name.toLocaleLowerCase("zh-CN"));
    if (result.length >= 30) break;
  }
  return result;
}

function normalizeClassicCases(values: unknown): VentureClassicCase[] {
  if (!Array.isArray(values)) return [];
  const result: VentureClassicCase[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 120);
    const analysis = clean(row.analysis, 520);
    if (!name || !analysis || seen.has(name.toLocaleLowerCase("zh-CN"))) continue;
    result.push({
      name,
      companySlug: clean(row.companySlug, 100) || undefined,
      analysis,
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(name.toLocaleLowerCase("zh-CN"));
    if (result.length >= 8) break;
  }
  return result;
}

function normalizeCompanyProfile(raw: CompanyVentureProfile): CompanyVentureProfile {
  return {
    slug: clean(raw.slug, 100),
    name: clean(raw.name, 120),
    updatedAt: clean(raw.updatedAt, 40),
    status: raw.status || "fallback",
    background: clean(raw.background, 900),
    technology: clean(raw.technology, 900),
    products: cleanList(raw.products, 16, 240),
    team: normalizeTeam(raw.team),
    financing: normalizeCapitalEvents(raw.financing),
    capitalMarkets: normalizeCapitalEvents(raw.capitalMarkets),
    sources: normalizeSources(raw.sources),
    warnings: cleanList(raw.warnings, 12, 220),
    evidenceScore: Number.isFinite(Number(raw.evidenceScore))
      ? Number(raw.evidenceScore)
      : undefined,
  };
}

function normalizeInstitutionProfile(raw: InstitutionVentureProfile): InstitutionVentureProfile {
  return {
    slug: clean(raw.slug, 100),
    name: clean(raw.name, 120),
    updatedAt: clean(raw.updatedAt, 40),
    status: raw.status || "fallback",
    overview: clean(raw.overview, 900),
    strategy: clean(raw.strategy, 900),
    team: normalizeTeam(raw.team),
    recentInvestments: normalizePortfolio(raw.recentInvestments),
    portfolio: normalizePortfolio(raw.portfolio),
    classicCases: normalizeClassicCases(raw.classicCases),
    sources: normalizeSources(raw.sources),
    warnings: cleanList(raw.warnings, 12, 220),
    evidenceScore: Number.isFinite(Number(raw.evidenceScore))
      ? Number(raw.evidenceScore)
      : undefined,
  };
}

const snapshot = rawVentureProfiles as VentureProfileSnapshot;

export const ventureProfileGeneratedAt = clean(snapshot.generatedAt, 40);
export const companyVentureProfiles = Object.fromEntries(
  Object.entries(snapshot.companies ?? {}).map(([slug, profile]) => [
    slug,
    normalizeCompanyProfile(profile),
  ]),
) as Record<string, CompanyVentureProfile>;
export const institutionVentureProfiles = Object.fromEntries(
  Object.entries(snapshot.institutions ?? {}).map(([slug, profile]) => [
    slug,
    normalizeInstitutionProfile(profile),
  ]),
) as Record<string, InstitutionVentureProfile>;
export const ventureProfileSourceStatus = snapshot.sourceStatus ?? [];
export const ventureProfileQualityGate = snapshot.qualityGate;

export function getCompanyVentureProfile(slug: string) {
  return companyVentureProfiles[slug];
}

export function getInstitutionVentureProfile(slug: string) {
  return institutionVentureProfiles[slug];
}
