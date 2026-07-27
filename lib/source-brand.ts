const COMPOUND_PUBLIC_SUFFIXES = new Set([
  "co.uk",
  "org.uk",
  "com.cn",
  "net.cn",
  "org.cn",
  "com.tw",
  "com.hk",
  "com.au",
  "co.jp",
  "co.kr",
  "co.in",
  "com.sg",
  "com.br",
]);

export function sourceHostname(value: string): string {
  try {
    return new URL(value).hostname.toLocaleLowerCase("en-US").replace(/^www\./, "");
  } catch {
    return value
      .trim()
      .toLocaleLowerCase("en-US")
      .replace(/^https?:\/\//, "")
      .split(/[/?#]/, 1)[0]
      .replace(/^www\./, "");
  }
}

/**
 * Returns the user-facing source brand key rather than the exact crawl host.
 * Different editorial subdomains may still be crawled independently, while
 * recommendations collapse them into one brand-level choice.
 */
export function sourceBrandKey(value: string): string {
  const host = sourceHostname(value);
  if (!host) return "";

  // Yahoo operates many regional and editorial subdomains that should appear
  // as one user-facing recommendation.
  if (/(^|\.)yahoo\./i.test(host) || host === "yimg.com" || host.endsWith(".yimg.com")) {
    return "yahoo";
  }

  const parts = host.split(".").filter(Boolean);
  if (parts.length <= 2) return host;

  const finalTwo = parts.slice(-2).join(".");
  if (COMPOUND_PUBLIC_SUFFIXES.has(finalTwo) && parts.length >= 3) {
    return parts.slice(-3).join(".");
  }
  return finalTwo;
}
