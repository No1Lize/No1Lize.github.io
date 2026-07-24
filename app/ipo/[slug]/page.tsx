import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ipoCompanies } from "@/lib/catalog-data";
import {
  companyFacts,
  intelligenceEvents,
  snapshotDate,
  type FinancialMetric,
} from "@/lib/intelligence-data";
import { ipoProfiles } from "@/lib/research-content";

export function generateStaticParams() {
  return ipoCompanies.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  return {
    title: `${ipoCompanies.find((item) => item.slug === slug)?.name ?? "公司"}上市跟踪`,
  };
}

export default async function IpoDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const company = ipoCompanies.find((item) => item.slug === slug);
  if (!company) notFound();

  const profile = ipoProfiles[slug];
  const facts = companyFacts[slug];
  const filings = intelligenceEvents
    .filter(
      (event) =>
        event.companySlug === slug &&
        ["财报", "监管文件", "IPO"].includes(event.type),
    )
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const sections = [
    "上市概览",
    "状态时间线",
    ...(facts?.metrics.length ? ["财务披露"] : []),
    ...(filings.length ? ["监管文件"] : []),
    "经营观察",
    "来源",
  ];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">
            {company.market} · {company.sector}
          </p>
          <h1>{company.name}</h1>
          <p>{profile?.description}</p>
          <div className="hero-chips">
            <span>{company.ticker}</span>
            <span>{company.status}</span>
            <span>{profile?.exchange ?? company.market}</span>
          </div>
        </div>
        <div className="hero-stat">
          <span>上市代码</span>
          <strong>{company.ticker}</strong>
          <small>{profile?.listedAt ?? "持续跟踪"}</small>
        </div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>上市档案</strong>
          {sections.map((item) => (
            <a href={`#${item}`} key={item}>
              {item}
            </a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="上市概览" title="上市概览">
            <dl className="facts-grid">
              <div>
                <dt>证券代码</dt>
                <dd>{company.ticker}</dd>
              </div>
              <div>
                <dt>交易所</dt>
                <dd>{profile?.exchange ?? company.market}</dd>
              </div>
              <div>
                <dt>上市日期</dt>
                <dd>{profile?.listedAt ?? "—"}</dd>
              </div>
              <div>
                <dt>资料更新</dt>
                <dd>{snapshotDate}</dd>
              </div>
            </dl>
            <p>{profile?.description}</p>
          </Section>

          <Section id="状态时间线" title="状态时间线">
            <div className="timeline">
              <div>
                <time>{profile?.listedAt ?? "上市"}</time>
                <div>
                  <strong>{profile?.exchange ?? company.market}挂牌</strong>
                  <p>
                    证券代码 {company.ticker}，当前状态为{company.status}。
                  </p>
                </div>
              </div>
              <div>
                <time>{snapshotDate}</time>
                <div>
                  <strong>持续公开披露</strong>
                  <p>{company.latest}</p>
                </div>
              </div>
            </div>
          </Section>

          {facts?.metrics.length > 0 && (
            <Section id="财务披露" title="SEC 最新财务披露">
              <div className="metric-grid">
                {facts.metrics.map((metric) => (
                  <div key={metric.id}>
                    <span>{metric.label}</span>
                    <strong>{formatMetric(metric)}</strong>
                    <small>
                      报告期 {metric.periodEnd} · {metric.form} ·{" "}
                      {metric.fiscalPeriod ?? "报告期"}
                    </small>
                  </div>
                ))}
              </div>
              <a
                className="source-card"
                href={facts.source.url}
                target="_blank"
                rel="noreferrer"
              >
                <span>{facts.source.level}</span>
                <strong>{facts.source.name}</strong>
                <small>CIK {facts.cik} · {facts.entityName}</small>
              </a>
            </Section>
          )}

          {filings.length > 0 && (
            <Section id="监管文件" title="最新监管文件">
              <div className="timeline">
                {filings.map((filing) => (
                  <div key={filing.id}>
                    <time>{filing.publishedAt}</time>
                    <div>
                      <strong>{filing.title}</strong>
                      <p>{filing.summary}</p>
                      <a
                        href={filing.source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        打开 SEC 原始文件
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          <Section id="经营观察" title="经营与资本市场观察">
            <div className="analysis-grid">
              {(profile?.watchItems ?? [company.sector]).map((item, index) => (
                <div key={item}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item}</strong>
                  <p>结合定期报告、公司公告与业务进展跟踪变化。</p>
                </div>
              ))}
            </div>
          </Section>

          <Section id="来源" title="监管与交易所来源">
            <a
              className="source-card"
              href={company.source.url}
              target="_blank"
              rel="noreferrer"
            >
              <span>{company.source.level}</span>
              <strong>{company.source.name}</strong>
              <small>{company.source.url}</small>
            </a>
          </Section>
        </article>

        <aside className="source-rail">
          <div className="confidence-box">
            <span>监管文件</span>
            <strong>{filings.length}</strong>
            <p>定时任务自动读取</p>
          </div>
          {facts && (
            <div className="confidence-box">
              <span>财务指标</span>
              <strong>{facts.metrics.length}</strong>
              <p>保留报告期与表单口径</p>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

function formatMetric(metric: FinancialMetric) {
  if (metric.unit === "USD") {
    return `US$${new Intl.NumberFormat("zh-CN", {
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(metric.value)}`;
  }
  return new Intl.NumberFormat("zh-CN", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(metric.value);
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="article-section">
      <p className="section-index">{id}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
