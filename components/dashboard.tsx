"use client";

import { ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { EventQualityIndicator } from "@/components/event-quality-indicator";
import qualityStyles from "@/components/dashboard-quality.module.css";
import { institutionCatalog } from "@/lib/catalog-data";
import {
  focusCompanies,
  type EventType,
  type IntelligenceEvent,
} from "@/lib/intelligence-data";
import { getInstitutionProfile } from "@/lib/research-content";
import { trackedSectors } from "@/lib/tracked-sectors";
import { useArticles } from "@/lib/use-articles";

const regions = ["全部", "中国", "美国", "全球"] as const;
const eventTypes = [
  "全部",
  "融资",
  "产业投资",
  "并购",
  "IPO",
  "财报",
  "政策",
  "监管文件",
  "商业进展",
  "产品发布",
  "技术突破",
  "公司动态",
  "论文",
  "人物观点",
] as const;

const enabledSectorNames = new Set(
  trackedSectors.flatMap((sector) => sector.aliases),
);

export function Dashboard({
  middle,
  children,
}: {
  middle?: ReactNode;
  children: ReactNode;
}) {
  const { articles, generatedAt, isLive, sourceStatus, qualityGate } = useArticles();
  const [region, setRegion] = useState<(typeof regions)[number]>("全部");
  const [eventType, setEventType] = useState<(typeof eventTypes)[number]>("全部");
  const [query, setQuery] = useState("");

  const activeArticles = useMemo(
    () => articles.filter((item) => enabledSectorNames.has(item.sector)),
    [articles],
  );
  const latestPublishedAt = useMemo(
    () =>
      activeArticles.reduce(
        (latest, item) => (item.publishedAt > latest ? item.publishedAt : latest),
        "",
      ),
    [activeArticles],
  );
  const processedAt = formatTaipeiDate(generatedAt);
  const freshnessLabel = !isLive
    ? "内置快照"
    : latestPublishedAt === processedAt
      ? "当日情报已更新"
      : "内容待刷新";
  const normalizedQuery = query.trim().toLowerCase();
  const visibleEvents = useMemo(
    () =>
      activeArticles
        .filter((item) => region === "全部" || item.region === region)
        .filter((item) => eventType === "全部" || item.type === (eventType as EventType))
        .filter((item) => {
          if (!normalizedQuery) return true;
          const searchableText = [
            item.title,
            item.summary,
            item.company,
            item.sector,
            item.type,
            item.region,
            item.source.name,
            item.source.platform,
            item.source.level,
            item.wechatAccount,
            ...(item.authors ?? []),
            ...(item.mentionedCompanies ?? []),
            ...(item.mentionedPeople ?? []),
            ...(item.matchedTrackingTerms ?? []),
            ...(item.relatedSources ?? []).flatMap((source) => [
              source.name,
              source.platform,
              source.title,
            ]),
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return searchableText.includes(normalizedQuery);
        })
        .sort(
          (a, b) =>
            b.publishedAt.localeCompare(a.publishedAt) ||
            b.importance - a.importance,
        ),
    [activeArticles, eventType, normalizedQuery, region],
  );
  const displayedEvents = visibleEvents.slice(0, 80);
  const sourceCount = new Set(activeArticles.map((item) => item.source.url)).size;
  const platformCount = new Set(
    activeArticles.map((item) => item.source.platform).filter(Boolean),
  ).size;
  const activeSourceIds = new Set(activeArticles.map((item) => item.sourceId).filter(Boolean));
  const healthySourceCount = sourceStatus.filter(
    (item) =>
      activeSourceIds.has(item.id) &&
      ["ok", "partial"].includes(item.status) &&
      item.accepted > 0,
  ).length;
  const trackingQuality = qualityGate?.trackingQuality;
  const sectorCount = trackedSectors.length;
  const chinaCount = activeArticles.filter((item) => item.region === "中国").length;
  const usCount = activeArticles.filter((item) => item.region === "美国").length;
  const marketSourceCount = (market: "中国" | "美国") =>
    new Set(
      activeArticles
        .filter((item) => item.region === market)
        .map((item) => item.source.url),
    ).size;
  const topSector = (market: "中国" | "美国") => {
    const counts = new Map<string, number>();
    activeArticles
      .filter((item) => item.region === market)
      .forEach((item) => counts.set(item.sector, (counts.get(item.sector) ?? 0) + 1));
    return (
      [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "持续更新"
    );
  };
  const institutions = institutionCatalog
    .map((institution) => ({
      ...institution,
      portfolioCount: getInstitutionProfile(institution).portfolio.length,
    }))
    .sort((a, b) => b.portfolioCount - a.portfolioCount);

  return (
    <>
      <section className="dashboard-intro">
        <div>
          <p className="eyebrow">DAILY INTELLIGENCE DESK · 中美双轨</p>
          <h1>科技投资，每一天进步一点点！</h1>
          <p className="intro-copy">
            持续读取公司与监管披露、金融创投媒体、新浪、X、微信公开索引及开放论文数据库，连接中美科技公司的产品、融资、经营、研究与资本市场进展。
          </p>
        </div>
      </section>

      <section className="market-strip" aria-label="中美科技投资概览">
        <MarketSummary market="中国" sources={marketSourceCount("中国")} events={String(chinaCount).padStart(2, "0")} sector={topSector("中国")} />
        <div className="market-divider"><span>CN</span><i /><span>US</span></div>
        <MarketSummary market="美国" sources={marketSourceCount("美国")} events={String(usCount).padStart(2, "0")} sector={topSector("美国")} />
      </section>

      <section className="content-grid">
        <div className="primary-column">
          <div className="section-heading">
            <div>
              <p className="section-index">01 / KEY EVENTS</p>
              <h2>关键事件</h2>
            </div>
            <span>
              {displayedEvents.length < visibleEvents.length
                ? `显示最新 ${displayedEvents.length} / ${visibleEvents.length} 条可追溯记录`
                : `最新 ${visibleEvents.length} 条可追溯记录`}
            </span>
          </div>

          <div className="filter-bar">
            <div className="segmented" aria-label="地区筛选">
              {regions.map((item) => (
                <button className={region === item ? "active" : ""} key={item} onClick={() => setRegion(item)}>{item}</button>
              ))}
            </div>
            <select value={eventType} onChange={(event) => setEventType(event.target.value as (typeof eventTypes)[number])} aria-label="事件类型">
              {eventTypes.map((item) => <option key={item}>{item}</option>)}
            </select>
            <label className="inline-search">
              <Search size={15} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索公司、事件或媒体" aria-label="搜索公司、事件或媒体" />
            </label>
          </div>

          <div className="event-list">
            {displayedEvents.length ? displayedEvents.map((item) => (
              <article className="event-row" key={item.id}>
                <div className="event-date">
                  <strong>{item.publishedAt.slice(5)}</strong>
                  <span>{item.publishedAt.slice(0, 4)}</span>
                </div>
                <div className="event-main">
                  <div className="event-tags">
                    <span className={`tag tag-${item.type}`}>{item.type}</span>
                    <span>{item.region}</span>
                    <span>{item.sector}</span>
                  </div>
                  <h3><EventTitle item={item} /></h3>
                  <p>{item.summary}</p>
                  <a className="source-link" href={item.source.url} target="_blank" rel="noreferrer">
                    {item.source.level} · {item.source.platform ? `${item.source.platform} · ` : ""}{item.source.name}
                    <ArrowUpRight size={14} />
                  </a>
                  <EventQualityIndicator item={item} />
                </div>
                <div className="importance" title="按事件规模、信源等级与产业影响计算">
                  <span>重要度</span>
                  <strong>{item.importance}</strong>
                </div>
              </article>
            )) : (
              <div className="empty-state">
                <Search size={22} />
                <strong>当前筛选没有结果</strong>
                <p>搜索会同时受地区和事件类型限制；可切换为“全部”后再次搜索媒体、公司或事件。</p>
              </div>
            )}
          </div>
        </div>

        {middle}

        <div className="side-column-stack">
          {children}
          <div className="snapshot-card">
            <div className="snapshot-top">
              <span>最新情报 · {latestPublishedAt || "暂无"}</span>
              <span className="status-pill"><i /> {freshnessLabel}</span>
            </div>
            <strong>{String(activeArticles.length).padStart(2, "0")}</strong>
            <p>
              {qualityGate?.passed === false
                ? "数据质量门未通过"
                : isLive && latestPublishedAt !== processedAt
                  ? "数据已处理，但最新情报仍待刷新"
                  : "当前启用赛道的可追溯公开情报"}
            </p>
            <div className="snapshot-meta">
              <span>{healthySourceCount || sourceCount} 个有效来源</span>
              <span>{platformCount} 类平台 · {sectorCount} 个启用赛道</span>
              <span>数据处理 · {processedAt}</span>
            </div>
            {trackingQuality && (
              <p className={qualityStyles.trackingSummary}>
                用户追踪：{trackingQuality.acceptedUserArticles} 条通过 · {trackingQuality.rejectedUserArticles} 条过滤 · {trackingQuality.clusteredDuplicates} 条重复报道已聚合
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="lower-grid">
        <div className="panel">
          <div className="section-heading compact">
            <div><p className="section-index">04 / FOCUS COMPANIES</p><h2>本周重点项目</h2></div>
            <Link href="/companies">全部案例</Link>
          </div>
          <div className="company-grid">
            {focusCompanies.slice(0, 6).map((company) => (
              <Link className="company-card" href={`/companies/${company.slug}`} key={company.slug}>
                <div className="company-monogram">{company.name.slice(0, 2).toUpperCase()}</div>
                <div><h3>{company.name}</h3><p>{company.focus}</p></div>
                <span>{company.region} · {company.stage}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="panel institution-panel">
          <div className="section-heading compact">
            <div><p className="section-index">05 / INSTITUTIONS</p><h2>机构活跃度</h2></div>
            <Link href="/institutions">机构库</Link>
          </div>
          {institutions.slice(0, 6).map((institution) => (
            <Link className="institution-row" href={`/institutions/${institution.slug}`} key={institution.name}>
              <div><strong>{institution.name}</strong><span>{institution.region} · {institution.sectors.join(" / ")}</span></div>
              <span className="institution-sample">公开组合</span>
              <b>{institution.portfolioCount}</b>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

function formatTaipeiDate(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value.slice(0, 10);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(timestamp);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function EventTitle({ item }: { item: IntelligenceEvent }) {
  return (
    <a href={item.source.url} target="_blank" rel="noreferrer">
      {item.title}
    </a>
  );
}

function MarketSummary({ market, sources, events, sector }: { market: string; sources: number; events: string; sector: string }) {
  return (
    <div className="market-summary">
      <div className="market-name"><span>{market === "中国" ? "CN" : "US"}</span><strong>{market}</strong></div>
      <dl>
        <div><dt>样本事件</dt><dd>{events}</dd></div>
        <div><dt>原始来源</dt><dd>{sources}</dd></div>
        <div><dt>高活跃赛道</dt><dd>{sector}</dd></div>
      </dl>
    </div>
  );
}
