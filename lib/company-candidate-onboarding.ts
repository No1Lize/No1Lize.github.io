import type { CompanyCandidate } from "@/lib/company-candidate-data";
import {
  companyCandidateEvidenceFingerprint,
  type CompanyCandidateDecision,
  type CompanyCandidateDecisionManifest,
} from "@/lib/company-candidate-review";

export type CompanyOnboardingStatus =
  | "awaiting_profile"
  | "requested"
  | "published"
  | "failed"
  | "merged";

export type CompanyOnboardingProfile = {
  slug: string;
  name: string;
  englishName: string;
  region: string;
  sector: string;
  stage: string;
  status: "运营中" | "已上市";
  founded: string;
  headquarters: string;
  summary: string;
  product: string;
  homepage: string;
  newsUrls: string[];
  aliases: string[];
  confidence: number;
};

export type CompanyCandidateOnboarding = {
  status: CompanyOnboardingStatus;
  mode: "create" | "merge";
  profile: CompanyOnboardingProfile;
  evidenceFingerprint: string;
  requestedAt: string;
  requestedBy: string;
  publishedAt: string;
  publishedSlug: string;
  error: string;
};

function text(value: unknown, limit = 1_200) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function list(value: unknown, limit = 30) {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = text(raw, 500);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function safeUrl(value: unknown) {
  const url = text(value, 2_000);
  return /^https?:\/\//iu.test(url) ? url : "";
}

export function normalizeCompanyOnboardingProfile(
  value: unknown,
): CompanyOnboardingProfile {
  const row = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  return {
    slug: text(row.slug, 120).toLocaleLowerCase("en-US"),
    name: text(row.name, 240),
    englishName: text(row.englishName, 240),
    region: text(row.region, 80),
    sector: text(row.sector, 120),
    stage: text(row.stage, 80),
    status: row.status === "已上市" ? "已上市" : "运营中",
    founded: text(row.founded, 40),
    headquarters: text(row.headquarters, 160),
    summary: text(row.summary, 1_200),
    product: text(row.product, 1_200),
    homepage: safeUrl(row.homepage),
    newsUrls: list(row.newsUrls, 20).map(safeUrl).filter(Boolean),
    aliases: list(row.aliases, 30),
    confidence: Math.max(0.5, Math.min(1, Number(row.confidence) || 0.9)),
  };
}

export function emptyCompanyOnboardingProfile(
  candidate: Pick<CompanyCandidate, "name" | "region" | "sector" | "aliases" | "sourceUrls">,
): CompanyOnboardingProfile {
  const source = candidate.sourceUrls.find((url) => /^https?:\/\//iu.test(url)) ?? "";
  let homepage = "";
  try {
    const parsed = new URL(source);
    homepage = `${parsed.protocol}//${parsed.hostname}/`;
  } catch {
    homepage = "";
  }
  return {
    slug: /^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(candidate.name.toLocaleLowerCase("en-US"))
      ? candidate.name.toLocaleLowerCase("en-US")
      : "",
    name: candidate.name,
    englishName: /^[\x00-\x7F]+$/u.test(candidate.name) ? candidate.name : "",
    region: candidate.region === "全球" ? "" : candidate.region,
    sector: candidate.sector === "待分类" ? "" : candidate.sector,
    stage: "成长期",
    status: "运营中",
    founded: "",
    headquarters: "",
    summary: "",
    product: "",
    homepage,
    newsUrls: source ? [source] : [],
    aliases: candidate.aliases,
    confidence: 0.9,
  };
}

export function normalizeCompanyCandidateOnboarding(
  value: unknown,
): CompanyCandidateOnboarding | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const rawStatus = text(row.status, 40) as CompanyOnboardingStatus;
  const statuses = new Set<CompanyOnboardingStatus>([
    "awaiting_profile",
    "requested",
    "published",
    "failed",
    "merged",
  ]);
  return {
    status: statuses.has(rawStatus) ? rawStatus : "awaiting_profile",
    mode: row.mode === "merge" ? "merge" : "create",
    profile: normalizeCompanyOnboardingProfile(row.profile),
    evidenceFingerprint: text(row.evidenceFingerprint, 10_000),
    requestedAt: text(row.requestedAt, 80),
    requestedBy: text(row.requestedBy, 120),
    publishedAt: text(row.publishedAt, 80),
    publishedSlug: text(row.publishedSlug, 120),
    error: text(row.error, 1_000),
  };
}

export function validateCompanyOnboardingProfile(
  profile: CompanyOnboardingProfile,
  candidate: Pick<CompanyCandidate, "name" | "eventTypes">,
) {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(profile.slug)) {
    return { valid: false, message: "请填写合法 slug，例如 shopify 或 x-corp。" };
  }
  if (profile.name.length < 2) {
    return { valid: false, message: "请填写规范公司名称。" };
  }
  if (!profile.region || !profile.sector || !profile.stage) {
    return { valid: false, message: "地区、赛道和阶段均为必填项。" };
  }
  if (profile.summary.length < 20) {
    return { valid: false, message: "公司简介至少需要 20 个字符。" };
  }
  if (profile.product.length < 6) {
    return { valid: false, message: "核心产品说明至少需要 6 个字符。" };
  }
  if (!/^https?:\/\//iu.test(profile.homepage)) {
    return { valid: false, message: "请填写可公开访问的公司官方主页。" };
  }
  if (
    candidate.eventTypes.length === 1 &&
    candidate.eventTypes[0] === "人物观点" &&
    profile.name.normalize("NFKC").toLocaleLowerCase("zh-CN") ===
      candidate.name.normalize("NFKC").toLocaleLowerCase("zh-CN")
  ) {
    return {
      valid: false,
      message: "该候选来自人物观点，必须改填规范公司实体名称，不能以人物姓名建档。",
    };
  }
  return { valid: true, message: "" };
}

export function requestCompanyCandidateOnboarding({
  manifest,
  candidate,
  profile,
  requestedBy,
  requestedAt,
}: {
  manifest: CompanyCandidateDecisionManifest;
  candidate: CompanyCandidate;
  profile: CompanyOnboardingProfile;
  requestedBy: string;
  requestedAt: string;
}): CompanyCandidateDecisionManifest {
  const current = manifest.decisions[candidate.decisionKey];
  if (!current || current.status !== "accepted") {
    throw new Error("只有已审核通过的候选才能发起新公司建档。");
  }
  const decision: CompanyCandidateDecision = {
    ...current,
    onboarding: {
      status: "requested",
      mode: "create",
      profile: normalizeCompanyOnboardingProfile(profile),
      evidenceFingerprint: companyCandidateEvidenceFingerprint(candidate),
      requestedAt,
      requestedBy,
      publishedAt: "",
      publishedSlug: "",
      error: "",
    },
  };
  return {
    schemaVersion: Math.max(1, manifest.schemaVersion || 1),
    decisions: {
      ...manifest.decisions,
      [candidate.decisionKey]: decision,
    },
  };
}
