import fs from "node:fs";
import path from "node:path";

import rawRankingData from "../config/institution_rankings.json";
import rawArticles from "../public/data/articles.json";
import {
  institutionEntities,
  institutionEntityByName,
  institutionEntityRegistryStats,
  resolveArticleInstitutionEntityMatches,
} from "../lib/institution-entity-registry";
import {
  starMarketInvestorAllRecords,
  starMarketInvestorGeneratedAt,
} from "../lib/star-market-investor-data";

const ROOT = path.resolve(import.meta.dirname, "..");
const CAPITAL_EVENT_TYPES = new Set(["融资", "产业投资", "并购", "IPO"]);

type RankingPayload = {
  schemaVersion: number;
  dataVersion: string;
  updatedAt: string;
  sources: { id: string; url: string }[];
  categories: unknown[];
};

type ArticleRecord = {
  id: string;
  title: string;
  summary: string;
  type: string;
  region: string;
  sector: string;
  company?: string;
  companySlug?: string;
  institutions?: string[];
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  publishedAt: string;
  firstSeenAt?: string;
  firstSeenEstimated?: boolean;
  lastVerifiedAt?: string;
  lastVerifiedEstimated?: boolean;
  sourceId?: string;
  source: {
    name: string;
    url: string;
    platform?: string;
    evidenceGrade?: "A" | "B" | "C" | "D";
    evidenceLabel?: string;
    evidencePolicy?: string;
  };
};

type ArticlePayload = {
  generatedAt: string;
  articles: ArticleRecord[];
};

function writeJson(relativePath: string, payload: unknown) {
  const outputPath = path.join(ROOT, relativePath);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function rankingSourceId(sourceUrl: string | undefined, rankingData: RankingPayload) {
  return rankingData.sources.find((source) => source.url === sourceUrl)?.id;
}

function buildEntityLayer(rankingData: RankingPayload) {
  const generatedAt = rankingData.updatedAt
    ? `${rankingData.updatedAt}T00:00:00+00:00`
    : "";
  const entities = institutionEntities.map((entity) => ({
    id: entity.id,
    name: entity.name,
    fullName: entity.fullName,
    aliases: entity.aliases,
    region: entity.directoryEntry.region,
    type: entity.directoryEntry.type,
    stages: entity.directoryEntry.stages,
    sectors: entity.directoryEntry.sectors,
    profileSlug: entity.profileSlug,
    officialUrl: entity.directoryEntry.officialUrl,
    officialDomains: entity.domains,
    rankings: entity.directoryEntry.rankings.map((ranking) => ({
      publisher: ranking.publisher,
      year: ranking.year,
      category: ranking.category,
      title: ranking.title,
      rank: ranking.rank,
      ordered: ranking.ordered,
      sourceId: rankingSourceId(ranking.sourceUrl, rankingData),
      sourceUrl: ranking.sourceUrl,
    })),
    reviewStatus: "reviewed",
    order: entity.order,
  }));

  return {
    schemaVersion: 1,
    dataVersion: rankingData.dataVersion,
    generatedAt,
    provenance: {
      rankingSchemaVersion: rankingData.schemaVersion,
      rankingSourceIds: rankingData.sources.map((source) => source.id),
      aliasManifest: "config/institution_entity_aliases.json",
      profileSource: "lib/catalog-data.ts#institutionCatalog",
    },
    stats: {
      entities: institutionEntityRegistryStats.entities,
      aliases: institutionEntityRegistryStats.aliases,
      officialDomains: institutionEntityRegistryStats.officialDomains,
      china: entities.filter((entity) => entity.region === "中国").length,
      us: entities.filter((entity) => entity.region === "美国").length,
      detailedProfiles: entities.filter((entity) => Boolean(entity.profileSlug)).length,
      rankingRecords: entities.reduce(
        (total, entity) => total + entity.rankings.length,
        0,
      ),
    },
    entities,
  };
}

function buildEventLayer(articlePayload: ArticlePayload) {
  const events = articlePayload.articles.flatMap((article) => {
    const matches = resolveArticleInstitutionEntityMatches(article);
    const scope = matches.length
      ? "institution-event"
      : CAPITAL_EVENT_TYPES.has(article.type)
        ? "capital-event"
        : undefined;
    if (!scope) return [];

    return [
      {
        id: article.id,
        articleId: article.id,
        scope,
        attributionStatus: matches.length ? "attributed" : "unattributed",
        eventType: article.type,
        title: article.title,
        summary: article.summary,
        region: article.region,
        sector: article.sector,
        company: article.company,
        companySlug: article.companySlug,
        publishedAt: article.publishedAt,
        firstSeenAt: article.firstSeenAt,
        firstSeenEstimated: article.firstSeenEstimated,
        lastVerifiedAt: article.lastVerifiedAt,
        lastVerifiedEstimated: article.lastVerifiedEstimated,
        institutionIds: matches.map((match) => match.entity.id),
        institutionNames: matches.map((match) => match.entity.name),
        attributions: matches.map((match) => ({
          institutionId: match.entity.id,
          institutionName: match.entity.name,
          methods: match.methods,
          evidence: match.evidence,
        })),
        sourceId: article.sourceId,
        source: {
          name: article.source.name,
          platform: article.source.platform,
          url: article.source.url,
          evidenceGrade: article.source.evidenceGrade,
          evidenceLabel: article.source.evidenceLabel,
          evidencePolicy: article.source.evidencePolicy,
        },
      },
    ];
  });

  return {
    schemaVersion: 1,
    generatedAt: articlePayload.generatedAt,
    eventCount: events.length,
    institutionEventCount: events.filter(
      (event) => event.scope === "institution-event",
    ).length,
    capitalEventCount: events.filter((event) => event.scope === "capital-event")
      .length,
    attributedInstitutionCount: new Set(
      events.flatMap((event) => event.institutionIds),
    ).size,
    methodology: {
      structuredField: "article.institutions exact reviewed alias match",
      officialDomain: "article source URL matches the institution official domain",
      reviewedAliasText:
        "unique reviewed alias with minimum-length safeguards occurs in normalized article text",
      genericCapitalEvents:
        "financing, industrial investment, M&A and IPO records without a resolved institution remain separate unattributed capital events",
    },
    events,
  };
}

function buildEquityLayer() {
  const rows = starMarketInvestorAllRecords.map((record) => {
    const directoryEntity = record.directoryInstitution
      ? institutionEntityByName(record.directoryInstitution.name)
      : undefined;
    return {
      id: `${record.company.slug}:${record.investor.id}`,
      company: {
        slug: record.company.slug,
        name: record.company.name,
        ticker: record.company.ticker,
        exchange: record.company.exchange,
        sector: record.company.sector,
      },
      investor: {
        candidateId: record.investor.id,
        name: record.investor.name,
        normalizedName: record.investor.normalizedName,
        investorType: record.investor.investorType,
        institutionEntityId: directoryEntity?.id,
        institutionEntityName: directoryEntity?.name,
      },
      holding: {
        preIpoShares: record.investor.preIpoShares,
        preIpoOwnershipPct: record.investor.preIpoOwnershipPct,
      },
      evidence: {
        prospectusTitle: record.company.prospectus.title,
        prospectusUrl: record.company.prospectus.url,
        prospectusSha256: record.company.prospectus.sha256,
        sourcePage: record.investor.sourcePage,
        sourceSection: record.investor.sourceSection,
        excerpt: record.investor.evidence,
      },
      review: {
        key: record.investor.reviewKey,
        status: record.investor.reviewStatus,
        reasons: record.investor.reviewReasons,
        reviewedBy: record.investor.reviewedBy,
        reviewedAt: record.investor.reviewedAt,
        note: record.investor.reviewNote,
        source: record.investor.reviewSource,
      },
      contactPublication: {
        status: record.investor.contactStatus,
        published: Boolean(record.investor.publicContact),
      },
    };
  });

  const relationships = rows.filter((row) => row.review.status === "verified");
  const candidates = rows.filter((row) => row.review.status === "needs_review");
  const rejected = rows.filter((row) => row.review.status === "rejected");

  return {
    schemaVersion: 1,
    generatedAt: starMarketInvestorGeneratedAt,
    verifiedRelationshipCount: relationships.length,
    needsReviewCount: candidates.length,
    rejectedCount: rejected.length,
    publicationRule:
      "Only manifest-backed verified records are authoritative equity relationships; needs-review and rejected extraction rows remain separate audit queues.",
    relationships,
    candidates,
    rejected,
  };
}

const rankingData = rawRankingData as RankingPayload;
const articlePayload = rawArticles as ArticlePayload;

if (rankingData.dataVersion === "migration-pending") {
  throw new Error("institution ranking migration has not completed");
}
if (!rankingData.sources.length || !rankingData.categories.length) {
  throw new Error("institution ranking data is empty");
}

writeJson("public/data/institution_entities.json", buildEntityLayer(rankingData));
writeJson("public/data/institution_events.json", buildEventLayer(articlePayload));
writeJson(
  "public/data/institution_equity_relationships.json",
  buildEquityLayer(),
);

console.log(
  JSON.stringify(
    {
      entities: institutionEntityRegistryStats.entities,
      eventSnapshot: articlePayload.generatedAt,
      equitySnapshot: starMarketInvestorGeneratedAt,
    },
    null,
    2,
  ),
);
