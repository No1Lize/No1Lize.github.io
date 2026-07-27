import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  formatReportFileSize,
  researchReportBySlug,
  researchReports,
} from "@/lib/research-report-data";
import styles from "./reader.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return researchReports.map((report) => ({ slug: report.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const report = researchReportBySlug.get(slug);
  return {
    title: report ? `${report.title} · PDF 阅读` : "研报 PDF 阅读",
    description: report?.summary,
  };
}

export default async function ResearchReportPdfReader({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const report = researchReportBySlug.get(slug);
  if (!report) notFound();

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.breadcrumbs}>
          <Link href="/reports">06 / 研究报告</Link>
          {report.companySlug ? (
            <Link href={`/ipo/${report.companySlug}`}>{report.companyName || report.ticker}</Link>
          ) : null}
        </div>
        <div className={styles.titleRow}>
          <div>
            <p className="eyebrow">
              {report.reportType} · {report.publishedAt}
            </p>
            <h1>{report.title}</h1>
            <p>{report.summary}</p>
          </div>
          <div className={styles.actions}>
            <a href={report.localPdfUrl} download>
              下载归档 PDF
            </a>
            <a href={report.sourcePageUrl} target="_blank" rel="noreferrer">
              查看原始来源
            </a>
          </div>
        </div>
        <dl className={styles.meta}>
          <div>
            <dt>发布机构</dt>
            <dd>{report.institution || report.sourceName}</dd>
          </div>
          <div>
            <dt>关联公司</dt>
            <dd>{report.companyName || "行业研究"}</dd>
          </div>
          <div>
            <dt>证券代码</dt>
            <dd>{report.ticker || "—"}</dd>
          </div>
          <div>
            <dt>行业</dt>
            <dd>{report.sector}</dd>
          </div>
          <div>
            <dt>文件大小</dt>
            <dd>{formatReportFileSize(report.fileSizeBytes)}</dd>
          </div>
          <div>
            <dt>归档时间</dt>
            <dd>{report.archivedAt.slice(0, 10)}</dd>
          </div>
        </dl>
      </header>

      <section className={styles.reader}>
        <iframe
          src={`${report.localPdfUrl}#view=FitH`}
          title={`${report.title} PDF`}
          loading="eager"
        />
        <div className={styles.fallback}>
          <p>浏览器无法内嵌显示时，可直接打开或下载 PDF。</p>
          <a href={report.localPdfUrl} target="_blank" rel="noreferrer">
            在新窗口打开 PDF
          </a>
        </div>
      </section>

      <footer className={styles.footer}>
        <p>
          本站保存的是公开可直接下载的原始 PDF 副本，未修改报告正文。报告版权、观点和免责声明归原作者及发布机构所有；内容仅用于资料检索与研究记录，不构成投资建议。
        </p>
        <a href={report.originalPdfUrl} target="_blank" rel="noreferrer">
          原始 PDF 地址
        </a>
      </footer>
    </main>
  );
}
