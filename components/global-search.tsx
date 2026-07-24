"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { companies, institutionCatalog, people, reports } from "@/lib/catalog-data";
import { sectors } from "@/lib/intelligence-data";
import { useArticles } from "@/lib/use-articles";

const staticRecords = [
  ...companies.map((item) => ({ type:"公司", title:item.name, text:item.summary, href:`/companies/${item.slug}`, region:item.region })),
  ...institutionCatalog.map((item) => ({ type:"机构", title:item.name, text:`${item.stages} · ${item.sectors.join(" / ")}`, href:`/institutions/${item.slug}`, region:item.region })),
  ...people.map((item) => ({ type:"人物", title:item.name, text:item.summary, href:`/people/${item.slug}`, region:"全球" })),
  ...reports.map((item) => ({ type:"报告", title:item.title, text:item.summary, href:`/reports/${item.slug}`, region:"全球" })),
  ...sectors.map((item) => ({ type:"赛道", title:item.name, text:`热度 ${item.heat} · 数据完整度 ${item.completeness}%`, href:`/technology/${item.slug}`, region:"全球" })),
];

export function GlobalSearch() {
  const { articles } = useArticles();
  const [query, setQuery] = useState("");
  const [type, setType] = useState("全部");
  const matches = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];
    const records = [
      ...staticRecords,
      ...articles.map((item) => ({ type:"事件", title:item.title, text:item.summary, href:item.companySlug ? `/companies/${item.companySlug}` : item.source.url, region:item.region })),
    ];
    return records.filter((item) => (type === "全部" || item.type === type) && `${item.title}${item.text}`.toLowerCase().includes(normalized)).slice(0, 30);
  }, [articles, query, type]);

  return (
    <div className="search-workspace">
      <div className="global-search-box"><Search size={22}/><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索公司、机构、赛道、人物、报告或事件" aria-label="全局搜索关键词" /></div>
      <div className="search-types">{["全部","公司","机构","赛道","人物","报告","事件"].map((item) => <button className={type === item ? "active" : ""} onClick={() => setType(item)} key={item}>{item}</button>)}</div>
      {!query && <div className="search-guide"><strong>从一个实体开始</strong><p>可尝试：OpenAI、机器人、红杉、巴菲特或 AI 芯片。</p></div>}
      {query && !matches.length && <div className="empty-state"><Search size={22}/><strong>没有匹配记录</strong><p>换一个关键词，或清除类型筛选。</p></div>}
      <div className="search-results">{matches.map((item, index) => <Link href={item.href} key={`${item.type}-${item.title}-${index}`}><span>{item.type}</span><div><h2>{item.title}</h2><p>{item.text}</p></div><small>{item.region}</small></Link>)}</div>
    </div>
  );
}
