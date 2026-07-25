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

const APPROVED_ACRONYMS = new Set(["VLA", "MCP", "RAG", "HBM"]);

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

const GLOBAL_TECH_TERMS = [
  "AI Agent",
  "Agentic AI",
  "VLA",
  "MCP",
  "RAG",
  "多模态",
  "推理模型",
  "世界模型",
  "代码智能体",
  "长上下文",
  "函数调用",
  "强化学习",
  "合成数据",
  "模型蒸馏",
  "端侧模型",
  "具身智能",
  "人形机器人",
  "灵巧手",
  "自动驾驶",
  "固态电池",
  "钠离子电池",
  "硅光",
  "Chiplet",
  "先进封装",
  "HBM",
  "量子纠错",
  "容错量子计算",
  "基因编辑",
  "蛋白质设计",
  "商业航天",
  "可回收火箭",
  "卫星互联网",
  "核聚变",
  "低空经济",
];

const SECTOR_FALLBACKS: Record<string, string[]> = {
  "ai / agi": ["AI Agent", "多模态", "推理模型", "MCP", "长上下文", "代码智能体"],
  机器人: ["VLA", "具身智能", "世界模型", "人形机器人", "灵巧手", "强化学习"],
  半导体: ["Chiplet", "先进封装", "HBM", "硅光", "端侧模型"],
  新能源: ["固态电池", "钠离子电池", "储能", "电池回收", "光伏钙钛矿"],
  生物科技: ["基因编辑", "蛋白质设计", "AI制药", "细胞治疗", "合成生物学"],
  量子计算: ["量子纠错", "容错量子计算", "量子芯片", "量子网络"],
  商业航天: ["可回收火箭", "卫星互联网", "低轨卫星", "商业发射"],
  新材料: ["钙钛矿", "碳纤维", "超材料", "高温超导"],
  智能制造: ["工业机器人", "数字孪生", "机器视觉", "柔性制造"],
};

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

function sectorMatches(articleSector: string, selectedSector: string): boolean {
  const article = normalizedKey(articleSector);
  const selected = normalizedKey(selectedSector);
  if (!article || !selected) return false;
  return article === selected || article.includes(selected) || selected.includes(article);
}

function articleText(article: LiveIntelligenceEvent): string {
  return `${article.title} ${article.summary} ${article.company}`.normalize("NFKC");
}

function isMeaningfulKeyword(value: string): boolean {
  const term = normalize(value);
  const key = normalizedKey(term);
  if (!term || GENERIC_TERMS.has(key)) return false;
  if (/^[A-Za-z]{1,2}$/.test(term)) return false;
  if (/^[A-Z0-9-]+$/.test(term) && !APPROVED_ACRONYMS.has(term)) return false;
  return /[A-Za-z0-9\u3400-\u9fff]/.test(term);
}

function isLikelyPersonName(value: string): boolean {
  const label = normalize(value);
  const key = normalizedKey(label);
  if (!label || GENERIC_PERSON_LABELS.has(key) || /\d|https?:|www\./i.test(label)) {
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
  const importance = items.reduce((sum, item) => sum + item.importance, 0) / items.length;
  const quality =
    items.reduce((sum, item) => sum + (item.qualityScore ?? 55), 0) / items.length;
  const authority = items.reduce((sum, item) => sum + sourceWeight(item), 0) / items.length;
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

function keywordCandidates(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: Set<string>,
): TrackingRecommendation[] {
  const candidates = new Map<string, { label: string; articles: LiveIntelligenceEvent[] }>();
  const terms = new Set([
    ...GLOBAL_TECH_TERMS,
    ...(SECTOR_FALLBACKS[normalizedKey(selectedSector)] ?? []),
  ]);

  for (const article of articles) {
    const text = articleText(article).toLocaleLowerCase("zh-CN");
    for (const term of terms) {
      const key = normalizedKey(term);
      if (
        !isMeaningfulKeyword(term) ||
        existing.has(key) ||
        !text.includes(key)
      ) {
        continue;
      }
      const current = candidates.get(key) ?? { label: term, articles: [] };
      current.articles.push(article);
      candidates.set(key, current);
    }
  }

  const ranked = [...candidates.entries()]
    .map(([key, candidate]) => ({
      value: candidate.label,
      label: candidate.label,
      reason: reasonFor(candidate.articles),
      score: scoreArticles(candidate.articles),
      key,
    }))
    .sort((left, right) => right.score - left.score || left.label.localeCompare(right.label))
    .slice(0, 18)
    .map(({ key: _key, ...item }) => item);

  if (ranked.length >= 6) return ranked;
  const fallback = SECTOR_FALLBACKS[normalizedKey(selectedSector)] ?? [];
  for (const term of fallback) {
    const key = normalizedKey(term);
    if (
      !isMeaningfulKeyword(term) ||
      existing.has(key) ||
      ranked.some((item) => normalizedKey(item.value) === key)
    ) {
      continue;
    }
    ranked.push({
      value: term,
      label: term,
      reason: "赛道技术词表中的高相关实体",
      score: 1,
    });
    if (ranked.length >= 12) break;
  }
  return ranked;
}

function xHandle(article: LiveIntelligenceEvent): string {
  const urlMatch = article.source.url.match(/(?:x|twitter)\.com\/([A-Za-z0-9_]{1,15})(?:\/|$)/i);
  if (urlMatch) return urlMatch[1];
  const sourceId = article.sourceId ?? "";
  const idMatch = sourceId.match(/^(?:user-)?x-([a-z0-9-]+)$/i);
  return idMatch ? idMatch[1].replace(/-/g, "_") : "";
}

function peopleCandidates(
  articles: LiveIntelligenceEvent[],
  existing: Set<string>,
): TrackingRecommendation[] {
  const groups = new Map<string, { label: string; articles: LiveIntelligenceEvent[] }>();

  for (const article of articles) {
    const isX = article.source.platform === "X" || /^(?:user-)?x-/i.test(article.sourceId ?? "");
    if (isX) {
      const displayName = normalize(article.source.name.replace(/\s+on X$/i, ""));
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
    .filter((candidate) => candidate.label.includes("@") || candidate.articles.length >= 2)
    .map((candidate) => ({
      value: candidate.label,
      label: candidate.label,
      reason: reasonFor(candidate.articles),
      score: scoreArticles(candidate.articles) + (candidate.label.includes("@") ? 12 : 0),
    }))
    .sort((left, right) => right.score - left.score || left.label.localeCompare(right.label))
    .slice(0, 18);
}

function companyCandidates(
  articles: LiveIntelligenceEvent[],
  existing: Set<string>,
): TrackingRecommendation[] {
  const groups = new Map<string, { label: string; articles: LiveIntelligenceEvent[] }>();
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
    .sort((left, right) => right.score - left.score || left.label.localeCompare(right.label))
    .slice(0, 18);
}

function urlHost(value: string): string {
  try {
    return new URL(value).hostname.toLocaleLowerCase("en-US").replace(/^www\./, "");
  } catch {
    return "";
  }
}

function mostCommon<T extends string>(values: T[], fallback: T): T {
  const counts = new Map<T, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? fallback;
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
    .filter(([, items]) => items.length >= 2 || items.some((item) => sourceWeight(item) >= 1))
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
      const name = isCompanySource
        ? `${company} 官方来源`
        : sourceName || host;
      const region = mostCommon(
        items.map((item) => item.region),
        "全球" as const,
      );
      const authoritative = items.filter((item) => sourceWeight(item) >= 0.8).length;
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
          keywords: [...new Set([isCompanySource ? company : "", selectedSector].filter(Boolean))],
        },
      };
    })
    .sort((left, right) => right.score - left.score || left.label.localeCompare(right.label))
    .slice(0, 12);
}

export function recommendTrackingAdditions(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: ExistingTrackingValues = {},
): TrackingRecommendationSet {
  const sectorArticles = articles.filter((article) => sectorMatches(article.sector, selectedSector));
  const keywordSet = new Set((existing.keywords ?? []).map(normalizedKey));
  const peopleSet = new Set((existing.people ?? []).map(normalizedKey));
  const companySet = new Set((existing.companies ?? []).map(normalizedKey));

  return {
    keywords: keywordCandidates(sectorArticles, selectedSector, keywordSet),
    people: peopleCandidates(sectorArticles, peopleSet),
    companies: companyCandidates(sectorArticles, companySet),
    sources: sourceCandidates(sectorArticles, selectedSector, existing.sources ?? []),
  };
}
