import type { IntelligenceEvent } from "./intelligence-data";
import {
  getArticleInstitutionRelations,
  type InstitutionActivityRelation,
} from "./institution-activity";
import { canonicalHotnessKey } from "./hotness";

export const INSTITUTION_HOT_WEIGHTS = {
  crawlerActivity: 0.85,
  localAttention: 0.15,
  halfLifeDays: 45,
  directRelation: 1,
  portfolioRelation: 0.35,
} as const;

export type InstitutionArticleEngagement = {
  opens: number;
  favorite: boolean;
  shares: number;
};

export type InstitutionHotArticle = IntelligenceEvent & {
  qualityScore?: number;
  qualityStatus?: "高可信" | "可用" | "低可信";
  relatedSources?: { url: string }[];
  duplicateCount?: number;
  eventClusterId?: string;
};

export type RankedInstitutionActivity = {
  relation: InstitutionActivityRelation;
  score: number;
  crawlerScore: number;
  attentionScore: number;
  rawCrawlerScore: number;
  rawAttentionScore: number;
  articleCount: number;
  directArticleCount: number;
  portfolioArticleCount: number;
  sourceCount: number;
  opens: number;
  favoriteArticles: number;
  shares: number;
  latestActivity?: string;
};

const DAY_MS = 24 * 60 * 60 * 1000;

const sourceWeights: Record<IntelligenceEvent["source"]["level"], number> = {
  官方披露: 1.18,
  监管文件: 1.22,
  原始材料: 1.12,
  数据库记录: 0.96,
  媒体报道: 0.86,
  待交叉验证: 0.58,
};

const eventWeights: Record<IntelligenceEvent["type"], number> = {
  融资: 1.35,
  产业投资: 1.4,
  并购: 1.34,
  IPO: 1.28,
  监管文件: 1.18,
  财报: 1.1,
  商业进展: 1.03,
  产品发布: 0.92,
  技术突破: 0.96,
  公司动态: 0.82,
  政策: 0.76,
  论文: 0.72,
  人物观点: 0.62,
};

function clampScore(value: number | undefined, fallback: number): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.max(0, Math.min(100, Number(value)));
}

function publishedTimestamp(value: string): number {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function freshnessWeight(publishedAt: string, asOf: number): number {
  const timestamp = publishedTimestamp(publishedAt);
  if (!timestamp) return 0.08;
  const ageDays = Math.max(0, (asOf - timestamp) / DAY_MS);
  return Math.max(
    0.08,
    2 ** (-ageDays / INSTITUTION_HOT_WEIGHTS.halfLifeDays),
  );
}

function confirmationWeight(article: InstitutionHotArticle): number {
  const relatedSourceCount = new Set(
    (article.relatedSources ?? [])
      .map((source) => canonicalHotnessKey(source.url))
      .filter(Boolean),
  ).size;
  const duplicateCount = Math.max(0, article.duplicateCount ?? 0);
  const confirmations = Math.min(4, Math.max(relatedSourceCount, duplicateCount));
  return 1 + confirmations * 0.08;
}

function crawlerArticleScore(
  article: InstitutionHotArticle,
  relationWeight: number,
  asOf: number,
): number {
  const importance = clampScore(article.importance, 50);
  const quality = clampScore(article.qualityScore, importance);
  const evidenceQuality = 0.55 * importance + 0.45 * quality;
  const qualityWeight = 0.45 + 0.55 * (evidenceQuality / 100);
  return (
    relationWeight *
    freshnessWeight(article.publishedAt, asOf) *
    qualityWeight *
    sourceWeights[article.source.level] *
    eventWeights[article.type] *
    confirmationWeight(article)
  );
}

function safeCount(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
}

function attentionArticleScore(signal?: InstitutionArticleEngagement): number {
  if (!signal) return 0;
  const opens = safeCount(signal.opens);
  const shares = safeCount(signal.shares);
  return (
    Math.log1p(opens) +
    Number(signal.favorite) * 5 +
    Math.log1p(shares) * 8
  );
}

function eventClusterKey(article: InstitutionHotArticle): string {
  return (
    article.eventClusterId ||
    canonicalHotnessKey(article.source.url) ||
    article.id
  );
}

function normalizeLog(value: number, maximum: number): number {
  if (maximum <= 0 || value <= 0) return 0;
  return Math.log1p(value) / Math.log1p(maximum);
}

function engagementFor(
  article: InstitutionHotArticle,
  engagementByHref: ReadonlyMap<string, InstitutionArticleEngagement>,
): InstitutionArticleEngagement | undefined {
  return engagementByHref.get(canonicalHotnessKey(article.source.url));
}

function buildRawInstitutionActivity(
  relation: InstitutionActivityRelation,
  engagementByHref: ReadonlyMap<string, InstitutionArticleEngagement>,
  asOf: number,
): Omit<RankedInstitutionActivity, "score" | "crawlerScore" | "attentionScore"> {
  const directIds = new Set(relation.directEvents.map((article) => article.id));
  const clusters = new Map<
    string,
    {
      crawler: number;
      attention: number;
      article: InstitutionHotArticle;
      direct: boolean;
      opens: number;
      favorite: boolean;
      shares: number;
    }
  >();

  for (const rawArticle of relation.relatedEvents) {
    const article = rawArticle as InstitutionHotArticle;
    const direct = directIds.has(article.id);
    const relationWeight = direct
      ? INSTITUTION_HOT_WEIGHTS.directRelation
      : INSTITUTION_HOT_WEIGHTS.portfolioRelation;
    const signal = engagementFor(article, engagementByHref);
    const key = eventClusterKey(article);
    const candidate = {
      crawler: crawlerArticleScore(article, relationWeight, asOf),
      attention: attentionArticleScore(signal) * relationWeight,
      article,
      direct,
      opens: safeCount(signal?.opens ?? 0),
      favorite: signal?.favorite === true,
      shares: safeCount(signal?.shares ?? 0),
    };
    const current = clusters.get(key);
    if (
      !current ||
      candidate.crawler > current.crawler ||
      (candidate.crawler === current.crawler && candidate.attention > current.attention)
    ) {
      clusters.set(key, candidate);
    }
  }

  const clusterValues = [...clusters.values()];
  const sourceCount = new Set(
    clusterValues
      .map((item) => canonicalHotnessKey(item.article.source.url))
      .filter(Boolean),
  ).size;
  const sourceDiversityWeight = 1 + Math.min(5, Math.max(0, sourceCount - 1)) * 0.06;
  const rawCrawlerScore =
    clusterValues.reduce((total, item) => total + item.crawler, 0) *
    sourceDiversityWeight;
  const rawAttentionScore = clusterValues.reduce(
    (total, item) => total + item.attention,
    0,
  );
  const directArticleCount = clusterValues.filter((item) => item.direct).length;
  const portfolioArticleCount = clusterValues.length - directArticleCount;
  const latestActivity = clusterValues
    .map((item) => item.article.publishedAt)
    .sort((left, right) => right.localeCompare(left))[0];

  return {
    relation,
    rawCrawlerScore,
    rawAttentionScore,
    articleCount: clusterValues.length,
    directArticleCount,
    portfolioArticleCount,
    sourceCount,
    opens: clusterValues.reduce((total, item) => total + item.opens, 0),
    favoriteArticles: clusterValues.filter((item) => item.favorite).length,
    shares: clusterValues.reduce((total, item) => total + item.shares, 0),
    latestActivity,
  };
}

export function rankInstitutionsByActivity(
  articles: InstitutionHotArticle[],
  engagementByHref: ReadonlyMap<string, InstitutionArticleEngagement> = new Map(),
  asOf: number = Date.now(),
): RankedInstitutionActivity[] {
  const raw = getArticleInstitutionRelations(articles).map((relation) =>
    buildRawInstitutionActivity(relation, engagementByHref, asOf),
  );
  const maximumCrawler = Math.max(
    0,
    ...raw.map((item) => item.rawCrawlerScore),
  );
  const maximumAttention = Math.max(
    0,
    ...raw.map((item) => item.rawAttentionScore),
  );
  const hasAttention = maximumAttention > 0;

  return raw
    .map<RankedInstitutionActivity>((item) => {
      const crawlerScore = normalizeLog(item.rawCrawlerScore, maximumCrawler);
      const attentionScore = normalizeLog(
        item.rawAttentionScore,
        maximumAttention,
      );
      const combined = hasAttention
        ? INSTITUTION_HOT_WEIGHTS.crawlerActivity * crawlerScore +
          INSTITUTION_HOT_WEIGHTS.localAttention * attentionScore
        : crawlerScore;
      return {
        ...item,
        crawlerScore: Math.round(crawlerScore * 100),
        attentionScore: Math.round(attentionScore * 100),
        score: Math.round(combined * 100),
      };
    })
    .sort(
      (left, right) =>
        right.score - left.score ||
        right.crawlerScore - left.crawlerScore ||
        right.directArticleCount - left.directArticleCount ||
        right.articleCount - left.articleCount ||
        (right.latestActivity ?? "").localeCompare(left.latestActivity ?? "") ||
        left.relation.institution.name.localeCompare(
          right.relation.institution.name,
          "zh-CN",
        ),
    );
}
