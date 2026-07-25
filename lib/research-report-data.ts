import rawResearchReports from "@/public/data/research_reports.json";

export type ResearchReportAsset = {
  id: string;
  slug: string;
  title: string;
  publishedAt: string;
  institution: string;
  analysts: string[];
  reportType: "个股研报" | "行业研报" | "策略报告" | "宏观研究" | "公司资料";
  companySlug?: string;
  companyName?: string;
  ticker?: string;
  market?: "A股" | "港股" | "美股";
  sector: string;
  rating?: string;
  ratingChange?: string;
  summary: string;
  sourceName: string;
  sourcePageUrl: string;
  originalPdfUrl: string;
  localPdfUrl: string;
  fileSizeBytes: number;
  archivedAt: string;
};

type ResearchReportSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  reports: ResearchReportAsset[];
  sourceStatus?: {
    source: string;
    status: string;
    fetched: number;
    archived: number;
    error?: string;
  }[];
};

const snapshot = rawResearchReports as ResearchReportSnapshot;

export const researchReportGeneratedAt = snapshot.generatedAt || "";
export const researchReports = [...(snapshot.reports ?? [])].sort((a, b) =>
  b.publishedAt.localeCompare(a.publishedAt),
);
export const researchReportSourceStatus = snapshot.sourceStatus ?? [];
export const researchReportBySlug = new Map(
  researchReports.map((report) => [report.slug, report]),
);

export function relatedResearchReports({
  companySlug,
  ticker,
  sector,
  limit = 8,
}: {
  companySlug?: string;
  ticker?: string;
  sector?: string;
  limit?: number;
}) {
  const normalizedTicker = ticker?.replace(/\D/gu, "").replace(/^0+/u, "");
  return researchReports
    .map((report) => {
      const reportTicker = report.ticker?.replace(/\D/gu, "").replace(/^0+/u, "");
      const companyMatch = Boolean(companySlug && report.companySlug === companySlug);
      const tickerMatch = Boolean(normalizedTicker && reportTicker === normalizedTicker);
      const sectorMatch = Boolean(sector && report.sector === sector);
      return {
        report,
        score: companyMatch || tickerMatch ? 3 : sectorMatch ? 1 : 0,
      };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || b.report.publishedAt.localeCompare(a.report.publishedAt))
    .slice(0, limit)
    .map((item) => item.report);
}

export function formatReportFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "PDF";
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
