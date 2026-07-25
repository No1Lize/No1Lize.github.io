import { ipoCompanies, type IpoCompany } from "@/lib/catalog-data";
import {
  userTrackingConfig,
  type TrackingListedCompany,
} from "@/lib/user-tracking";

export type ListedCompanyView = {
  id: string;
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
    `${company.market}:${company.ticker.toUpperCase()}`,
    company,
  ]),
);

export function resolveListedCompany(
  item: TrackingListedCompany,
): ListedCompanyView {
  const catalog = item.catalogSlug
    ? catalogBySlug.get(item.catalogSlug)
    : catalogByMarketTicker.get(`${item.market}:${item.ticker.toUpperCase()}`);

  return {
    id: item.id,
    name: item.name || catalog?.name || item.ticker,
    ticker: item.ticker,
    market: item.market,
    sector: item.sector || catalog?.sector || "未分类",
    enabled: item.enabled,
    custom: item.custom,
    ...(catalog ? { catalogSlug: catalog.slug } : {}),
    status: catalog?.status ?? "待接入数据",
    latest: catalog?.latest ?? "等待接入公告与财务数据源",
    ...(catalog ? { source: catalog.source } : {}),
  };
}

export const listedCompaniesForDisplay: ListedCompanyView[] =
  configuredListedCompanies
    .filter((company) => company.enabled)
    .map(resolveListedCompany);
