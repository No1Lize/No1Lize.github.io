import type { IpoCompany } from "@/lib/catalog-data";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";
import type { TrackingListedCompany } from "@/lib/user-tracking";

export type ListedCompanyRecommendation = {
  value: string;
  label: string;
  reason: string;
  score: number;
  company: IpoCompany;
};

function normalize(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase("zh-CN");
}

function sectorMatches(left: string, right: string): boolean {
  const a = normalize(left);
  const b = normalize(right);
  return Boolean(a && b && (a === b || a.includes(b) || b.includes(a)));
}

function articleMatchesCompany(article: LiveIntelligenceEvent, company: IpoCompany): boolean {
  if (article.companySlug && article.companySlug === company.slug) return true;
  const companyName = normalize(company.name);
  const ticker = normalize(company.ticker);
  const text = normalize(`${article.company} ${article.title} ${article.summary}`);
  return text.includes(companyName) || (ticker.length >= 3 && text.includes(ticker));
}

function daysAgo(value: string): number {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return 365;
  return Math.max(0, (Date.now() - timestamp) / 86_400_000);
}

export function recommendListedCompanies(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  catalog: IpoCompany[],
  existing: TrackingListedCompany[],
): ListedCompanyRecommendation[] {
  const existingKeys = new Set(
    existing.map((item) => `${item.market}:${item.ticker.toUpperCase()}`),
  );
  const sectorArticles = articles.filter((article) =>
    sectorMatches(article.sector, selectedSector),
  );

  return catalog
    .filter(
      (company) =>
        sectorMatches(company.sector, selectedSector) &&
        !existingKeys.has(`${company.market}:${company.ticker.toUpperCase()}`),
    )
    .map((company) => {
      const matches = sectorArticles.filter((article) =>
        articleMatchesCompany(article, company),
      );
      const recent = matches.filter((article) => daysAgo(article.publishedAt) <= 30).length;
      const averageImportance = matches.length
        ? matches.reduce((sum, article) => sum + article.importance, 0) / matches.length
        : 0;
      const averageQuality = matches.length
        ? matches.reduce((sum, article) => sum + (article.qualityScore ?? 55), 0) /
          matches.length
        : 0;
      const score = Math.round(
        matches.length * 18 + recent * 8 + averageImportance * 0.25 + averageQuality * 0.15,
      );
      const reason = matches.length
        ? `当前赛道 ${matches.length} 条相关情报 · 近30天 ${recent} 条`
        : `当前赛道已有${company.market}上市公司档案和固定披露源`;
      return {
        value: `${company.market}:${company.ticker}`,
        label: `${company.name} · ${company.market} · ${company.ticker}`,
        reason,
        score,
        company,
      };
    })
    .sort(
      (left, right) =>
        right.score - left.score ||
        left.company.name.localeCompare(right.company.name, "zh-CN"),
    );
}
