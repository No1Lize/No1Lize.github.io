"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  formatReportFileSize,
  type ResearchReportAsset,
} from "@/lib/research-report-data";
import styles from "./research-report-library.module.css";

export function ResearchReportLibrary({
  reports,
  compact = false,
}: {
  reports: ResearchReportAsset[];
  compact?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("全部");
  const types = useMemo(
    () => ["全部", ...Array.from(new Set(reports.map((report) => report.reportType)))],
    [reports],
  );
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("zh-CN");
    return reports.filter((report) => {
      if (type !== "全部" && report.reportType !== type) return false;
      if (!normalized) return true;
      return [
        report.title,
        report.institution,
        report.companyName,
        report.ticker,
        report.sector,
        report.summary,
      ]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("zh-CN").includes(normalized));
    });
  }, [query, reports, type]);

  if (!reports.length) {
    return (
      <div className={styles.empty}>
        <strong>公开 PDF 研报正在建立索引</strong>
        <p>定时任务只归档无需登录、可直接下载且通过 PDF 校验的原文。</p>
      </div>
    );
  }

  return (
    <div className={styles.library} data-compact={compact || undefined}>
      {!compact && (
        <div className={styles.toolbar}>
          <label>
            <span>检索研报</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="公司、代码、机构、行业或报告标题"
            />
          </label>
          <div className={styles.filters} aria-label="报告类型筛选">
            {types.map((item) => (
              <button
                key={item}
                type="button"
                data-active={item === type || undefined}
                onClick={() => setType(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <small>显示 {filtered.length} / {reports.length} 份已归档 PDF</small>
        </div>
      )}

      <div className={styles.grid}>
        {filtered.map((report) => (
          <Link href={`/reports/pdf/${report.slug}`} className={styles.card} key={report.id}>
            <div className={styles.cardTop}>
              <span>{report.reportType}</span>
              <small>{report.publishedAt}</small>
            </div>
            <h3>{report.title}</h3>
            <p>{report.summary}</p>
            <div className={styles.meta}>
              <span>{report.institution || report.sourceName}</span>
              {report.companyName && <span>{report.companyName}</span>}
              {report.ticker && <span>{report.ticker}</span>}
              <span>{report.sector}</span>
            </div>
            <div className={styles.cardBottom}>
              <span>{formatReportFileSize(report.fileSizeBytes)}</span>
              <strong>站内阅读 PDF →</strong>
            </div>
          </Link>
        ))}
      </div>

      {!filtered.length && (
        <div className={styles.empty}>
          <strong>没有匹配的已归档 PDF</strong>
          <p>更换公司、代码或报告类型继续检索。</p>
        </div>
      )}
    </div>
  );
}
