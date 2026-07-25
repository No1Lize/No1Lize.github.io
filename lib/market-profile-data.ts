import rawMarketProfiles from "@/public/data/market_profiles.json";
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
  sources: {
    tonghuashun: string;
    price?: string;
    quote?: string;
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
    error?: string;
  }[];
};

const snapshot = rawMarketProfiles as MarketProfileSnapshot;

export const marketProfileGeneratedAt = snapshot.generatedAt || "";
export const marketProfiles = snapshot.profiles ?? {};
export const marketProfileStatus = snapshot.sourceStatus ?? [];
