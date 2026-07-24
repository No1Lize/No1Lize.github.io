import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import {
  eventsForTrackedSector,
  getTrackedSector,
  trackedSectors,
} from "@/lib/tracked-sectors";
import { heatMethodology, snapshotDate } from "@/lib/intelligence-data";
import { reportContent } from "@/lib/research-content";
import styles from "./sector-detail.module.css";

const institutionKeywords: Record<string, string[]> = {
  "AI / AGI": ["AI", "企业科技", "企业软件", "TMT", "科技"],
  机器人: ["先进制造", "制造", "硬科技", "科技", "工业", "国防科技"],
  半导体: ["硬科技", "先进制造", "制造", "科技"],
  新能源: ["气候科技", "先进制造", "制造", "科技"],
  生物科技: ["生物科技", "医疗"],
};

export function generateStaticParams() {
  return trackedSectors.map((sector) => ({ slug: sector.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const sector = getTrackedSector(slug);
  return { title: sector?.name ?? "赛道" };
}

export default async function SectorDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sector = getTrackedSector(slug);
  if (!sector) notFound();

  const relatedCompanies = companies
    .filter((item) => sector.aliases.includes(item.sector))
    .slice(0, 12);
  const catalogCompanyNames = new Set(
    relatedCompanies.map((company) => company.name.toLowerCase()),
  );
  const customCompanies = sector.tracking.sampleCompanies.filter(
    (name) => !catalogCompanyNames.has(name.toLowerCase()),
  );
  const keywords = [
    ...(institutionKeywords[sector.name] ?? []),
    ...sector.tracking.keywords,
  ];
  const relatedInstitutions = institutionCatalog
    .filter((institution) =>
      institution.sectors.some((focus) =>
        keywords.some(
          (keyword) => focus.includes(keyword) || keyword.includes(focus),
        ),
      ),
    )
    .slice(0, 10);
  const events = eventsForTrackedSector(sector)
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const relatedReports = reports.filter((report) =>
    reportContent[report.slug]?.eventSectors.some((name) =>
      sector.aliases.includes(name),
    ),
  );
  const chinaCompanies = relatedCompanies.filter(
    (item) => item.region === "中国",
  ).length;
  const usCompanies = relatedCompanies.filter(
    (item) => item.region === "美国",
  ).length;

  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>
            SECTOR DOSSIER · {sector.events} 项公开事件
          </p>
          <h1>{sector.name}</h1>
          <p className={styles.heroDescription}>{sector.definition}</p>
          <div className={styles.chips}>
            {sector.subsectors.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
        <div className={styles.heroStat}>
          <span>HeatScore</span>
          <strong>{sector.heat}</strong>
          <small>{sector.sourceCount} 个来源</small>
        </div>
      </header>

      <div className={styles.stack}>
        <article className={styles.article}>
          <Section id="赛道定义" title="赛道定义">
            <p className={styles.lead}>{sector.definition}</p>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <span>公开事件</span>
                <strong>{sector.events}</strong>
                <p>当前数据快照中归入该赛道的公开事件。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>跟踪来源</span>
                <strong>{sector.sourceCount}</strong>
                <p>用于计算热度和追踪变化的独立来源数量。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>自定义对象</span>
                <strong>
                  {sector.tracking.keywords.length +
                    sector.tracking.people.length +
                    sector.tracking.sampleCompanies.length}
                </strong>
                <p>用户配置的关键词、关键人物和样本公司总数。</p>
              </div>
            </div>
          </Section>

          <Section id="中美对照" title="中美发展对照">
            <div className={styles.comparisonGrid}>
              <div className={styles.comparisonCard}>
                <span>中国</span>
                <strong>{chinaCompanies} 家样本公司</strong>
                <p>{sector.chinaLens}</p>
              </div>
              <div className={styles.comparisonCard}>
                <span>美国</span>
                <strong>{usCompanies} 家样本公司</strong>
                <p>{sector.usLens}</p>
              </div>
            </div>
          </Section>

          <Section id="产业链" title="产业链结构">
            <div className={styles.chain}>
              {sector.chain.map((node) => (
                <div className={styles.chainNode} key={node.title}>
                  <strong>{node.title}</strong>
                  <span>{node.detail}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="代表公司" title="代表公司">
            {relatedCompanies.length || customCompanies.length ? (
              <div className={styles.entityGrid}>
                {relatedCompanies.map((company) => (
                  <Link
                    className={styles.companyCard}
                    href={`/companies/${company.slug}`}
                    key={company.slug}
                  >
                    <span>{company.region} · {company.stage}</span>
                    <strong>{company.name}</strong>
                    <p>{company.product}</p>
                  </Link>
                ))}
                {customCompanies.map((company) => (
                  <div className={styles.companyCard} key={company}>
                    <span className={styles.customBadge}>用户添加</span>
                    <strong>{company}</strong>
                    <p>该公司已加入本赛道的搜索和事件发现范围。</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>暂无样本公司，可在追踪配置中添加。</p>
            )}
            <Link className={styles.configLink} href="/tracking">
              管理样本公司与关键词 →
            </Link>
          </Section>

          <Section id="投资机构" title="相关投资机构">
            {relatedInstitutions.length ? (
              <div className={styles.entityGrid}>
                {relatedInstitutions.map((institution) => (
                  <Link
                    className={styles.institutionCard}
                    href={`/institutions/${institution.slug}`}
                    key={institution.slug}
                  >
                    <span>{institution.region} · {institution.type}</span>
                    <strong>{institution.name}</strong>
                    <p>{institution.stages} · {institution.sectors.join("、")}</p>
                  </Link>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>暂无匹配的投资机构样本。</p>
            )}
          </Section>

          <Section id="最新事件" title="最新公开事件">
            {events.length ? (
              <div className={styles.eventList}>
                {events.map((event) => (
                  <a
                    className={styles.eventCard}
                    href={event.source.url}
                    key={event.id}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <div className={styles.eventMeta}>
                      {event.publishedAt}
                      <br />
                      {event.type} · {event.region}
                    </div>
                    <div>
                      <strong>{event.title}</strong>
                      <p>{event.summary}</p>
                    </div>
                  </a>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>当前数据快照中暂无该赛道事件。</p>
            )}
          </Section>

          <Section id="研究重点" title="关键研究变量">
            <div className={styles.focusGrid}>
              {sector.researchFocus.map((item, index) => (
                <div className={styles.focusCard} key={item}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item}</strong>
                </div>
              ))}
            </div>
          </Section>

          <Section id="相关研究" title="相关研究">
            {relatedReports.length ? (
              <div className={styles.researchGrid}>
                {relatedReports.map((report) => (
                  <Link
                    className={styles.researchCard}
                    href={`/reports/${report.slug}`}
                    key={report.slug}
                  >
                    <strong>{report.title}</strong>
                    <p>{report.summary}</p>
                    <span>{report.date} · {report.sources} 个来源</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>暂无与该赛道直接关联的专题研究。</p>
            )}
          </Section>

          <Section id="风险" title="主要风险">
            <ul className={styles.riskList}>
              {sector.risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          </Section>

          <Section id="数据口径" title="热度计算口径">
            <div className={styles.methodRow}>
              <p>{heatMethodology}</p>
              <p>数据更新：{snapshotDate}</p>
            </div>
          </Section>
        </article>
      </div>
    </main>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className={styles.section} id={id}>
      <p className={styles.sectionLabel}>{id}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
