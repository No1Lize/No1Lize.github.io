import assert from "node:assert/strict";
import test from "node:test";
import {
  relatedResearchReports,
  researchReports,
} from "../lib/research-report-data";

test("research report snapshot exposes valid PDF reader records", () => {
  for (const report of researchReports) {
    assert.ok(report.id);
    assert.ok(report.slug);
    assert.ok(report.title);
    assert.match(report.publishedAt, /^\d{4}-\d{2}-\d{2}$/u);
    assert.ok(report.originalPdfUrl.startsWith("https://"));
    assert.ok(report.localPdfUrl.startsWith("/research-reports/"));
    assert.ok(report.localPdfUrl.endsWith(".pdf"));
    assert.ok(report.fileSizeBytes > 1024);
  }
});

test("company reports outrank sector-only matches", () => {
  const reports = relatedResearchReports({
    companySlug: "cambricon",
    ticker: "688256",
    sector: "半导体",
  });
  const firstCompanyMatch = reports.findIndex(
    (report) => report.companySlug === "cambricon" || report.ticker === "688256",
  );
  const firstSectorOnly = reports.findIndex(
    (report) => report.sector === "半导体" && report.companySlug !== "cambricon",
  );
  if (firstCompanyMatch >= 0 && firstSectorOnly >= 0) {
    assert.ok(firstCompanyMatch < firstSectorOnly);
  }
});
