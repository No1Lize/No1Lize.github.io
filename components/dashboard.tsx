"use client";

import { ArrowUpRight, ChevronRight, Info, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  focusCompanies,
  heatMethodology,
  institutions,
  sectors,
  type EventType,
} from "@/lib/intelligence-data";
import { useArticles } from "@/lib/use-articles";

const regions = ["全部", "中国", "美国"] as const;
const eventTypes = ["全部", "融资", "产业投资", "产品发布", "技术突破", "监管文件"] as const;

export function Dashboard() {
  const { articles, generatedAt, isLive } = useArticles();
  const [region, setRegion] = useState<(typeof regions)[number]>("全部");
  const [eventType, setEventType] = useState<(typeof eventTypes)[number]>("全部");
  const [query, setQuery] = useState("");
  const [showMethod, setShowMethod] = useState(false);

  const visibleEvents = useMemo(
    () =>
      articles
        .filter((item) => region === "全部" || item.region === region)
        .filter((item) => eventType === "全部" || item.type === (eventType as EventType))
        .filter((item) => `${item.title}${item.summary}${item.company}`.toLowerCase().includes(query.toLowerCase()))
        .sort((a, b) => b.importance - a.importance),
    [articles, eventType, query, region],
  );
  const sourceCount = new Set(articles.map((item) => item.source.url)).size;
  const sectorCount = new Set(articles.map((item) => item.sector)).size;
  const chinaCount = articles.filter((item) => item.region === "中国").length;
  const usCount = articles.filter((item) => item.region === "美国").length;

  return (
    <>
      <section className="dashboard-intro">
        <div>
          <p className="eyebrow">DAILY INTELLIGENCE DESK · 中美双轨</p>
          <h1>把公开信息，变成可追溯的判断依据。</h1>
          <p className="intro-copy">
            聚合公司、监管机构与投资机构的原始披露。事实、计算与分析分层呈现，不用未经核验的数字填补信息空白。
          </p>
        </div>
        <div className="snapshot-card">
          <div className="snapshot-top">
            <span>公开资料快照 · {generatedAt.slice(0, 10)}</span>
            <span className="status-pill"><i /> {isLive ? "已同步" : "内置快照"}</span>
          </div>
          <strong>{String(articles.length).padStart(2, "0")}</strong>
          <p>已核验关键事件</p>
          <div className="snapshot-meta">
            <span>{sourceCount} 个原始链接</span>
            <span>覆盖 {sectorCount} 个赛道</span>
          </div>
        </div>
      </section>

      <section className="market-strip" aria-label="中美科技投资概览">
        <MarketSummary market="中国" amount="按披露口径" events={String(chinaCount).padStart(2, "0")} sector="AI / 机器人" />
        <div className="market-divider"><span>CN</span><i /><span>US</span></div>
        <MarketSummary market="美国" amount="按披露口径" events={String(usCount).padStart(2, "0")} sector="AI / 机器人" />
      </section>

      <section className="content-grid">
        <div className="primary-column">
          <div className="section-heading">
            <div>
              <p className="section-index">01 / KEY EVENTS</p>
              <h2>关键事件</h2>
            </div>
            <span>{visibleEvents.length} 条可追溯记录</span>
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
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索公司或事件" aria-label="搜索关键事件" />
            </label>
          </div>

          <div className="event-list">
            {visibleEvents.length ? visibleEvents.map((item) => (
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
                  <h3>{item.companySlug ? <Link href={`/companies/${item.companySlug}`}>{item.title}</Link> : item.title}</h3>
                  <p>{item.summary}</p>
                  <a className="source-link" href={item.source.url} target="_blank" rel="noreferrer">
                    {item.source.level} · {item.source.name}
                    <ArrowUpRight size={14} />
                  </a>
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
                <p>尝试清除关键词或切换地区。系统不会用模拟数据补齐空白。</p>
              </div>
            )}
          </div>
        </div>

        <aside className="side-column">
          <div className="section-heading compact">
            <div>
              <p className="section-index">02 / SECTOR HEAT</p>
              <h2>赛道热度</h2>
            </div>
            <button className="method-button" onClick={() => setShowMethod(!showMethod)}><Info size={15} /> 口径</button>
          </div>
          {showMethod && <p className="method-note">{heatMethodology}</p>}
          <div className="heat-list">
            {sectors.slice(0, 7).map((sector, index) => (
              <Link href={`/technology/${sector.slug}`} className="heat-row" key={sector.slug}>
                <span className="heat-rank">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{sector.name}</strong>
                  <span>{sector.events} 事件 · 完整度 {sector.completeness}%</span>
                </div>
                <div className="heat-meter"><i style={{ width: `${sector.heat}%` }} /></div>
                <b>{sector.heat}</b>
              </Link>
            ))}
          </div>
          <Link className="text-link" href="/technology">查看全部十个赛道 <ChevronRight size={15} /></Link>
        </aside>
      </section>

      <section className="lower-grid">
        <div className="panel">
          <div className="section-heading compact">
            <div><p className="section-index">03 / FOCUS COMPANIES</p><h2>本周重点项目</h2></div>
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
            <div><p className="section-index">04 / INSTITUTIONS</p><h2>机构活跃度</h2></div>
            <Link href="/institutions">机构库</Link>
          </div>
          {institutions.slice(0, 6).map((institution) => (
            <div className="institution-row" key={institution.name}>
              <div><strong>{institution.name}</strong><span>{institution.region} · {institution.focus}</span></div>
              <div className="institution-score"><i style={{ width: `${institution.activity}%` }} /></div>
              <b>{institution.activity}</b>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function MarketSummary({ market, amount, events, sector }: { market: string; amount: string; events: string; sector: string }) {
  return (
    <div className="market-summary">
      <div className="market-name"><span>{market === "中国" ? "CN" : "US"}</span><strong>{market}</strong></div>
      <dl>
        <div><dt>样本事件</dt><dd>{events}</dd></div>
        <div><dt>披露金额</dt><dd>{amount}</dd></div>
        <div><dt>高活跃赛道</dt><dd>{sector}</dd></div>
      </dl>
    </div>
  );
}
