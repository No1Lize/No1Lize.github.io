import rawDisclosureSnapshot from "@/public/data/listed_company_disclosures.json";

export type ListedDisclosureSource = {
  name: string;
  url: string;
  level: "监管文件" | "数据库记录";
};

export type ListedDisclosureEvent = {
  id: string;
  companySlug: string;
  companyName: string;
  market: "A股" | "港股";
  ticker: string;
  exchange: string;
  listingRole: string;
  publishedAt: string;
  documentType: string;
  title: string;
  summary: string;
  source: ListedDisclosureSource;
  discoveredVia: string;
  fallback: boolean;
};

export type ListedCompanyDisclosure = {
  slug: string;
  name: string;
  updatedAt: string;
  status: "ok" | "retained" | "partial";
  listings: {
    market: "A股" | "港股";
    ticker: string;
    exchange: string;
    listingRole: string;
  }[];
  events: ListedDisclosureEvent[];
  officialEventCount: number;
  fallbackEventCount: number;
};

type ListedDisclosureSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  companyCount: number;
  eventCount: number;
  companies: Record<string, ListedCompanyDisclosure>;
};

const snapshot = rawDisclosureSnapshot as ListedDisclosureSnapshot;

export const listedDisclosureGeneratedAt = snapshot.generatedAt || "";

export function getListedCompanyDisclosure(
  slug: string,
): ListedCompanyDisclosure | undefined {
  return snapshot.companies?.[slug];
}
