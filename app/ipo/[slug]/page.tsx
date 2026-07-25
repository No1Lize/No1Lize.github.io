import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  FinancialSeriesChart,
  MarketLineChart,
} from "@/components/market-line-chart";
import {
  companyFacts,
  intelligenceEvents,
  snapshotDate,
  type FinancialMetric,
  type IntelligenceEvent,
} from "@/lib/intelligence-data";
import {
  listedCompaniesForDisplay,
  listedCompanyBySlug,
} from "@/lib/listed-companies";
import { marketProfiles } from "@/lib/market-profile-data";
import { ipoProfiles } from "@/lib/research-content";

export function generateStaticParams() {
  return listedCompaniesForDisplay.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  return {
    title: `${listedCompanyBySlug.get(slug)?.name ?? "公司"}上市跟踪`,
  };
}

export default async function IpoDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const company = listedCompanyBySlug.get(slug);
  if (!company) notFound();

  const catalogSlug = company.catalogSlug ?? slug;
  const researchProfile = ipoProfiles[catalogSlug];
  const marketData = marketProfiles[slug];
  const displayName = marketData?.company.name || company.name;
  const facts =
    companyFacts[catalogSlug] ??
    Object.values(companyFacts).find(
      (item) => item.ticker.toUpperCase() === company.ticker.toUpperCase(),
    );
  const companyEvents = findCompanyEvents(
    slug,
    catalogSlug,
    displayName,
    company.name,
  );
  const filings = companyEvents
    .filter((event) => ["财报", "监管文件", "IPO"].includes(event.type))
    .slice(0, 12);
  const news = companyEvents
    .filter((event) => !["财报", "监管文件", "IPO"].includes(event.type))
    .slice(0, 10);
  const listedAt =
    marketData?.company.listedAt ?? researchProfile?.listedAt ?? "持续跟踪";
  const exchange =
    marketData?.company.exchange ?? researchProfile?.exchange ?? company.market;
  const description =
    marketData?.company.description ??
    marketData?.company.mainBusiness ??
    researchProfile?.description ??
    `${displayName}的公开市场、财务与公司披露跟踪页面。`;
  const sections = [
    "行情走势",
    "基本资料",
    "新闻公告",
    "财务分析",
    "经营分析",
    "上市概览",
    "状态时间线",
    "经营观察",
    "来源",
  ];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero market-entity-hero">
        <div>
          <p className="eyebrow">
            {company.market} · {company.sector}
          </p>
          <h1>{displayName}</h1>
          <p>{description}</p>
          <div className="hero-chips">
            <span>{company.ticker}</span>
            <span>{company.status}</span>
            <span>{exchange}</span>
            <span>
              {marketData?.status === "ok"
                ? "市场数据已同步"
                : marketData?.status === "partial"
                  ? "市场数据部分同步"
                  : "等待市场数据同步"}
            </span>
          </div>
        </div>
        <div className="hero-stat">
          <span>上市代码</span>
          <strong>{company.ticker}</strong>
          <small>{listedAt}</small>
        </div>
      </header>

      <div className="detail-layout market-detail-layout">
        <aside className="toc market-toc">
          <strong>同花顺内容</strong>
          {sections.map((item) => (
            <a href={`#${item}`} key={item}>
              {item}
            </a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="行情走势" title="行情走势">
            <MarketLineChart
              points={marketData?.priceHistory ?? []}
              market={company.market}
            />
          </Section>

          <Section id="基本资料" title="基本资料">
            <dl className="facts-grid market-facts-grid">
              <Fact label="证券代码" value={company.ticker} />
              <Fact label="交易市场" value={exchange} />
              <Fact label="上市日期" value={listedAt} />
              <Fact
                label="所属行业"
                value={marketData?.company.industry || company.sector}
              />
              <Fact label="董事长 / 负责人" value={marketData?.company.chairman} />
              <Fact label="员工人数" value={marketData?.company.employees} />
              <Fact label="公司网站" value={marketData?.company.website} />
              <Fact label="资料更新" value={marketData?.updatedAt?.slice(0, 10) || snapshotDate} />
            </dl>
            {marketData?.company.address && (
              <p className="data-note">办公 / 注册地址：{marketData.company.address}</p>
            )}
            <p>{description}</p>
          </Section>

          <Section id="新闻公告" title="新闻公告">
            {news.length || filings.length ? (
              <div className="timeline">
                {[...news.slice(0, 6), ...filings.slice(0, 4)]
                  .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
                  .map((event) => (
                    <EventRow event={event} key={event.id} />
                  ))}
              </div>
            ) : (
              <DataPending text="已建立公司页，等待新闻与公告抓取器完成首次归属。" />
            )}
          </Section>

          <Section id="财务分析" title="财务分析">
            {marketData?.metrics.length ? (
              <div className="market-metric-grid">
                {marketData.metrics.map((metric) => (
                  <div key={metric.id}>
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                    {metric.period && <small>{metric.period}</small>}
                  </div>
                ))}
              </div>
            ) : (
              <DataPending text="同花顺公开页暂未返回可验证的核心指标，旧快照不会被空结果覆盖。" />
            )}

            {marketData?.financialSeries.length ? (
              <div className="financial-series-grid">
                {marketData.financialSeries.map((series) => (
                  <FinancialSeriesChart series={series} key={series.id} />
                ))}
              </div>
            ) : null}

            {facts?.metrics.length ? (
              <>
                <h3 className="subsection-title">监管口径财务指标</h3>
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
              </>
            ) : null}
          </Section>

          <Section id="经营分析" title="经营分析">
            <div className="market-business-card">
              <span>主营业务</span>
              <strong>{displayName}</strong>
              <p>
                {marketData?.company.mainBusiness ||
                  marketData?.company.description ||
                  researchProfile?.description ||
                  "等待公开公司资料同步。"}
              </p>
            </div>
            <div className="analysis-grid">
              {(researchProfile?.watchItems ?? [company.sector, "收入质量", "现金流"])
                .slice(0, 4)
                .map((item, index) => (
                  <div key={item}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{item}</strong>
                    <p>结合公司公告、定期报告与业务进展持续验证。</p>
                  </div>
                ))}
            </div>
          </Section>

          <Section id="上市概览" title="上市概览">
            <dl className="facts-grid">
              <Fact label="证券代码" value={company.ticker} />
              <Fact label="交易所" value={exchange} />
              <Fact label="上市日期" value={listedAt} />
              <Fact label="资料更新" value={marketData?.updatedAt?.slice(0, 10) || snapshotDate} />
            </dl>
            <p>{description}</p>
          </Section>

          <Section id="状态时间线" title="状态时间线">
            <div className="timeline">
              <div>
                <time>{listedAt}</time>
                <div>
                  <strong>{exchange}挂牌</strong>
                  <p>
                    证券代码 {company.ticker}，当前状态为{company.status}。
                  </p>
                </div>
              </div>
              <div>
                <time>{marketData?.updatedAt?.slice(0, 10) || snapshotDate}</time>
                <div>
                  <strong>持续公开披露</strong>
                  <p>{company.latest}</p>
                </div>
              </div>
            </div>
          </Section>

          <Section id="经营观察" title="经营与资本市场观察">
            <div className="analysis-grid">
              {(researchProfile?.watchItems ?? [company.sector, "财务披露", "重大事项"]).map(
                (item, index) => (
                  <div key={item}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{item}</strong>
                    <p>结合定期报告、公司公告与业务进展跟踪变化。</p>
                  </div>
                ),
              )}
            </div>
          </Section>

          <Section id="来源" title="数据与监管来源">
            {marketData && (
              <a
                className="source-card"
                href={marketData.sources.tonghuashun}
                target="_blank"
                rel="noreferrer"
              >
                <span>数据库记录</span>
                <strong>同花顺公开公司页</strong>
                <small>{marketData.sources.tonghuashun}</small>
              </a>
            )}
            {marketData?.sources.price && (
              <a
                className="source-card"
                href={marketData.sources.price}
                target="_blank"
                rel="noreferrer"
              >
                <span>延迟公开行情</span>
                <strong>日线走势回退源</strong>
                <small>{marketData.sources.price}</small>
              </a>
            )}
            {company.source && (
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
            )}
            {facts && (
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
            )}
          </Section>
        </article>

        <aside className="source-rail market-source-rail">
          <div className="confidence-box">
            <span>行情交易日</span>
            <strong>{marketData?.priceHistory.length ?? 0}</strong>
            <p>延迟日线，不作为实时行情</p>
          </div>
          <div className="confidence-box">
            <span>核心指标</span>
            <strong>{marketData?.metrics.length ?? 0}</strong>
            <p>来自公开公司页面</p>
          </div>
          <div className="confidence-box">
            <span>新闻与监管文件</span>
            <strong>{companyEvents.length}</strong>
            <p>按公司实体自动归属</p>
          </div>
          {marketData?.warnings?.length ? (
            <div className="confidence-box warning-box">
              <span>数据说明</span>
              {marketData.warnings.slice(0, 3).map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}
        </aside>
      </div>
    </main>
  );
}

function findCompanyEvents(
  slug: string,
  catalogSlug: string,
  ...names: string[]
): IntelligenceEvent[] {
  const normalizedNames = names
    .map((name) => name.trim().toLocaleLowerCase("zh-CN"))
    .filter(Boolean);
  return intelligenceEvents
    .filter((event) => {
      if (event.companySlug === slug || event.companySlug === catalogSlug) return true;
      const company = event.company.toLocaleLowerCase("zh-CN");
      return normalizedNames.some(
        (name) => company === name || company.includes(name) || name.includes(company),
      );
    })
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
}

function EventRow({ event }: { event: IntelligenceEvent }) {
  return (
    <div>
      <time>{event.publishedAt}</time>
      <div>
        <strong>{event.title}</strong>
        <p>{event.summary}</p>
        <a href={event.source.url} target="_blank" rel="noreferrer">
          {event.source.name} →
        </a>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value || "—"}</dd>
    </div>
  );
}

function DataPending({ text }: { text: string }) {
  return (
    <div className="data-note">
      <strong>等待数据同步</strong>
      <p>{text}</p>
    </div>
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
