import type { TrackingMarket } from "@/lib/user-tracking";

export type ListedCompanyIdentity = {
  market: TrackingMarket;
  ticker: string;
  slug: string;
  thsCode: string;
  quoteCode: string;
};

const US_TICKER = /^[A-Z][A-Z0-9.-]{0,14}$/;

export function normalizeMarketTicker(
  market: TrackingMarket,
  value: string,
): string {
  const raw = String(value ?? "").normalize("NFKC").trim().toUpperCase();

  if (market === "A股") {
    const digits = raw
      .replace(/^(SH|SZ|BJ)/, "")
      .replace(/\.(SH|SZ|BJ)$/, "")
      .replace(/\D/g, "");
    return /^\d{6}$/.test(digits) ? digits : "";
  }

  if (market === "港股") {
    const digits = raw
      .replace(/^HK/, "")
      .replace(/\.HK$/, "")
      .replace(/\D/g, "");
    if (!digits || digits.length > 5) return "";
    return digits.padStart(5, "0");
  }

  const ticker = raw.replace(/\s+/g, "");
  return US_TICKER.test(ticker) ? ticker : "";
}

export function aShareExchange(ticker: string): "SH" | "SZ" | "BJ" {
  if (/^(4|8|92)/.test(ticker)) return "BJ";
  if (/^(5|6|9)/.test(ticker)) return "SH";
  return "SZ";
}

export function listedCompanyIdentity(
  market: TrackingMarket,
  tickerValue: string,
): ListedCompanyIdentity | null {
  const ticker = normalizeMarketTicker(market, tickerValue);
  if (!ticker) return null;

  if (market === "A股") {
    const exchange = aShareExchange(ticker);
    return {
      market,
      ticker,
      slug: `a-${ticker}`,
      thsCode: ticker,
      quoteCode: `${exchange.toLowerCase()}${ticker}`,
    };
  }

  if (market === "港股") {
    const shortTicker = String(Number(ticker)).padStart(4, "0");
    return {
      market,
      ticker,
      slug: `hk-${ticker}`,
      thsCode: `HK${shortTicker}`,
      quoteCode: `hk${ticker}`,
    };
  }

  return {
    market,
    ticker,
    slug: `us-${ticker.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    thsCode: ticker,
    quoteCode: `us${ticker}`,
  };
}

export function listedCompanySlug(
  market: TrackingMarket,
  ticker: string,
  catalogSlug?: string,
): string {
  return catalogSlug || listedCompanyIdentity(market, ticker)?.slug || "";
}
