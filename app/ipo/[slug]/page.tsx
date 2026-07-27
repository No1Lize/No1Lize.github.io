import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalDatabaseLinks } from "@/components/external-database-links";
import { ResearchReportLibrary } from "@/components/research-report-library";
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
import {
  latestQuoteView,
  marketProfiles,
  quoteCurrencyPrefix,
  type MarketMetric,
  type MarketNewsItem,
} from "@/lib/market-profile-data";
import {
  companyDatabaseLinks,
  hanghangchaResearchLink,
} from "@/lib/external-database-links";
import { ipoProfiles } from "@/lib/research-content";
import { relatedResearchReports } from "@/lib/research-report-data";

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
  const rawDescription =
    marketData?.company.description ??
    marketData?.company.mainBusiness ??
    researchProfile?.description ??
    `${displayName}的公开市场、财务与公司披露跟踪页面。`;
  const detailDescription = composeDescription(
    rawDescription,
    marketData?.company.mainBusiness,
    360,
  );
  const heroDescription = clipAtSentence(detailDescription, 140);
  const region = marketData?.company.region || inferDisplayRegion(company.market);
  const marketCap = metricValue(marketData?.metrics, "marketCap");
  const quoteView = latestQuoteView(marketData);
  const marketNews: MarketNewsItem[] = marketData?.news ?? [];
  const relatedReports = relatedResearchReports({
    companySlug: slug,
    ticker: company.ticker,
    market: company.market,
    sector: company.sector,
    limit: 8,
  });
  const marketSections = ["行情走势", "基本资料", "新闻公告", "财务分析", "经营分析"];
  const archiveSections = ["上市概览", "状态时间线", "经营观察", "来源", "研报与行业研究"];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero market-entity-hero">
        <div>
          <p className="eyebrow">
            {company.market} · {company.sector}
          </p>
          <h1>{displayName}</h1>
          <p className="market-hero-description">{heroDescription}</p>
          <div className="hero-chips">
            <span>{company.ticker}</span>
            <span>{company.status}</span>
            <span>{exchange}</span>
            <span>{region}</span>
            <span>
              {marketData?.status === "ok"
                ? "市场数据已同步"
                : marketData?.status === "partial"
                  ? "市场数据部分同步"
                  : "等待市场数据同步"}
            </span>
          </div>
        </div>
        <div className="market-hero-stats" data-cols={quoteView ? "3" : "2"}>
          <div className="hero-stat">
            <span>上市代码</span>
            <strong>{company.ticker}</strong>
            <small>{listedAt}</small>
          </div>
          {quoteView && (
            <div className="hero-stat" data-direction={quoteView.direction}>
              <span>{quoteView.delayed ? "最近收盘" : "最新价"}</span>
              <strong className="market-cap-value">{quoteView.price}</strong>
              <small>
                {quoteView.changePercent >= 0 ? "+" : ""}
                {quoteView.changePercent.toFixed(2)}% ·{" "}
                {quoteView.delayed ? "延迟行情" : quoteView.sourceName ?? "公开报价"}
              </small>
            </div>
          )}
          <div className="hero-stat">
            <span>总市值</span>
            <strong className="market-cap-value">{marketCap || "待同步"}</strong>
            <small>延迟公开报价</small>
          </div>
        </div>
      </header>

      <div className="detail-layout market-detail-layout">
        <aside className="toc market-toc">
          <strong>同花顺内容</strong>
          {marketSections.map((item) => (
            <a href={`#${item}`} key={item}>{item}</a>
          ))}
          <strong className="toc-group-title">上市档案</strong>
          {archiveSections.map((item) => (
            <a href={`#${item}`} key={item}>{item}</a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="行情走势" title="行情走势">
            {marketData?.quote && (
              <div
                className="market-live-quote"
                data-direction={
                  (marketData.quote.changePercent ?? 0) > 0
                    ? "up"
                    : (marketData.quote.changePercent ?? 0) < 0
                      ? "down"
                      : "flat"
                }
              >
                <div className="market-live-price">
                  <span>最新价 · {marketData.quote.source?.name ?? "公开报价"}</span>
                  <strong>
                    {quoteCurrencyPrefix(marketData.quote, company.market)}
                    {marketData.quote.price.toFixed(2)}
                  </strong>
                  <small>
                    {signedFixed(marketData.quote.change)} ·{" "}
                    {signedFixed(marketData.quote.changePercent)}%
                  </small>
                </div>
                <dl className="market-live-facts">
                  <div>
                    <dt>昨收</dt>
                    <dd>
                      {marketData.quote.previousClose !== undefined
                        ? marketData.quote.previousClose.toFixed(2)
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>币种</dt>
                    <dd>{marketData.quote.currency ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>更新时间</dt>
                    <dd>{formatQuoteTime(marketData.quote.asOf)}</dd>
                  </div>
                  <div>
                    <dt>来源</dt>
                    <dd>
                      {marketData.quote.source ? (
                        <a
                          href={marketData.quote.source.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {marketData.quote.source.name} →
                        </a>
                      ) : (
                        "公开延迟报价"
                      )}
                    </dd>
                  </div>
                </dl>
              </div>
            )}
            <MarketLineChart
              points={marketData?.priceHistory ?? []}
              market={company.market}
              metrics={marketData?.metrics ?? []}
            />
          </Section>

          <Section id="基本资料" title="基本资料">
            <dl className="facts-grid market-facts-grid">
              <Fact label="证券代码" value={company.ticker} />
              <Fact label="交易市场" value={exchange} />
              <Fact label="上市日期" value={listedAt} />
              <Fact label="所属地域" value={region} />
              <Fact
                label="所属行业"
                value={marketData?.company.industry || company.sector}
              />
              <Fact label="总市值" value={marketCap} />
              <Fact label="董事长 / 负责人" value={marketData?.company.chairman} />
              <Fact label="员工人数" value={marketData?.company.employees} />
              <Fact label="公司网站" value={marketData?.company.website} />
              <Fact label="资料更新" value={marketData?.updatedAt?.slice(0, 10) || snapshotDate} />
            </dl>
            {marketData?.company.address && (
              <p className="data-note">办公 / 注册地址：{marketData.company.address}</p>
            )}
            <div className="company-description-card">
              <span>公司简介</span>
              <p>{detailDescription}</p>
              <small>已自动移除冗长荣誉列表，并在完整语句处截断。</small>
            </div>
          </Section>

          <Section id="新闻公告" title="新闻公告">
            {marketNews.length ? (
              <>
                <h3 className="subsection-title">
                  市场新闻速览 · Yahoo财经 / 新浪财经
                </h3>
                <div className="market-news-list">
                  {marketNews.map((item) => (
                    <a
                      key={item.url}
                      className="market-news-item"
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <time>{formatQuoteTime(item.publishedAt)}</time>
                      <strong>{item.title}</strong>
                      <span
                        className="market-news-source"
                        data-source={item.source === "Yahoo财经" ? "yahoo" : "sina"}
                      >
                        {item.source}
                      </span>
                    </a>
                  ))}
                </div>
                <p className="data-note">
                  以上条目仅保存公开标题、时间与原文链接，点击跳转到 Yahoo财经或新浪财经原文。
                </p>
              </>
            ) : null}
            {news.length || filings.length ? (
              <>
                {marketNews.length ? (
                  <h3 className="subsection-title">公司事件与披露归属</h3>
                ) : null}
                <div className="timeline">
                  {[...news.slice(0, 6), ...filings.slice(0, 4)]
                    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
                    .map((event) => <EventRow event={event} key={event.id} />)}
                </div>
              </>
            ) : !marketNews.length ? (
              <DataPending text="已建立公司页，等待新闻与公告抓取器完成首次归属。" />
            ) : null}
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
              <DataPending text="公开公司页暂未返回可验证的核心指标，旧快照不会被空结果覆盖。" />
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
                        报告期 {metric.periodEnd} · {metric.form} · {metric.fiscalPeriod ?? "报告期"}
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
                {composeDescription(
                  marketData?.company.mainBusiness || detailDescription,
                  detailDescription,
                  240,
                )}
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
              <Fact label="所属地域" value={region} />
              <Fact label="总市值" value={marketCap} />
              <Fact label="资料更新" value={marketData?.updatedAt?.slice(0, 10) || snapshotDate} />
            </dl>
            <p>{detailDescription}</p>
          </Section>

          <Section id="状态时间线" title="状态时间线">
            <div className="timeline">
              <div>
                <time>{listedAt}</time>
                <div>
                  <strong>{exchange}挂牌</strong>
                  <p>证券代码 {company.ticker}，当前状态为{company.status}。</p>
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
              <a className="source-card" href={marketData.sources.tonghuashun} target="_blank" rel="noreferrer">
                <span>公司资料</span>
                <strong>同花顺公开公司页</strong>
                <small>{marketData.sources.tonghuashun}</small>
              </a>
            )}
            {marketData?.sources.quote && (
              <a className="source-card" href={marketData.sources.quote} target="_blank" rel="noreferrer">
                <span>公开报价快照</span>
                <strong>总市值、估值与交易指标补全源</strong>
                <small>{marketData.sources.quote}</small>
              </a>
            )}
            {marketData?.sources.price && (
              <a className="source-card" href={marketData.sources.price} target="_blank" rel="noreferrer">
                <span>延迟公开行情</span>
                <strong>历史日线走势源</strong>
                <small>{marketData.sources.price}</small>
              </a>
            )}
            {marketData?.sources.yahooFinance && (
              <a className="source-card" href={marketData.sources.yahooFinance} target="_blank" rel="noreferrer">
                <span>行情快照与新闻</span>
                <strong>Yahoo财经（新加坡站）公司页</strong>
                <small>{marketData.sources.yahooFinance}</small>
              </a>
            )}
            {marketData?.sources.sinaFinance && (
              <a className="source-card" href={marketData.sources.sinaFinance} target="_blank" rel="noreferrer">
                <span>行情快照与新闻</span>
                <strong>新浪财经公司页</strong>
                <small>{marketData.sources.sinaFinance}</small>
              </a>
            )}
            {company.source && (
              <a className="source-card" href={company.source.url} target="_blank" rel="noreferrer">
                <span>{company.source.level}</span>
                <strong>{company.source.name}</strong>
                <small>{company.source.url}</small>
              </a>
            )}
            {facts && (
              <a className="source-card" href={facts.source.url} target="_blank" rel="noreferrer">
                <span>{facts.source.level}</span>
                <strong>{facts.source.name}</strong>
                <small>CIK {facts.cik} · {facts.entityName}</small>
              </a>
            )}
            <ExternalDatabaseLinks
              links={companyDatabaseLinks(
                displayName,
                company.market === "美股" ? "美国" : "中国",
              )}
            />
          </Section>

          <Section id="研报与行业研究" title="研报与行业研究">
            <p className="research-directory-intro">
              这里直接展示与“{displayName}”、代码“{company.ticker}”及行业“{marketData?.company.industry || company.sector}”相关的已归档 PDF。
              点击卡片进入站内阅读，不再跳转到第三方研报首页。
            </p>
            <ResearchReportLibrary reports={relatedReports} compact />
            <Link className="source-card" href="/reports">
              <span>06 / RESEARCH</span>
              <strong>查看全部公开研报 PDF</strong>
              <small>按公司、代码、机构和行业统一检索 →</small>
            </Link>
            <ExternalDatabaseLinks
              links={[
                hanghangchaResearchLink(company.name, "公司与行业研报公开索引检索"),
              ].filter((link): link is NonNullable<typeof link> => Boolean(link))}
              lead="以下入口跳转到外部研报数据库检索本公司与所属行业；报告在对方平台查看，本站不抓取、不缓存其内容。"
            />
          </Section>
        </article>

        <aside className="source-rail market-source-rail">
          <div className="confidence-box">
            <span>总市值</span>
            <strong>{marketCap || "待同步"}</strong>
            <p>公开延迟报价</p>
          </div>
          <div className="confidence-box">
            <span>所属地域</span>
            <strong>{region}</strong>
            <p>公司资料与地址归一化</p>
          </div>
          <div className="confidence-box">
            <span>行情交易日</span>
            <strong>{marketData?.priceHistory.length ?? 0}</strong>
            <p>延迟日线，不作为实时行情</p>
          </div>
          <div className="confidence-box">
            <span>核心指标</span>
            <strong>{marketData?.metrics.length ?? 0}</strong>
            <p>公司资料与报价快照合并</p>
          </div>
          <div className="confidence-box">
            <span>市场新闻速览</span>
            <strong>{marketNews.length}</strong>
            <p>Yahoo财经 / 新浪财经标题条目</p>
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

function metricValue(metrics: MarketMetric[] | undefined, id: string) {
  return metrics?.find((metric) => metric.id === id)?.value || "";
}

function signedFixed(value: number | undefined, digits = 2) {
  if (value === undefined || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function formatQuoteTime(value: string | undefined) {
  if (!value) return "—";
  return value.slice(0, 16).replace("T", " ");
}

function inferDisplayRegion(market: "A股" | "港股" | "美股") {
  if (market === "港股") return "中国香港";
  if (market === "美股") return "美国";
  return "中国";
}

function cleanDisplayText(value: string) {
  return value
    .replace(/\s+/g, " ")
    .replace(/公司成立至今共获得多项荣誉[\s\S]*$/u, "")
    .replace(/公司先后获得多项荣誉[\s\S]*$/u, "")
    .trim()
    .replace(/[，；;\s]+$/u, "");
}

function clipAtSentence(value: string, maxLength: number) {
  const text = cleanDisplayText(value);
  if (text.length <= maxLength) return ensureSentence(text);
  const clipped = text.slice(0, maxLength);
  const sentenceEnd = Math.max(clipped.lastIndexOf("。"), clipped.lastIndexOf("！"), clipped.lastIndexOf("？"));
  if (sentenceEnd >= Math.max(50, Math.floor(maxLength * 0.55))) {
    return clipped.slice(0, sentenceEnd + 1);
  }
  const commaEnd = Math.max(clipped.lastIndexOf("，"), clipped.lastIndexOf("；"));
  return ensureSentence((commaEnd >= 60 ? clipped.slice(0, commaEnd) : clipped).trim());
}

function ensureSentence(value: string) {
  if (!value) return "等待公开公司资料同步。";
  return /[。！？]$/u.test(value) ? value : `${value}。`;
}

function composeDescription(primary: string, secondary: string | undefined, maxLength: number) {
  let value = cleanDisplayText(primary);
  const fallback = cleanDisplayText(secondary || "");
  if (value.length < 70 && fallback && !value.includes(fallback) && !fallback.includes(value)) {
    value = `${value} ${fallback}`.trim();
  }
  return clipAtSentence(value, maxLength);
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
      const eventCompany = event.company.toLocaleLowerCase("zh-CN");
      return normalizedNames.some(
        (name) => eventCompany === name || eventCompany.includes(name) || name.includes(eventCompany),
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
