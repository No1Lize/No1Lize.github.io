import rawMarketProfiles from "@/public/data/market_profiles.json";
import { ipoProfiles } from "@/lib/research-content";
import type { TrackingMarket } from "@/lib/user-tracking";

export type MarketPricePoint = {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume?: number;
};

export type MarketMetric = {
  id: string;
  label: string;
  value: string;
  period?: string;
};

export type MarketFinancialSeries = {
  id: string;
  label: string;
  unit: string;
  points: { period: string; value: number }[];
};

export type MarketQuote = {
  price: number;
  change?: number;
  changePercent?: number;
  previousClose?: number;
  currency?: string;
  asOf?: string;
  source?: { name: string; url: string };
};

export type MarketNewsItem = {
  title: string;
  url: string;
  publishedAt: string;
  source: string;
};

export type MarketCompanyProfile = {
  name: string;
  englishName?: string;
  industry?: string;
  exchange?: string;
  listedAt?: string;
  website?: string;
  employees?: string;
  chairman?: string;
  address?: string;
  region?: string;
  description?: string;
  mainBusiness?: string;
};

export type MarketProfile = {
  slug: string;
  market: TrackingMarket;
  ticker: string;
  thsCode: string;
  updatedAt: string;
  status: "ok" | "partial" | "error" | "pending";
  company: MarketCompanyProfile;
  priceHistory: MarketPricePoint[];
  metrics: MarketMetric[];
  financialSeries: MarketFinancialSeries[];
  quote?: MarketQuote;
  news?: MarketNewsItem[];
  sources: {
    tonghuashun: string;
    price?: string;
    quote?: string;
    yahooFinance?: string;
    sinaFinance?: string;
  };
  warnings?: string[];
};

type MarketProfileSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  profiles: Record<string, MarketProfile>;
  sourceStatus?: {
    slug: string;
    status: string;
    profileAccepted: boolean;
    pricePoints: number;
    marketCapAccepted?: boolean;
    quoteAccepted?: boolean;
    newsCount?: number;
    error?: string;
  }[];
};

const PROVINCES = [
  "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
  "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
  "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古",
  "广西", "西藏", "宁夏", "新疆", "香港", "澳门", "台湾",
];

const NAVIGATION_NOISE = [
  "所属地域",
  "所属地区",
  "经营分析",
  "财务分析",
  "公司资料",
  "公司概况",
  "主营业务",
  "营业收入构成",
  "总市值",
  "行情走势",
  "新闻公告",
];

function hasNumericValue(value: string | undefined) {
  return Boolean(value && /\d/u.test(value) && !["0", "0.00", "0%"].includes(value));
}

function parseShares(value: string | undefined) {
  const match = value?.replaceAll(",", "").match(/(-?\d+(?:\.\d+)?)\s*(万亿|亿|万)?\s*股?/u);
  if (!match) return 0;
  const multiplier = match[2] === "万亿"
    ? 1_000_000_000_000
    : match[2] === "亿"
      ? 100_000_000
      : match[2] === "万"
        ? 10_000
        : 1;
  return Number(match[1]) * multiplier;
}

function formatMarketCap(value: number, market: TrackingMarket) {
  const prefix = market === "A股" ? "¥" : market === "港股" ? "HK$" : "US$";
  if (value >= 1_000_000_000_000) return `${prefix}${(value / 1_000_000_000_000).toFixed(2)}万亿`;
  if (value >= 100_000_000) return `${prefix}${(value / 100_000_000).toFixed(2)}亿`;
  if (value >= 10_000) return `${prefix}${(value / 10_000).toFixed(2)}万`;
  return `${prefix}${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value)}`;
}

function normalizedRegion(company: MarketCompanyProfile, market: TrackingMarket) {
  const explicit = company.region?.trim();
  if (explicit && !["-", "--"].includes(explicit)) return explicit;
  const address = company.address || "";
  const province = PROVINCES.find((item) => address.includes(item));
  if (province) {
    return ["北京", "上海", "天津", "重庆"].includes(province) ? `${province}市` : province;
  }
  if (market === "港股") return "中国香港";
  if (market === "美股") return "美国";
  return "中国";
}

function isNavigationNoise(value: string) {
  const compact = value.replace(/[\s，。；;:：|\-—_/]/gu, "");
  if (!compact) return true;
  const noiseHits = NAVIGATION_NOISE.filter((label) => compact.includes(label)).length;
  if (noiseHits >= 2 && compact.length < 80) return true;
  if (noiseHits >= 1 && compact.length < 18) return true;
  return /^(?:--?|暂无|待同步|亿|万|元|股)+$/u.test(compact);
}

function cleanIndustry(value: string | undefined) {
  const text = (value || "").replace(/\s+/gu, " ").trim();
  if (!text || isNavigationNoise(text) || /总市值|流通市值|成交额/u.test(text)) return "";
  return text.slice(0, 80);
}

function cleanCompanyText(value: string | undefined, limit: number) {
  let text = (value || "").replace(/\s+/gu, " ").trim().replace(/[，；;\s]+$/u, "");
  if (isNavigationNoise(text)) return "";
  for (const marker of [
    "公司成立至今共获得多项荣誉",
    "公司先后获得多项荣誉",
    "公司曾获多项荣誉",
    "所获荣誉",
    "获奖情况",
  ]) {
    const index = text.indexOf(marker);
    if (index >= 20) {
      text = text.slice(0, index).replace(/[，；;\s]+$/u, "");
      break;
    }
  }
  if (text.length > limit) {
    const clipped = text.slice(0, limit);
    const sentenceEnd = Math.max(clipped.lastIndexOf("。"), clipped.lastIndexOf("！"), clipped.lastIndexOf("？"));
    text = sentenceEnd >= Math.max(70, Math.floor(limit * 0.55))
      ? clipped.slice(0, sentenceEnd + 1)
      : clipped.replace(/[，；;\s]+$/u, "");
  }
  if (text && !/[。！？]$/u.test(text)) text += "。";
  return text;
}

function fallbackDescription(profile: MarketProfile) {
  const archive = ipoProfiles[profile.slug]?.description?.replace(/[。\s]+$/u, "");
  if (archive) {
    return `${profile.company.name}是一家${archive}，本页持续跟踪其历史行情、财务指标、公司公告与经营进展。`;
  }
  return `${profile.company.name}的公开市场资料页，持续跟踪历史行情、财务指标、公司公告与经营进展。`;
}

function normalizeQuote(quote: MarketQuote | undefined): MarketQuote | undefined {
  if (!quote || typeof quote !== "object") return undefined;
  const price = Number(quote.price);
  if (!Number.isFinite(price) || price <= 0) return undefined;
  return { ...quote, price };
}

function normalizeNews(news: MarketNewsItem[] | undefined): MarketNewsItem[] {
  if (!Array.isArray(news)) return [];
  return news
    .filter(
      (item) =>
        item &&
        typeof item.title === "string" &&
        item.title.trim() &&
        typeof item.url === "string" &&
        /^https?:\/\//u.test(item.url) &&
        typeof item.publishedAt === "string" &&
        item.publishedAt.trim(),
    )
    .slice(0, 10);
}

export function quoteCurrencyPrefix(quote: MarketQuote | undefined, market: TrackingMarket) {
  const currency = quote?.currency?.toUpperCase();
  if (currency === "CNY" || currency === "RMB") return "¥";
  if (currency === "HKD") return "HK$";
  if (currency === "USD") return "US$";
  return market === "A股" ? "¥" : market === "港股" ? "HK$" : "US$";
}

export type MarketQuoteView = {
  price: string;
  changePercent: number;
  direction: "up" | "down" | "flat";
  asOf?: string;
  sourceName?: string;
  delayed: boolean;
};

/** 列表页/详情页共用的最新价视图：优先公开报价快照，退化为最近收盘。 */
export function latestQuoteView(profile: MarketProfile | undefined): MarketQuoteView | null {
  if (!profile) return null;
  const prefix = quoteCurrencyPrefix(profile.quote, profile.market);
  const quote = profile.quote;
  if (quote) {
    const pct = Number.isFinite(quote.changePercent) ? Number(quote.changePercent) : 0;
    return {
      price: `${prefix}${quote.price.toFixed(2)}`,
      changePercent: pct,
      direction: pct > 0 ? "up" : pct < 0 ? "down" : "flat",
      ...(quote.asOf ? { asOf: quote.asOf } : {}),
      ...(quote.source?.name ? { sourceName: quote.source.name } : {}),
      delayed: false,
    };
  }
  const points = profile.priceHistory;
  if (points.length >= 2) {
    const latest = points.at(-1)!;
    const previous = points.at(-2)!;
    const pct = previous.close ? ((latest.close - previous.close) / previous.close) * 100 : 0;
    return {
      price: `${prefix}${latest.close.toFixed(2)}`,
      changePercent: pct,
      direction: pct > 0 ? "up" : pct < 0 ? "down" : "flat",
      asOf: latest.date,
      delayed: true,
    };
  }
  return null;
}

function normalizeProfile(profile: MarketProfile): MarketProfile {
  // The snapshot is crawler-generated; a partial profile must degrade to
  // empty sections instead of crashing the whole static build.
  const priceHistory = profile.priceHistory ?? [];
  const financialSeries = profile.financialSeries ?? [];
  const company = { ...profile.company };
  company.industry = cleanIndustry(company.industry) || undefined;
  const description = cleanCompanyText(company.description, 360);
  const mainBusiness = cleanCompanyText(company.mainBusiness, 220);
  company.mainBusiness = mainBusiness || undefined;
  const combined = description.length >= 70 || !mainBusiness || description.includes(mainBusiness)
    ? description || mainBusiness
    : cleanCompanyText(`${description} ${mainBusiness}`, 360);
  company.description = combined.length >= 40 ? combined : fallbackDescription(profile);
  company.region = normalizedRegion(company, profile.market);

  const metrics = (profile.metrics ?? []).filter((metric) => hasNumericValue(metric.value));
  const marketCapIndex = metrics.findIndex((metric) => metric.id === "marketCap");
  const currentMarketCap = marketCapIndex >= 0 ? metrics[marketCapIndex].value : "";
  if (!hasNumericValue(currentMarketCap)) {
    const totalShares = metrics.find((metric) => metric.id === "totalShares")?.value;
    const shares = parseShares(totalShares);
    const latestClose = priceHistory.at(-1)?.close || 0;
    if (shares > 0 && latestClose > 0) {
      const derived: MarketMetric = {
        id: "marketCap",
        label: "总市值",
        value: formatMarketCap(shares * latestClose, profile.market),
        period: "按最新收盘价估算",
      };
      if (marketCapIndex >= 0) metrics[marketCapIndex] = derived;
      else metrics.unshift(derived);
    }
  }

  const quote = normalizeQuote(profile.quote);
  const normalized: MarketProfile = {
    ...profile,
    company,
    priceHistory,
    metrics,
    financialSeries,
    news: normalizeNews(profile.news),
  };
  if (quote) normalized.quote = quote;
  else delete normalized.quote;
  return normalized;
}

const snapshot = rawMarketProfiles as MarketProfileSnapshot;

export const marketProfileGeneratedAt = snapshot.generatedAt || "";
export const marketProfiles = Object.fromEntries(
  Object.entries(snapshot.profiles ?? {}).map(([slug, profile]) => [slug, normalizeProfile(profile)]),
) as Record<string, MarketProfile>;
export const marketProfileStatus = snapshot.sourceStatus ?? [];
