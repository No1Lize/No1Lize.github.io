"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import { coreTechnologyEntities } from "@/lib/core-research-objects";
import { researchPeople } from "@/lib/people-data";
import { trackedSectors } from "@/lib/tracked-sectors";
import { useArticles } from "@/lib/use-articles";

const staticRecords = [
  ...coreTechnologyEntities.map((item) => ({
    type: "技术",
    title: item.name,
    text: `${item.summary} · ${item.trackNames.join(" / ")}`,
    href: `/tracking/entities/topic/${item.slug}`,
    region: "全球",
  })),
  ...trackedSectors.map((item) => ({
    type: "赛道",
    title: item.name,
    text: `热度 ${item.heat} · 数据完整度 ${item.completeness}%`,
    href: `/technology/${item.slug}`,
    region: "全球",
  })),
  ...researchPeople.map((item) => ({
    type: "人物",
    title: item.name,
    text: item.summary,
    href: `/people/${item.slug}`,
    region: "全球",
  })),
  ...companies.map((item) => ({
    type: "公司",
    title: item.name,
    text: item.summary,
    href: `/companies/${item.slug}`,
    region: item.region,
  })),
  ...institutionCatalog.map((item) => ({
    type: "资料",
    title: item.name,
    text: `投资机构 · ${item.stages} · ${item.sectors.join(" / ")}`,
    href: `/institutions/${item.slug}`,
    region: item.region,
  })),
  ...reports.map((item) => ({
    type: "资料",
    title: item.title,
    text: `研究报告 · ${item.summary}`,
    href: `/reports/${item.slug}`,
    region: "全球",
  })),
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
      ...articles.map((item) => ({
        type: "事件",
        title: item.title,
        text: item.summary,
        href: item.companySlug ? `/companies/${item.companySlug}` : item.source.url,
        region: item.region,
      })),
    ];
    return records
      .filter(
        (item) =>
          (type === "全部" || item.type === type) &&
          `${item.title}${item.text}`.toLowerCase().includes(normalized),
      )
      .slice(0, 30);
  }, [articles, query, type]);

  return (
    <div className="search-workspace">
      <div className="global-search-box">
        <Search size={22} />
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索核心技术、赛道、人物、公司或证据资料"
          aria-label="全局搜索关键词"
        />
      </div>
      <div className="search-types">
        {["全部", "技术", "赛道", "人物", "公司", "资料", "事件"].map((item) => (
          <button
            className={type === item ? "active" : ""}
            onClick={() => setType(item)}
            key={item}
          >
            {item}
          </button>
        ))}
      </div>
      {!query && (
        <div className="search-guide">
          <strong>从四类研究对象开始</strong>
          <p>可尝试：推理芯片、具身智能、某位创始人或一家核心公司。</p>
        </div>
      )}
      {query && !matches.length && (
        <div className="empty-state">
          <Search size={22} />
          <strong>没有匹配记录</strong>
          <p>换一个关键词，或清除类型筛选。</p>
        </div>
      )}
      <div className="search-results">
        {matches.map((item, index) => (
          <Link href={item.href} key={`${item.type}-${item.title}-${index}`}>
            <span>{item.type}</span>
            <div>
              <h2>{item.title}</h2>
              <p>{item.text}</p>
            </div>
            <small>{item.region}</small>
          </Link>
        ))}
      </div>
    </div>
  );
}
