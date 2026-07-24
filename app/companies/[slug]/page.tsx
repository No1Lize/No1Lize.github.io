import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import {
  getCompanyResearch,
  getInstitutionProfile,
  reportContent,
} from "@/lib/research-content";

export function generateStaticParams() {
  return companies.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const company = companies.find((item) => item.slug === slug);
  return {
    title: company?.name ?? "公司档案",
    description: company?.summary,
  };
}

export default async function CompanyDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const company = companies.find((item) => item.slug === slug);
  if (!company) notFound();

  const research = getCompanyResearch(company);
  const events = intelligenceEvents
    .filter((item) => item.companySlug === slug)
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const peers = companies
    .filter((item) => item.sector === company.sector && item.slug !== company.slug)
    .slice(0, 8);
  const relatedInstitutions = institutionCatalog.filter((institution) =>
    getInstitutionProfile(institution).portfolio.some(
      (portfolio) => portfolio.slug === company.slug,
    ),
  );
  const relatedReports = reports.filter((report) =>
    reportContent[report.slug]?.companySlugs.includes(company.slug),
  );

  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">
            {company.region} · {company.sector} · {company.status}
          </p>
          <h1>{company.name}</h1>
          <p>{company.englishName}</p>
          <div className="hero-chips">
            <span>{company.stage}</span>
            <span>{company.headquarters}</span>
            <span>资料更新 {snapshotDate}</span>
          </div>
        </div>
        <div className="entity-monogram">
          {company.name.slice(0, 2).toUpperCase()}
        </div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>公司档案</strong>
          {[
            "公司概览",
            "业务拆解",
            "公开动态",
            "关键研究问题",
            "同赛道对照",
            "风险观察",
            "来源",
          ].map((item) => (
            <a href={`#${item}`} key={item}>
              {item}
            </a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="公司概览" title="公司概览">
            <dl className="facts-grid">
              <div>
                <dt>成立时间</dt>
                <dd>{company.founded}</dd>
              </div>
              <div>
                <dt>总部</dt>
                <dd>{company.headquarters}</dd>
              </div>
              <div>
                <dt>当前阶段</dt>
                <dd>{company.stage}</dd>
              </div>
              <div>
                <dt>产业方向</dt>
                <dd>{company.sector}</dd>
              </div>
            </dl>
            <p>{company.summary}</p>
          </Section>

          <Section id="业务拆解" title="业务与产业位置">
            <div className="insight-grid">
              <Insight label="核心产品" text={company.product} />
              <Insight label="产业位置" text={research.industryPosition} />
              <Insight label="商业化观察" text={research.commercialization} />
              <Insight label="技术观察" text={research.technology} />
            </div>
          </Section>

          <Section id="公开动态" title="融资、产品与监管动态">
            {events.length ? (
              <div className="timeline">
                {events.map((event) => (
                  <div key={event.id}>
                    <time>{event.publishedAt}</time>
                    <div>
                      <div className="event-tags">
                        <span className={`tag tag-${event.type}`}>
                          {event.type}
                        </span>
                      </div>
                      <strong>{event.title}</strong>
                      <p>{event.summary}</p>
                      <a
                        href={event.source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {event.source.level} · {event.source.name}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <a
                className="source-card"
                href={company.source.url}
                target="_blank"
                rel="noreferrer"
              >
                <span>公司动态入口</span>
                <strong>{company.source.name}</strong>
                <small>查看产品、公告与公司资料</small>
              </a>
            )}
          </Section>

          <Section id="关键研究问题" title="关键研究问题">
            <div className="analysis-grid">
              {research.researchQuestions.map((question, index) => (
                <div key={question}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{question}</strong>
                  <p>结合后续产品、客户、财务与监管披露持续跟踪。</p>
                </div>
              ))}
            </div>
          </Section>

          <Section id="同赛道对照" title={`${company.sector}对照样本`}>
            <div className="entity-list">
              {peers.map((peer) => (
                <Link href={`/companies/${peer.slug}`} key={peer.slug}>
                  <strong>{peer.name}</strong>
                  <span>
                    {peer.region} · {peer.product}
                  </span>
                </Link>
              ))}
            </div>
          </Section>

          <Section id="风险观察" title="风险观察">
            <ul className="risk-list">
              {research.risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          </Section>

          <Section id="来源" title="原始来源">
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
            {events.slice(0, 4).map((event) => (
              <a
                className="source-card"
                href={event.source.url}
                target="_blank"
                rel="noreferrer"
                key={event.id}
              >
                <span>{event.publishedAt}</span>
                <strong>{event.source.name}</strong>
                <small>{event.title}</small>
              </a>
            ))}
          </Section>
        </article>

        <aside className="source-rail">
          {relatedInstitutions.length > 0 && (
            <>
              <strong>公开投资机构</strong>
              {relatedInstitutions.map((institution) => (
                <Link
                  href={`/institutions/${institution.slug}`}
                  key={institution.slug}
                >
                  {institution.name}
                  <span>{institution.stages}</span>
                </Link>
              ))}
            </>
          )}
          <strong>相关研究</strong>
          {relatedReports.map((report) => (
            <Link href={`/reports/${report.slug}`} key={report.slug}>
              {report.title}
              <span>{report.date}</span>
            </Link>
          ))}
          <div className="confidence-box">
            <span>公开动态</span>
            <strong>{events.length}</strong>
            <p>公司公告与监管文件</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function Insight({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <span>{label}</span>
      <p>{text}</p>
    </div>
  );
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
