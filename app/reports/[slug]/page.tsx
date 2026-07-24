import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, reports } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import { reportContent } from "@/lib/research-content";

export function generateStaticParams() {
  return reports.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const report = reports.find((item) => item.slug === slug);
  return {
    title: report?.title ?? "研究报告",
    description: report?.summary,
  };
}

export default async function ReportDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const report = reports.find((item) => item.slug === slug);
  const content = reportContent[slug];
  if (!report || !content) notFound();

  const relatedCompanies = content.companySlugs
    .map((companySlug) =>
      companies.find((company) => company.slug === companySlug),
    )
    .filter((company) => company !== undefined);
  const evidence = intelligenceEvents
    .filter(
      (event) =>
        (event.companySlug &&
          content.companySlugs.includes(event.companySlug)) ||
        content.eventSectors.includes(event.sector),
    )
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const sources = Array.from(
    new Map(
      [
        ...evidence.map((event) => event.source),
        ...relatedCompanies.map((company) => company.source),
      ].map((source) => [source.url, source]),
    ).values(),
  );

  return (
    <main className="page-shell subpage printable">
      <header className="report-hero">
        <p className="eyebrow">
          {report.type} · 更新 {snapshotDate}
        </p>
        <h1>{report.title}</h1>
        <p>{content.thesis}</p>
        <div>
          {report.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
          <span>{sources.length} 个一手来源</span>
        </div>
      </header>

      <article className="report-body">
        <Section title="摘要">
          <p>{report.summary}</p>
          <p>{content.thesis}</p>
        </Section>

        <Section title="核心发现">
          <div className="insight-grid">
            {content.points.map((point, index) => (
              <div key={point.title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{point.title}</strong>
                <p>{point.body}</p>
              </div>
            ))}
          </div>
        </Section>

        {evidence.length > 0 && (
          <Section title="事实时间线">
            <div className="timeline">
              {evidence.map((event) => (
                <div key={event.id}>
                  <time>{event.publishedAt}</time>
                  <div>
                    <div className="event-tags">
                      <span className={`tag tag-${event.type}`}>
                        {event.type}
                      </span>
                      <span>{event.company}</span>
                    </div>
                    <strong>{event.title}</strong>
                    <p>{event.summary}</p>
                    <a
                      href={event.source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {event.source.name}
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        <Section title="公司样本">
          <div className="entity-list">
            {relatedCompanies.map((company) => (
              <Link href={`/companies/${company.slug}`} key={company.slug}>
                <strong>{company.name}</strong>
                <span>
                  {company.region} · {company.product}
                </span>
              </Link>
            ))}
          </div>
        </Section>

        <Section title="后续跟踪">
          <div className="analysis-grid">
            {content.watchlist.map((item, index) => (
              <div key={item}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{item}</strong>
                <p>后续公告和监管文件将进入同一时间线。</p>
              </div>
            ))}
          </div>
        </Section>

        <Section title="来源">
          {sources.map((source) => (
            <a
              className="source-card"
              href={source.url}
              target="_blank"
              rel="noreferrer"
              key={source.url}
            >
              <span>{source.level}</span>
              <strong>{source.name}</strong>
              <small>{source.url}</small>
            </a>
          ))}
        </Section>
        <footer>修订时间：{snapshotDate} · 研究记录，不构成投资建议</footer>
      </article>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <p className="section-index">{title}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
