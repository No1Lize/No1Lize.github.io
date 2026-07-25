import entitySeedConfig from "../config/tracking_entity_seeds.json";
import {
  isKnownTrackingSeedTerm,
  isTrackingTermAllowedForSector,
  trackingSectorSeedTerms,
  trackingSectorsMatch,
} from "@/lib/tracking-sector-policy";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export type TrackingRecommendation = {
  value: string;
  label: string;
  reason: string;
  score: number;
};

export type TrackingSourceRecommendation = TrackingRecommendation & {
  source: {
    name: string;
    url: string;
    sourceType: "listing-search";
    sourceCategory: "company" | "media" | "person";
    region: "中国" | "美国" | "全球";
    sector: string;
    company: string;
    ticker: string;
    keywords: string[];
  };
};

export type TrackingRecommendationSet = {
  keywords: TrackingRecommendation[];
  people: TrackingRecommendation[];
  companies: TrackingRecommendation[];
  sources: TrackingSourceRecommendation[];
};

type ExistingTrackingValues = {
  keywords?: string[];
  people?: string[];
  companies?: string[];
  sources?: string[];
};

type EntitySeedConfig = {
  schemaVersion: number;
  seedAcronyms: string[];
  globalTerms: string[];
  sectorTerms: Record<string, string[]>;
};

type DynamicCandidate = {
  label: string;
  articles: Map<string, LiveIntelligenceEvent>;
  sources: Set<string>;
  titleMentions: number;
  authoritativeMentions: number;
  strongShape: boolean;
};

const ENTITY_SEEDS = entitySeedConfig as EntitySeedConfig;
const SEED_ACRONYMS = new Set(ENTITY_SEEDS.seedAcronyms);

const GENERIC_COMPANIES = new Set([
  "",
  "AI 研究",
  "科技产业",
  "未识别",
  "未分类",
  "行业",
  "产业",
  "研究机构",
  "媒体",
]);

const GENERIC_TERMS = new Set([
  "ai",
  "agi",
  "ml",
  "llm",
  "us",
  "uk",
  "cn",
  "eu",
  "rt",
  "k3",
  "stem",
  "ceo",
  "cto",
  "cfo",
  "coo",
  "vp",
  "the",
  "new",
  "this",
  "that",
  "with",
  "from",
  "into",
  "using",
  "based",
  "research",
  "report",
  "study",
  "update",
  "release",
  "launch",
  "model",
  "models",
  "system",
  "platform",
  "company",
  "technology",
  "tech",
  "news",
  "人工智能",
  "技术",
  "科技",
  "公司",
  "企业",
  "行业",
  "产业",
  "研究",
  "论文",
  "新闻",
  "资讯",
  "产品",
  "项目",
  "模型",
  "系统",
  "平台",
  "发布",
  "市场",
  "应用",
]);

const GENERIC_PERSON_LABELS = new Set([
  "ceo",
  "cto",
  "cfo",
  "coo",
  "founder",
  "researcher",
  "scientist",
  "author",
  "team",
  "staff",
  "editor",
  "研究员",
  "科学家",
  "创始人",
  "作者",
  "团队",
]);

const TECH_CONTEXT_PATTERN =
  /\b(?:model|models|architecture|framework|protocol|benchmark|dataset|algorithm|agent|agents|inference|training|reasoning|multimodal|token|context|chip|accelerator|memory|robot|robotics|battery|semiconductor|quantum|protein|genome|satellite|rocket|compiler|runtime)\b|模型|架构|框架|协议|基准|数据集|算法|智能体|推理|训练|多模态|芯片|加速器|机器人|电池|半导体|量子|蛋白质|基因|卫星|火箭|编译器|运行时/i;

const DYNAMIC_PATTERNS = [
  /\b[A-Z][A-Z0-9]{2,9}(?:-[A-Z0-9]{1,8})*\b/g,
  /\b[A-Za-z]{2,}[0-9][A-Za-z0-9.-]*\b/g,
  /\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b/g,
  /\b[A-Z][a-z]{1,15}(?:[A-Z][A-Za-z0-9]{1,15})+\b/g,
  /\b[A-Z][A-Za-z0-9-]{2,20}\s+(?:Transformer|Model|Network|Protocol|Framework|Benchmark|Dataset|Algorithm|Architecture|Agent|Runtime|Compiler)\b/g,
];

const BLOCKED_RECOMMENDATION_HOSTS = new Set([
  "x.com",
  "twitter.com",
  "syndication.twitter.com",
  "sec.gov",
  "www.sec.gov",
  "openalex.org",
  "api.openalex.org",
  "arxiv.org",
  "export.arxiv.org",
  "bing.com",
  "www.bing.com",
  "google.com",
  "www.google.com",
]);

function normalize(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim();
}

function normalizedKey(value: string): string {
  return normalize(value).toLocaleLowerCase("zh-CN");
}

function daysAgo(value: string): number {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return 365;
  return Math.max(0, (Date.now() - timestamp) / 86_400_000);
}

function urlHost(value: string): string {
  try {
    return new URL(value).hostname.toLocaleLowerCase("en-US").replace(/^www\./, "");
  } catch {
    return "";
  }
}

function articleText(article: LiveIntelligenceEvent): string {
  return `${article.title} ${article.summary} ${article.company}`.normalize("NFKC");
}

function sourceWeight(article: LiveIntelligenceEvent): number {
  switch (article.source.level) {
    case "官方披露":
    case "原始材料":
    case "监管文件":
      return 1;
    case "数据库记录":
      return 0.8;
    case "媒体报道":
      return 0.65;
    default:
      return 0.35;
  }
}

function scoreArticles(items: LiveIntelligenceEvent[]): number {
  if (!items.length) return 0;
  const uniqueSources = new Set(items.map((item) => item.source.url)).size;
  const importance =
    items.reduce((sum, item) => sum + item.importance, 0) / items.length;
  const quality =
    items.reduce((sum, item) => sum + (item.qualityScore ?? 55), 0) /
    items.length;
  const authority =
    items.reduce((sum, item) => sum + sourceWeight(item), 0) / items.length;
  const recent = items.filter((item) => daysAgo(item.publishedAt) <= 30).length;
  return Math.round(
    items.length * 10 +
      uniqueSources * 7 +
      importance * 0.22 +
      quality * 0.18 +
      authority * 10 +
      recent * 4,
  );
}

function reasonFor(items: LiveIntelligenceEvent[]): string {
  const recent = items.filter((item) => daysAgo(item.publishedAt) <= 30).length;
  const authoritative = items.filter((item) => sourceWeight(item) >= 0.8).length;
  if (recent >= 2) return `近30天在 ${recent} 条相关情报中出现`;
  if (authoritative > 0) return `被 ${authoritative} 条高可信来源提及`;
  return `在 ${items.length} 条当前赛道情报中出现`;
}

function isSeedKeyword(value: string): boolean {
  const term = normalize(value);
  const key = normalizedKey(term);
  if (!term || GENERIC_TERMS.has(key)) return false;
  if (/^[A-Za-z]{1,2}$/.test(term)) return false;
  if (/^[A-Z0-9-]+$/.test(term) && !SEED_ACRONYMS.has(term)) return false;
  return /[A-Za-z0-9\u3400-\u9fff]/.test(term);
}

function isPotentialDynamicTerm(value: string): boolean {
  const term = normalize(value).replace(
    /^[\s.,:;()[\]{}]+|[\s.,:;()[\]{}]+$/g,
    "",
  );
  const key = normalizedKey(term);
  if (!term || term.length < 3 || term.length > 40) return false;
  if (GENERIC_TERMS.has(key)) return false;
  if (/^\d+$/.test(term) || /https?:|www\.|@/.test(term)) return false;
  if (/^[A-Za-z]{1,2}$/.test(term)) return false;
  return /[A-Za-z]/.test(term);
}

function hasStrongEntityShape(value: string): boolean {
  const term = normalize(value);
  return (
    /^[A-Z][A-Z0-9]{2,9}(?:-[A-Z0-9]{1,8})*$/.test(term) ||
    /\d/.test(term) ||
    /-/.test(term) ||
    /[a-z][A-Z]/.test(term) ||
    /\s(?:Transformer|Model|Network|Protocol|Framework|Benchmark|Dataset|Algorithm|Architecture|Agent|Runtime|Compiler)$/.test(
      term,
    )
  );
}

function isLikelyPersonName(value: string): boolean {
  const label = normalize(value);
  const key = normalizedKey(label);
  if (
    !label ||
    GENERIC_PERSON_LABELS.has(key) ||
    /\d|https?:|www\./i.test(label)
  ) {
    return false;
  }
  if (/^[\u3400-\u9fff·•\s]{2,16}$/.test(label)) return true;
  const words = label.split(/\s+/).filter(Boolean);
  return (
    words.length >= 2 &&
    words.length <= 5 &&
    words.every((word) => /^[A-Za-z][A-Za-z'.-]*$/.test(word)) &&
    !words.every((word) => word === word.toUpperCase())
  );
}

function mentionHasTechnicalContext(text: string, label: string): boolean {
  const lowerText = text.toLocaleLowerCase("en-US");
  const lowerLabel = label.toLocaleLowerCase("en-US");
  let offset = 0;
  while (offset < lowerText.length) {
    const index = lowerText.indexOf(lowerLabel, offset);
    if (index < 0) return false;
    const window = text.slice(
      Math.max(0, index - 90),
      index + label.length + 90,
    );
    if (TECH_CONTEXT_PATTERN.test(window)) return true;
    offset = index + Math.max(1, label.length);
  }
  return false;
}

function structuredEntityKeys(
  articles: LiveIntelligenceEvent[],
): Set<string> {
  const values: string[] = [];
  for (const article of articles) {
    values.push(article.company, article.source.name, article.source.platform ?? "");
    values.push(...(article.authors ?? []), ...(article.institutions ?? []));
  }
  return new Set(values.map(normalizedKey).filter(Boolean));
}

function extractedDynamicTerms(
  article: LiveIntelligenceEvent,
): Array<{ label: string; titleMention: boolean; strongShape: boolean }> {
  const found = new Map<
    string,
    { label: string; titleMention: boolean; strongShape: boolean }
  >();
  const collect = (text: string, titleMention: boolean, pattern: RegExp) => {
    for (const match of text.match(pattern) ?? []) {
      const label = normalize(match);
      const key = normalizedKey(label);
      if (!isPotentialDynamicTerm(label)) continue;
      const current = found.get(key);
      found.set(key, {
        label: current?.label ?? label,
        titleMention: Boolean(current?.titleMention || titleMention),
        strongShape: Boolean(
          current?.strongShape || hasStrongEntityShape(label),
        ),
      });
    }
  };

  for (const pattern of DYNAMIC_PATTERNS) {
    collect(article.title, true, pattern);
    collect(article.summary, false, pattern);
  }
  return [...found.values()];
}

function dynamicKeywordCandidates(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: Set<string>,
): TrackingRecommendation[] {
  const blockedEntities = structuredEntityKeys(articles);
  const candidates = new Map<string, DynamicCandidate>();

  for (const article of articles) {
    const text = `${article.title} ${article.summary}`;
    for (const extracted of extractedDynamicTerms(article)) {
      const key = normalizedKey(extracted.label);
      if (existing.has(key) || blockedEntities.has(key)) continue;
      if (
        isKnownTrackingSeedTerm(extracted.label) &&
        !isTrackingTermAllowedForSector(extracted.label, selectedSector)
      ) {
        continue;
      }
      if (!mentionHasTechnicalContext(text, extracted.label)) continue;

      const current = candidates.get(key) ?? {
        label: extracted.label,
        articles: new Map<string, LiveIntelligenceEvent>(),
        sources: new Set<string>(),
        titleMentions: 0,
        authoritativeMentions: 0,
        strongShape: false,
      };
      if (!current.articles.has(article.id)) {
        current.articles.set(article.id, article);
        if (extracted.titleMention) current.titleMentions += 1;
        if (sourceWeight(article) >= 0.8) {
          current.authoritativeMentions += 1;
        }
      }
      const host = urlHost(article.source.url);
      if (host) current.sources.add(host);
      current.strongShape ||= extracted.strongShape;
      candidates.set(key, current);
    }
  }

  return [...candidates.values()]
    .filter((candidate) => {
      const items = [...candidate.articles.values()];
      const articleCount = items.length;
      const sourceCount = candidate.sources.size;
      const averageQuality =
        items.reduce((sum, item) => sum + (item.qualityScore ?? 55), 0) /
        articleCount;
      const averageImportance =
        items.reduce((sum, item) => sum + item.importance, 0) / articleCount;

      if (
        articleCount >= 2 &&
        sourceCount >= 2 &&
        candidate.titleMentions >= 1
      ) {
        return true;
      }
      if (
        articleCount >= 3 &&
        candidate.authoritativeMentions >= 1 &&
        candidate.titleMentions >= 1
      ) {
        return true;
      }
      return (
        articleCount === 1 &&
        candidate.strongShape &&
        candidate.authoritativeMentions === 1 &&
        candidate.titleMentions === 1 &&
        averageQuality >= 85 &&
        averageImportance >= 80
      );
    })
    .map((candidate) => {
      const items = [...candidate.articles.values()];
      return {
        value: candidate.label,
        label: candidate.label,
        reason:
          items.length === 1
            ? "动态发现：高质量官方首发中的新技术实体"
            : `动态发现：${items.length} 条情报、${candidate.sources.size} 个独立来源`,
        score: scoreArticles(items) + 18 + candidate.sources.size * 5,
      };
    })
    .sort(
      (left, right) =>
        right.score - left.score || left.label.localeCompare(right.label),
    )
    .slice(0, 18);
}

function keywordCandidates(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: Set<string>,
): TrackingRecommendation[] {
  const candidates = new Map<
    string,
    { label: string; articles: LiveIntelligenceEvent[] }
  >();
  const terms = new Set(trackingSectorSeedTerms(selectedSector));

  for (const article of articles) {
    const text = articleText(article).toLocaleLowerCase("zh-CN");
    for (const term of terms) {
      const key = normalizedKey(term);
      if (!isSeedKeyword(term) || existing.has(key) || !text.includes(key)) {
        continue;
      }
      const current = candidates.get(key) ?? { label: term, articles: [] };
      current.articles.push(article);
      candidates.set(key, current);
    }
  }

  const seeded = [...candidates.values()]
    .map((candidate) => ({
      value: candidate.label,
      label: candidate.label,
      reason: reasonFor(candidate.articles),
      score: scoreArticles(candidate.articles),
    }))
    .sort(
      (left, right) =>
        right.score - left.score || left.label.localeCompare(right.label),
    );

  const merged = new Map<string, TrackingRecommendation>();
  for (const item of [
    ...seeded,
    ...dynamicKeywordCandidates(articles, selectedSector, existing),
  ]) {
    const key = normalizedKey(item.value);
    const current = merged.get(key);
    if (!current || item.score > current.score) merged.set(key, item);
  }

  const ranked = [...merged.values()]
    .sort(
      (left, right) =>
        right.score - left.score || left.label.localeCompare(right.label),
    )
    .slice(0, 18);

  if (ranked.length >= 6) return ranked;
  for (const term of trackingSectorSeedTerms(selectedSector)) {
    const key = normalizedKey(term);
    if (
      !isSeedKeyword(term) ||
      existing.has(key) ||
      ranked.some((item) => normalizedKey(item.value) === key)
    ) {
      continue;
    }
    ranked.push({
      value: term,
      label: term,
      reason: "赛道种子配置中的高相关技术实体",
      score: 1,
    });
    if (ranked.length >= 12) break;
  }
  return ranked;
}

function xHandle(article: LiveIntelligenceEvent): string {
  const urlMatch = article.source.url.match(
    /(?:x|twitter)\.com\/([A-Za-z0-9_]{1,15})(?:\/|$)/i,
  );
  if (urlMatch) return urlMatch[1];
  const sourceId = article.sourceId ?? "";
  const idMatch = sourceId.match(/^(?:user-)?x-([a-z0-9-]+)$/i);
  return idMatch ? idMatch[1].replace(/-/g, "_") : "";
}

function peopleCandidates(
  articles: LiveIntelligenceEvent[],
  existing: Set<string>,
): TrackingRecommendation[] {
  const groups = new Map<
    string,
    { label: string; articles: LiveIntelligenceEvent[] }
  >();

  for (const article of articles) {
    const isX =
      article.source.platform === "X" ||
      /^(?:user-)?x-/i.test(article.sourceId ?? "");
    if (isX) {
      const displayName = normalize(
        article.source.name.replace(/\s+on X$/i, ""),
      );
      const handle = xHandle(article);
      const label = handle ? `${displayName || handle} @${handle}` : displayName;
      const key = normalizedKey(label);
      if (
        label &&
        !existing.has(key) &&
        (Boolean(handle) || isLikelyPersonName(displayName))
      ) {
        const current = groups.get(key) ?? { label, articles: [] };
        current.articles.push(article);
        groups.set(key, current);
      }
    }

    for (const author of article.authors ?? []) {
      const label = normalize(author);
      const key = normalizedKey(label);
      if (!isLikelyPersonName(label) || existing.has(key)) continue;
      const current = groups.get(key) ?? { label, articles: [] };
      current.articles.push(article);
      groups.set(key, current);
    }
  }

  return [...groups.values()]
    .filter(
      (candidate) =>
        candidate.label.includes("@") || candidate.articles.length >= 2,
    )
    .map((candidate) => ({
      value: candidate.label,
      label: candidate.label,
      reason: reasonFor(candidate.articles),
      score:
        scoreArticles(candidate.articles) +
        (candidate.label.includes("@") ? 12 : 0),
    }))
    .sort(
      (left, right) =>
        right.score - left.score || left.label.localeCompare(right.label),
    )
    .slice(0, 18);
}

function companyCandidates(
  articles: LiveIntelligenceEvent[],
  existing: Set<string>,
): TrackingRecommendation[] {
  const groups = new Map<
    string,
    { label: string; articles: LiveIntelligenceEvent[] }
  >();
  for (const article of articles) {
    const label = normalize(article.company);
    const key = normalizedKey(label);
    if (!label || GENERIC_COMPANIES.has(label) || existing.has(key)) continue;
    const current = groups.get(key) ?? { label, articles: [] };
    current.articles.push(article);
    groups.set(key, current);
  }

  return [...groups.values()]
    .map((candidate) => ({
      value: candidate.label,
      label: candidate.label,
      reason: reasonFor(candidate.articles),
      score: scoreArticles(candidate.articles),
    }))
    .sort(
      (left, right) =>
        right.score - left.score || left.label.localeCompare(right.label),
    )
    .slice(0, 18);
}

function mostCommon<T extends string>(values: T[], fallback: T): T {
  const counts = new Map<T, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  return (
    [...counts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ??
    fallback
  );
}

function sourceCandidates(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existingUrls: string[],
): TrackingSourceRecommendation[] {
  const existingHosts = new Set(existingUrls.map(urlHost).filter(Boolean));
  const groups = new Map<string, LiveIntelligenceEvent[]>();

  for (const article of articles) {
    const host = urlHost(article.source.url);
    if (
      !host ||
      existingHosts.has(host) ||
      BLOCKED_RECOMMENDATION_HOSTS.has(host) ||
      article.source.platform === "X" ||
      article.source.level === "待交叉验证"
    ) {
      continue;
    }
    const group = groups.get(host) ?? [];
    group.push(article);
    groups.set(host, group);
  }

  return [...groups.entries()]
    .filter(
      ([, items]) =>
        items.length >= 2 || items.some((item) => sourceWeight(item) >= 1),
    )
    .map(([host, items]) => {
      const representative = [...items].sort(
        (left, right) =>
          sourceWeight(right) - sourceWeight(left) ||
          right.importance - left.importance,
      )[0];
      const company = representative.company;
      const isCompanySource =
        sourceWeight(representative) >= 1 &&
        Boolean(company) &&
        !GENERIC_COMPANIES.has(company);
      const category: TrackingSourceRecommendation["source"]["sourceCategory"] =
        isCompanySource ? "company" : "media";
      const sourceName = normalize(
        representative.source.name || representative.source.platform || host,
      );
      const name = isCompanySource ? `${company} 官方来源` : sourceName || host;
      const region = mostCommon(
        items.map((item) => item.region),
        "全球" as const,
      );
      const authoritative = items.filter(
        (item) => sourceWeight(item) >= 0.8,
      ).length;
      const reason = `${items.length} 条当前赛道情报 · ${authoritative} 条高可信记录`;
      const url = `https://${host}/`;
      return {
        value: url,
        label: name,
        reason,
        score: scoreArticles(items) + authoritative * 5,
        source: {
          name,
          url,
          sourceType: "listing-search" as const,
          sourceCategory: category,
          region,
          sector: selectedSector,
          company: isCompanySource ? company : "",
          ticker: "",
          keywords: [
            ...new Set(
              [isCompanySource ? company : "", selectedSector].filter(Boolean),
            ),
          ],
        },
      };
    })
    .sort(
      (left, right) =>
        right.score - left.score || left.label.localeCompare(right.label),
    )
    .slice(0, 12);
}

export function recommendTrackingAdditions(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: ExistingTrackingValues = {},
): TrackingRecommendationSet {
  const sectorArticles = articles.filter((article) =>
    trackingSectorsMatch(article.sector, selectedSector),
  );
  const keywordSet = new Set((existing.keywords ?? []).map(normalizedKey));
  const peopleSet = new Set((existing.people ?? []).map(normalizedKey));
  const companySet = new Set((existing.companies ?? []).map(normalizedKey));

  return {
    keywords: keywordCandidates(sectorArticles, selectedSector, keywordSet),
    people: peopleCandidates(sectorArticles, peopleSet),
    companies: companyCandidates(sectorArticles, companySet),
    sources: sourceCandidates(
      sectorArticles,
      selectedSector,
      existing.sources ?? [],
    ),
  };
}
