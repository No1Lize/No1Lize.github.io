import rawVentureProfiles from "@/public/data/venture_profiles.json";

export type ProfessionalSourceStatus = {
  name: string;
  status: "success" | "no_data" | "disabled" | "error" | string;
  detail: string;
  url: string;
  records: number;
  updatedAt?: string;
};

export type EquityHolder = {
  name: string;
  percent?: string;
  subscribedCapital?: string;
  paidCapital?: string;
  tags: string[];
  relationship?: string;
  sourceName?: string;
  sourceUrl?: string;
};

export type EquityChange = {
  date?: string;
  item: string;
  before?: string;
  after?: string;
  sourceName?: string;
  sourceUrl?: string;
};

export type ExternalInvestment = {
  name: string;
  percent?: string;
  amount?: string;
  registeredCapital?: string;
  status?: string;
  sourceName?: string;
  sourceUrl?: string;
};

export type CompanyEquityProfile = {
  legalName?: string;
  creditCode?: string;
  registrationStatus?: string;
  registeredCapital?: string;
  paidUpCapital?: string;
  legalRepresentative?: string;
  shareholders: EquityHolder[];
  beneficialOwners: EquityHolder[];
  changes: EquityChange[];
  externalInvestments: ExternalInvestment[];
  sourceNames: string[];
  sourceUrls: string[];
  evidenceStatus: "cross-verified" | "single-source" | "pending" | string;
  verifiedAt?: string;
};

type RawCompanyProfile = {
  equityProfile?: unknown;
  professionalSources?: unknown;
};

type RawSnapshot = {
  professionalSourceGeneratedAt?: string;
  companies?: Record<string, RawCompanyProfile>;
};

function text(value: unknown, limit = 500) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function url(value: unknown) {
  const candidate = text(value, 1200);
  return /^https?:\/\//iu.test(candidate) ? candidate : "";
}

function strings(value: unknown, limit = 30, itemLimit = 180) {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = text(raw, itemLimit);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function records(value: unknown) {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => Boolean(item) && typeof item === "object",
      )
    : [];
}

function normalizeHolders(value: unknown): EquityHolder[] {
  const result: EquityHolder[] = [];
  const seen = new Set<string>();
  for (const row of records(value)) {
    const name = text(row.name, 160);
    const key = name.toLocaleLowerCase("zh-CN");
    if (!name || seen.has(key)) continue;
    result.push({
      name,
      percent: text(row.percent, 50) || undefined,
      subscribedCapital: text(row.subscribedCapital, 120) || undefined,
      paidCapital: text(row.paidCapital, 120) || undefined,
      tags: strings(row.tags, 8, 80),
      relationship: text(row.relationship, 100) || undefined,
      sourceName: text(row.sourceName, 80) || undefined,
      sourceUrl: url(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 100) break;
  }
  return result;
}

function normalizeChanges(value: unknown): EquityChange[] {
  return records(value)
    .map((row) => ({
      date: text(row.date, 30) || undefined,
      item: text(row.item, 180),
      before: text(row.before, 520) || undefined,
      after: text(row.after, 520) || undefined,
      sourceName: text(row.sourceName, 80) || undefined,
      sourceUrl: url(row.sourceUrl) || undefined,
    }))
    .filter((row) => row.item)
    .slice(0, 100);
}

function normalizeInvestments(value: unknown): ExternalInvestment[] {
  return records(value)
    .map((row) => ({
      name: text(row.name, 180),
      percent: text(row.percent, 50) || undefined,
      amount: text(row.amount, 120) || undefined,
      registeredCapital: text(row.registeredCapital, 120) || undefined,
      status: text(row.status, 80) || undefined,
      sourceName: text(row.sourceName, 80) || undefined,
      sourceUrl: url(row.sourceUrl) || undefined,
    }))
    .filter((row) => row.name)
    .slice(0, 100);
}

function normalizeEquityProfile(value: unknown): CompanyEquityProfile | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  return {
    legalName: text(row.legalName, 220) || undefined,
    creditCode: text(row.creditCode, 100) || undefined,
    registrationStatus: text(row.registrationStatus, 100) || undefined,
    registeredCapital: text(row.registeredCapital, 120) || undefined,
    paidUpCapital: text(row.paidUpCapital, 120) || undefined,
    legalRepresentative: text(row.legalRepresentative, 140) || undefined,
    shareholders: normalizeHolders(row.shareholders),
    beneficialOwners: normalizeHolders(row.beneficialOwners),
    changes: normalizeChanges(row.changes),
    externalInvestments: normalizeInvestments(row.externalInvestments),
    sourceNames: strings(row.sourceNames, 8, 80),
    sourceUrls: strings(row.sourceUrls, 12, 1200).filter((item) =>
      /^https?:\/\//iu.test(item),
    ),
    evidenceStatus: text(row.evidenceStatus, 40) || "pending",
    verifiedAt: text(row.verifiedAt, 40) || undefined,
  };
}

function normalizeProfessionalSources(value: unknown): ProfessionalSourceStatus[] {
  return records(value)
    .map((row) => ({
      name: text(row.name, 80),
      status: text(row.status, 40) || "disabled",
      detail: text(row.detail, 360),
      url: url(row.url),
      records: Math.max(0, Number(row.records) || 0),
      updatedAt: text(row.updatedAt, 40) || undefined,
    }))
    .filter((row) => row.name && row.url)
    .slice(0, 8);
}

const snapshot = rawVentureProfiles as unknown as RawSnapshot;

export const professionalVentureGeneratedAt = text(
  snapshot.professionalSourceGeneratedAt,
  40,
);

export function getCompanyProfessionalVentureProfile(slug: string) {
  const profile = snapshot.companies?.[slug];
  if (!profile) return undefined;
  return {
    equityProfile: normalizeEquityProfile(profile.equityProfile),
    professionalSources: normalizeProfessionalSources(profile.professionalSources),
  };
}
