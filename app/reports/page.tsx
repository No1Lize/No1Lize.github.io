import type { Metadata } from "next";
import Link from "next/link";
import { ResearchReportLibrary } from "@/components/research-report-library";
import { reports } from "@/lib/catalog-data";
import {
  researchReportGeneratedAt,
  researchReports,
} from "@/lib/research-report-data";
import styles from "./reports.module.css";

export const metadata: Metadata = {
  title: "研究报告",
  description: "赛道、公司、IPO、机构和人物研究，以及公开 PDF 研报归档。",
};

export default function ReportsPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">06 / RESEARCH</p>
        <h1>研究报告</h1>
        <p>
          围绕 AI、机器人、芯片、商业航天和自动驾驶，连接核心判断、公司样本、事实时间线，
          并归档无需登录即可公开下载的研究报告 PDF。
        </p>
      </header>

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div>
            <p className="section-index">PUBLIC PDF ARCHIVE</p>
            <h2>公开研报 PDF 资产库</h2>
          </div>
          <div className={styles.stats}>
            <strong>{researchReports.length}</strong>
            <span>份已归档 PDF</span>
            <small>
              {researchReportGeneratedAt
                ? `更新 ${researchReportGeneratedAt.slice(0, 10)}`
                : "等待首次抓取"}
            </small>
          </div>
        </div>
        <p className={styles.note}>
          点击任意研报进入站内 PDF 阅读页。系统仅保存公开可直接下载且通过 PDF 文件校验的原文，
          不绕过登录、付费或访问权限。
        </p>
        <ResearchReportLibrary reports={researchReports} />
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div>
            <p className="section-index">EDITORIAL RESEARCH</p>
            <h2>专题研究与持续跟踪</h2>
          </div>
          <span className={styles.count}>{reports.length} 个专题</span>
        </div>
        <div className="report-list">
          {reports.map((report, index) => (
            <Link href={`/reports/${report.slug}`} key={report.slug}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <p>
                  {report.type} · {report.date}
                </p>
                <h2>{report.title}</h2>
                <strong>{report.summary}</strong>
                <div>
                  {report.tags.map((tag) => (
                    <i key={tag}>{tag}</i>
                  ))}
                </div>
              </div>
              <small>{report.sources} 个来源</small>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
