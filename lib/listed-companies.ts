import { ipoCompanies, type IpoCompany } from "@/lib/catalog-data";
import { listedCompanySlug, normalizeMarketTicker } from "@/lib/listed-company-identity";
import { marketProfiles } from "@/lib/market-profile-data";
import {
  userTrackingConfig,
  type TrackingListedCompany,
} from "@/lib/user-tracking";

export type ListedCompanyView = {
  id: string;
  slug: string;
  name: string;
  ticker: string;
  market: "A股" | "港股" | "美股";
  sector: string;
  enabled: boolean;
  custom: boolean;
  catalogSlug?: string;
  status: string;
  latest: string;
  source?: IpoCompany["source"];
};

export function catalogCompanyToTracking(
  company: IpoCompany,
): TrackingListedCompany {
  return {
    id: `catalog-${company.slug}`,
    name: company.name,
    ticker: company.ticker,
    market: company.market,
    sector: company.sector,
    enabled: true,
    custom: false,
    catalogSlug: company.slug,
  };
}

export function ensureListedCompanyDefaults(
  listedCompanies: TrackingListedCompany[],
): TrackingListedCompany[] {
  return listedCompanies.length
    ? listedCompanies
    : ipoCompanies.map(catalogCompanyToTracking);
}

export const configuredListedCompanies = ensureListedCompanyDefaults(
  userTrackingConfig.listedCompanies,
);

const catalogBySlug = new Map(
  ipoCompanies.map((company) => [company.slug, company]),
);
const catalogByMarketTicker = new Map(
  ipoCompanies.map((company) => [
    `${company.market}:${normalizeMarketTicker(company.market, company.ticker)}`,
    company,
  ]),
);

export function resolveListedCompany(
  item: TrackingListedCompany,
): ListedCompanyView {
  const ticker = normalizeMarketTicker(item.market, item.ticker) || item.ticker;
  const catalog = item.catalogSlug
    ? catalogBySlug.get(item.catalogSlug)
    : catalogByMarketTicker.get(`${item.market}:${ticker}`);
  const slug = listedCompanySlug(item.market, ticker, catalog?.slug ?? item.catalogSlug);
  const marketProfile = marketProfiles[slug];
  const source = catalog?.source ??
    (marketProfile
      ? {
          name: "同花顺公开公司页",
          url: marketProfile.sources.tonghuashun,
          level: "数据库记录" as const,
        }
      : undefined);

  return {
    id: item.id,
    slug,
    name: marketProfile?.company.name || item.name || catalog?.name || ticker,
    ticker,
    market: item.market,
    sector: item.sector || catalog?.sector || "未分类",
    enabled: item.enabled,
    custom: item.custom,
    ...(catalog ? { catalogSlug: catalog.slug } : {}),
    status:
      marketProfile?.status === "ok"
        ? "数据已同步"
        : marketProfile?.status === "partial"
          ? "部分数据已同步"
          : catalog?.status ?? "等待首次市场数据同步",
    latest:
      marketProfile?.updatedAt?.slice(0, 10) ??
      catalog?.latest ??
      "已创建详情页，等待定时任务抓取",
    ...(source ? { source } : {}),
  };
}

export const listedCompaniesForDisplay: ListedCompanyView[] =
  configuredListedCompanies
    .filter((company) => company.enabled)
    .map(resolveListedCompany)
    .filter((company) => Boolean(company.slug));

export const listedCompanyBySlug = new Map(
  listedCompaniesForDisplay.map((company) => [company.slug, company]),
);
