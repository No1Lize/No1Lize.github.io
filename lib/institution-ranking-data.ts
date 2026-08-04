import rawRankingData from "@/config/institution_rankings.json";
import { institutionCatalog } from "./catalog-data";

export type InstitutionRankingRecord = {
  publisher: "清科";
  year: 2025;
  category: InstitutionRankingCategory;
  title: string;
  rank?: number;
  ordered: boolean;
  sourceId: string;
  sourceUrl: string;
};

export type InstitutionRankingCategory =
  | "早期投资"
  | "创业投资"
  | "私募股权"
  | "国资投资"
  | "战略投资者/CVC"
  | "并购投资"
  | "海外代表";

export type InstitutionDirectoryEntry = {
  name: string;
  fullName?: string;
  region: "中国" | "美国";
  type: string;
  stages: string;
  sectors: string[];
  profileSlug?: string;
  officialUrl?: string;
  rankings: InstitutionRankingRecord[];
};

type RankingSource = {
  id: string;
  publisher: string;
  year: number;
  title: string;
  url: string;
  role: "primary-ranking-source" | "classification-reference";
  categories: string[];
};

type RankingCategoryRecord = {
  id: string;
  publisher: "清科";
  year: 2025;
  category: Exclude<InstitutionRankingCategory, "海外代表">;
  title: string;
  ordered: boolean;
  sourceId: string;
  stages: string;
  sectors: string[];
  entries: { name: string; fullName?: string; rank?: number }[];
};

type RankingPayload = {
  schemaVersion: number;
  dataVersion: string;
  updatedAt: string;
  description: string;
  sources: RankingSource[];
  categories: RankingCategoryRecord[];
};

const rankingData = rawRankingData as RankingPayload;
const sourceById = new Map(rankingData.sources.map((source) => [source.id, source]));

export const institutionRankingDataVersion = rankingData.dataVersion;
export const institutionRankingUpdatedAt = rankingData.updatedAt;
export const institutionRankingSources = rankingData.sources;

const profileAliases: Record<string, string> = {
  真格基金: "zhenfund",
  IDG资本: "idg-capital",
  深创投集团: "scgc",
  启明创投: "qiming",
  君联资本: "legend-capital",
  达晨财智: "fortune-capital",
  高榕创投: "gaorong",
  经纬创投: "matrix-china",
  红杉中国: "hongshan",
  高瓴投资: "hillhouse",
};

const directory = new Map<string, InstitutionDirectoryEntry>();

for (const category of rankingData.categories) {
  const source = sourceById.get(category.sourceId);
  if (!source) throw new Error(`Missing institution ranking source: ${category.sourceId}`);
  category.entries.forEach((entry, index) => {
    const current = directory.get(entry.name);
    const ranking: InstitutionRankingRecord = {
      publisher: category.publisher,
      year: category.year,
      category: category.category,
      title: category.title,
      rank: category.ordered ? entry.rank ?? index + 1 : undefined,
      ordered: category.ordered,
      sourceId: category.sourceId,
      sourceUrl: source.url,
    };
    if (current) {
      current.rankings.push(ranking);
      current.sectors = [...new Set([...current.sectors, ...category.sectors])];
      if (!current.fullName && entry.fullName) current.fullName = entry.fullName;
      return;
    }
    directory.set(entry.name, {
      name: entry.name,
      fullName: entry.fullName,
      region: "中国",
      type:
        category.category === "战略投资者/CVC"
? "产业资本/CVC"
: category.category === "国资投资"
  ? "国资投资机构"
  : category.category === "并购投资"
    ? "并购投资机构"
    : category.category,
      stages: category.stages,
      sectors: [...category.sectors],
      profileSlug: profileAliases[entry.name],
      rankings: [ranking],
    });
  });
}

for (const institution of institutionCatalog) {
  const matchedName =
    institution.name === "IDG 资本"
      ? "IDG资本"
      : institution.name === "深创投"
        ? "深创投集团"
        : institution.name === "高瓴"
? "高瓴投资"
: institution.name;
  const existing = directory.get(matchedName);
  if (existing) {
    existing.profileSlug = institution.slug;
    existing.officialUrl = institution.source.url;
    existing.type = institution.type;
    existing.stages = institution.stages;
    existing.sectors = institution.sectors;
    continue;
  }
  directory.set(institution.name, {
    name: institution.name,
    fullName: institution.englishName,
    region: institution.region,
    type: institution.type,
    stages: institution.stages,
    sectors: institution.sectors,
    profileSlug: institution.slug,
    officialUrl: institution.source.url,
    rankings: [],
  });
}

export const institutionDirectory = [...directory.values()].sort((left, right) => {
  const leftRank = Math.min(...left.rankings.map((item) => item.rank ?? 999), 999);
  const rightRank = Math.min(...right.rankings.map((item) => item.rank ?? 999), 999);
  return (
    Number(Boolean(right.rankings.length)) - Number(Boolean(left.rankings.length)) ||
    leftRank - rightRank ||
    left.name.localeCompare(right.name, "zh-CN")
  );
});

export const institutionDirectoryStats = {
  total: institutionDirectory.length,
  china: institutionDirectory.filter((item) => item.region === "中国").length,
  us: institutionDirectory.filter((item) => item.region === "美国").length,
  detailedProfiles: institutionDirectory.filter((item) => item.profileSlug).length,
  rankedRecords: institutionDirectory.reduce(
    (total, item) => total + item.rankings.length,
    0,
  ),
};

export const institutionRankingCategories: InstitutionRankingCategory[] = [
  "早期投资",
  "创业投资",
  "私募股权",
  "国资投资",
  "战略投资者/CVC",
  "并购投资",
  "海外代表",
];

export function getInstitutionRankingEntry(name: string) {
  const normalized =
    name === "深创投"
      ? "深创投集团"
      : name === "高瓴"
        ? "高瓴投资"
        : name;
  return institutionDirectory.find((item) => item.name === normalized);
}
