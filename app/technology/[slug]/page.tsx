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

const genericCompanies = new Set(["", "科技产业", "AI 研究", "未分类"]);

function unique(values: string[], limit = 20): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.replace(/\s+/g, " ").trim();
    const key = value.toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function emptyEventMessage(status: string, message: string): string {
  if (status === "pending") {
    return "赛道配置已写入，正在等待首次爬虫运行；完成前网站不会把该空快照视为正式结果。";
  }
  if (status === "error") {
    return `赛道爬虫本轮失败：${message}`;
  }
  if (status === "partial") {
    return `赛道爬虫仅部分完成：${message}`;
  }
  return message || "三路发现源均已运行，但当前没有满足归属条件的公开事件。";
}

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

  const events = eventsForTrackedSector(sector)
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 20);
  const relatedCompanies = companies
    .filter((item) => sector.aliases.includes(item.sector))
    .slice(0, 12);
  const catalogCompanyNames = new Set(
    relatedCompanies.map((company) => company.name.toLocaleLowerCase("zh-CN")),
  );
  const observedCompanies = events
    .map((event) => event.company)
    .filter((company) => !genericCompanies.has(company));
  const customCompanies = unique([
    ...sector.tracking.sampleCompanies,
    ...observedCompanies,
  ]).filter(
    (name) => !catalogCompanyNames.has(name.toLocaleLowerCase("zh-CN")),
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
  const catalogInstitutionNames = new Set(
    relatedInstitutions.map((item) => item.name.toLocaleLowerCase("zh-CN")),
  );
  const observedInstitutions = unique(
    events.flatMap((event) => event.institutions ?? []),
    12,
  ).filter(
    (name) => !catalogInstitutionNames.has(name.toLocaleLowerCase("zh-CN")),
  );
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
  const coverage = sector.coverage;

  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>
            SECTOR DOSSIER · {coverage.label} · {sector.events} 项公开事件
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
          <small>
            {coverage.completedSources}/{coverage.expectedSources} 路爬虫完成
          </small>
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
                <p>包含本轮新抓取及从既有快照回填的相关事件。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>独立来源</span>
                <strong>{sector.sourceCount}</strong>
                <p>当前赛道事件对应的独立原始链接数量。</p>
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

          <Section id="爬取覆盖" title="赛道爬取覆盖">
            <p className={styles.lead}>{coverage.message}</p>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <span>发现源完成度</span>
                <strong>
                  {coverage.completedSources}/{coverage.expectedSources}
                </strong>
                <p>Bing、Google News 中文和 Google News 英文三路发现。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>扫描 / 接收</span>
                <strong>
                  {coverage.scanned} / {coverage.accepted}
                </strong>
                <p>本轮搜索结果扫描数与通过基础解析的记录数。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>历史回填</span>
                <strong>{coverage.backfilledArticles}</strong>
                <p>从现有情报库重新识别并归入该赛道的文章。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>失败来源</span>
                <strong>{coverage.failedSources}</strong>
                <p>最近一次覆盖检查中返回错误的发现源数量。</p>
              </div>
            </div>
          </Section>

          <Section id="中美对照" title="中美发展对照">
            <div className={styles.comparisonGrid}>
              <div className={styles.comparisonCard}>
                <span>中国</span>
                <strong>{chinaCompanies} 家目录公司</strong>
                <p>{sector.chinaLens}</p>
              </div>
              <div className={styles.comparisonCard}>
                <span>美国</span>
                <strong>{usCompanies} 家目录公司</strong>
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
                    <span>
                      {company.region} · {company.stage}
                    </span>
                    <strong>{company.name}</strong>
                    <p>{company.product}</p>
                  </Link>
                ))}
                {customCompanies.map((company) => (
                  <div className={styles.companyCard} key={company}>
                    <span className={styles.customBadge}>
                      {sector.tracking.sampleCompanies.includes(company)
                        ? "用户添加"
                        : "事件识别"}
                    </span>
                    <strong>{company}</strong>
                    <p>该主体已进入本赛道的搜索、事件归属和持续跟踪范围。</p>
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
            {relatedInstitutions.length || observedInstitutions.length ? (
              <div className={styles.entityGrid}>
                {relatedInstitutions.map((institution) => (
                  <Link
                    className={styles.institutionCard}
                    href={`/institutions/${institution.slug}`}
                    key={institution.slug}
                  >
                    <span>
                      {institution.region} · {institution.type}
                    </span>
                    <strong>{institution.name}</strong>
                    <p>
                      {institution.stages} · {institution.sectors.join("、")}
                    </p>
                  </Link>
                ))}
                {observedInstitutions.map((institution) => (
                  <div className={styles.institutionCard} key={institution}>
                    <span className={styles.customBadge}>事件识别</span>
                    <strong>{institution}</strong>
                    <p>该机构出现在本赛道已收录的论文或公开事件元数据中。</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>
                当前事件尚未识别出投资或研究机构；爬虫完成后会自动回填。
              </p>
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
              <p className={styles.empty}>
                {emptyEventMessage(coverage.status, coverage.message)}
              </p>
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
                    <span>
                      {report.date} · {report.sources} 个来源
                    </span>
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
              <p>
                数据更新：{coverage.lastRun?.slice(0, 10) || snapshotDate}
              </p>
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
