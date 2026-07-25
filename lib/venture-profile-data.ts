import rawVentureProfiles from "@/public/data/venture_profiles.json";

export type VentureSource = {
  name: string;
  url: string;
  level: "官方披露" | "原始材料" | "监管文件" | "媒体报道" | "数据库记录" | "待交叉验证";
  section?: string;
  title?: string;
  publishedAt?: string;
};

export type VentureTeamMember = {
  name: string;
  role?: string;
  summary?: string;
  background?: string;
  previousExperience?: string;
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
  investmentLogic?: string;
  followOnPerformance?: string;
  exitPerformance?: string;
  analysis: string;
  sourceUrl?: string;
};

export type VentureProjectBackground = {
  summary: string;
  problemSolved?: string;
  marketOpportunity?: string;
};

export type VentureTechnologyProduct = {
  name: string;
  category?: string;
  description: string;
  technicalHighlights?: string[];
  sourceUrl?: string;
};

export type VentureCapitalSummary = {
  eventCount: number;
  disclosedAmounts: string[];
  rounds: string[];
  majorInvestors: string[];
  latestDate?: string;
  latestRound?: string;
  summary: string;
};

export type VentureExitPerformance = {
  status: string;
  latestDate?: string;
  latestEvent?: string;
  summary: string;
  sourceUrl?: string;
};

export type VentureRecentYearSummary = {
  periodStart: string;
  periodEnd: string;
  investmentCount: number;
  companies: string[];
  sectors: string[];
  rounds: string[];
  summary: string;
};

export type CompanyVentureProfile = {
  slug: string;
  name: string;
  updatedAt: string;
  status: "ok" | "partial" | "retained" | "fallback";
  background: string;
  projectBackground?: VentureProjectBackground;
  technology: string;
  products: string[];
  technologyProducts?: VentureTechnologyProduct[];
  team: VentureTeamMember[];
  financing: VentureCapitalEvent[];
  capitalSummary?: VentureCapitalSummary;
  capitalMarkets: VentureCapitalEvent[];
  exitPerformance?: VentureExitPerformance;
  researchModelVersion?: number;
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
  recentYearSummary?: VentureRecentYearSummary;
  portfolio: VenturePortfolioCase[];
  classicCases: VentureClassicCase[];
  researchModelVersion?: number;
  sources: VentureSource[];
  warnings?: string[];
  evidenceScore?: number;
};

type VentureProfileSnapshot = {
  schemaVersion: number;
  researchModelVersion?: number;
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
  "原始材料",
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
      summary: clean(row.summary, 360) || undefined,
      background: clean(row.background, 360) || undefined,
      previousExperience: clean(row.previousExperience, 360) || undefined,
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
    const summary = clean(row.summary, 520);
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
    if (result.length >= 20) break;
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
    const date = clean(row.date, 20);
    const key = `${name.toLocaleLowerCase("zh-CN")}|${date}`;
    if (!name || seen.has(key)) continue;
    result.push({
      name,
      companySlug: clean(row.companySlug, 100) || undefined,
      date: date || undefined,
      round: clean(row.round, 80) || undefined,
      summary: clean(row.summary, 420) || "公开组合记录。",
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 40) break;
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
    const analysis = clean(row.analysis, 760);
    if (!name || !analysis || seen.has(name.toLocaleLowerCase("zh-CN"))) continue;
    result.push({
      name,
      companySlug: clean(row.companySlug, 100) || undefined,
      investmentLogic: clean(row.investmentLogic, 520) || undefined,
      followOnPerformance: clean(row.followOnPerformance, 520) || undefined,
      exitPerformance: clean(row.exitPerformance, 520) || undefined,
      analysis,
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(name.toLocaleLowerCase("zh-CN"));
    if (result.length >= 8) break;
  }
  return result;
}

function normalizeProjectBackground(value: unknown): VentureProjectBackground | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const summary = clean(row.summary, 900);
  if (!summary) return undefined;
  return {
    summary,
    problemSolved: clean(row.problemSolved, 520) || undefined,
    marketOpportunity: clean(row.marketOpportunity, 520) || undefined,
  };
}

function normalizeTechnologyProducts(values: unknown): VentureTechnologyProduct[] {
  if (!Array.isArray(values)) return [];
  const result: VentureTechnologyProduct[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 160);
    const description = clean(row.description, 520);
    const key = name.toLocaleLowerCase("zh-CN");
    if (!name || !description || seen.has(key)) continue;
    result.push({
      name,
      category: clean(row.category, 80) || undefined,
      description,
      technicalHighlights: cleanList(row.technicalHighlights, 6, 260),
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 12) break;
  }
  return result;
}

function normalizeCapitalSummary(value: unknown): VentureCapitalSummary | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  return {
    eventCount: Math.max(0, Number(row.eventCount) || 0),
    disclosedAmounts: cleanList(row.disclosedAmounts, 12, 80),
    rounds: cleanList(row.rounds, 12, 80),
    majorInvestors: cleanList(row.majorInvestors, 20, 120),
    latestDate: clean(row.latestDate, 20) || undefined,
    latestRound: clean(row.latestRound, 80) || undefined,
    summary: clean(row.summary, 520) || "当前未识别到可核对的融资汇总。",
  };
}

function normalizeExitPerformance(value: unknown): VentureExitPerformance | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const status = clean(row.status, 100);
  const summary = clean(row.summary, 520);
  if (!status && !summary) return undefined;
  return {
    status: status || "暂无公开退出信息",
    latestDate: clean(row.latestDate, 20) || undefined,
    latestEvent: clean(row.latestEvent, 220) || undefined,
    summary: summary || "当前未识别到可核对的上市、并购或退出记录。",
    sourceUrl: validUrl(row.sourceUrl) || undefined,
  };
}

function normalizeRecentYearSummary(value: unknown): VentureRecentYearSummary | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const periodStart = clean(row.periodStart, 20);
  const periodEnd = clean(row.periodEnd, 20);
  if (!periodStart || !periodEnd) return undefined;
  return {
    periodStart,
    periodEnd,
    investmentCount: Math.max(0, Number(row.investmentCount) || 0),
    companies: cleanList(row.companies, 30, 120),
    sectors: cleanList(row.sectors, 12, 100),
    rounds: cleanList(row.rounds, 12, 80),
    summary: clean(row.summary, 520) || "最近一年暂无可核对投资记录。",
  };
}

function normalizeCompanyProfile(raw: CompanyVentureProfile): CompanyVentureProfile {
  const projectBackground = normalizeProjectBackground(raw.projectBackground);
  return {
    slug: clean(raw.slug, 100),
    name: clean(raw.name, 120),
    updatedAt: clean(raw.updatedAt, 40),
    status: raw.status || "fallback",
    background: projectBackground?.summary || clean(raw.background, 900),
    projectBackground,
    technology: clean(raw.technology, 900),
    products: cleanList(raw.products, 16, 240),
    technologyProducts: normalizeTechnologyProducts(raw.technologyProducts),
    team: normalizeTeam(raw.team),
    financing: normalizeCapitalEvents(raw.financing),
    capitalSummary: normalizeCapitalSummary(raw.capitalSummary),
    capitalMarkets: normalizeCapitalEvents(raw.capitalMarkets),
    exitPerformance: normalizeExitPerformance(raw.exitPerformance),
    researchModelVersion: Number(raw.researchModelVersion) || undefined,
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
    recentYearSummary: normalizeRecentYearSummary(raw.recentYearSummary),
    portfolio: normalizePortfolio(raw.portfolio),
    classicCases: normalizeClassicCases(raw.classicCases),
    researchModelVersion: Number(raw.researchModelVersion) || undefined,
    sources: normalizeSources(raw.sources),
    warnings: cleanList(raw.warnings, 12, 220),
    evidenceScore: Number.isFinite(Number(raw.evidenceScore))
      ? Number(raw.evidenceScore)
      : undefined,
  };
}

const snapshot = rawVentureProfiles as VentureProfileSnapshot;

export const ventureProfileGeneratedAt = clean(snapshot.generatedAt, 40);
export const ventureResearchModelVersion = Number(snapshot.researchModelVersion) || 1;
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
