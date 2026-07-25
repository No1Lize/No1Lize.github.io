import { companies, type Company } from "@/lib/catalog-data";
import { trackingSectorsMatch } from "@/lib/tracking-sector-policy";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

function normalize(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/[&＆]/g, "and")
    .replace(/[^A-Za-z0-9\u3400-\u9fff]+/g, "")
    .toLocaleLowerCase("zh-CN");
}

function sourceHost(value: string): string {
  try {
    return new URL(value).hostname.toLocaleLowerCase("en-US").replace(/^www\./, "");
  } catch {
    return "";
  }
}

const COMPANY_KEYS = new Map<string, Company>();
for (const company of companies) {
  for (const value of [company.slug, company.name, company.englishName ?? ""]) {
    const key = normalize(value);
    if (key) COMPANY_KEYS.set(key, company);
  }
}

export function catalogCompanyForRecommendation(
  label: string,
  articles: LiveIntelligenceEvent[] = [],
): Company | undefined {
  for (const article of articles) {
    const slug = normalize(article.companySlug ?? "");
    if (slug && COMPANY_KEYS.has(slug)) return COMPANY_KEYS.get(slug);
  }
  return COMPANY_KEYS.get(normalize(label));
}

function sourceRepresentsCompany(
  label: string,
  article: LiveIntelligenceEvent,
): boolean {
  const companyKey = normalize(label);
  if (!companyKey) return false;
  const names = [article.source.name, article.source.platform ?? "", article.sourceId ?? ""]
    .map(normalize)
    .filter(Boolean);
  if (names.some((value) => value.includes(companyKey) || companyKey.includes(value))) {
    return true;
  }
  const hostKey = normalize(sourceHost(article.source.url).split(".")[0] ?? "");
  return Boolean(hostKey && (hostKey.includes(companyKey) || companyKey.includes(hostKey)));
}

export function companyRecommendationAllowedForSector(
  label: string,
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
): boolean {
  const catalogCompany = catalogCompanyForRecommendation(label, articles);
  if (catalogCompany) {
    return trackingSectorsMatch(catalogCompany.sector, selectedSector);
  }

  const uniqueArticles = new Map(articles.map((article) => [article.id, article]));
  const items = [...uniqueArticles.values()];
  const independentHosts = new Set(items.map((article) => sourceHost(article.source.url)).filter(Boolean));
  if (items.length >= 2 && independentHosts.size >= 2) return true;

  return items.some(
    (article) =>
      ["官方披露", "原始材料", "监管文件"].includes(article.source.level) &&
      sourceRepresentsCompany(label, article),
  );
}

export function companySourceAllowedForSector(
  article: LiveIntelligenceEvent,
  selectedSector: string,
): boolean {
  const label = article.company.trim();
  if (!label) return true;
  const catalogCompany = catalogCompanyForRecommendation(label, [article]);
  if (!catalogCompany) return true;
  if (trackingSectorsMatch(catalogCompany.sector, selectedSector)) return true;
  return !sourceRepresentsCompany(label, article);
}
