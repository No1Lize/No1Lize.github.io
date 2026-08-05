"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { companies } from "@/lib/catalog-data";

export function CompanyDirectory({ pageSize = 12 }: { pageSize?: number }) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("全部");
  const [sector, setSector] = useState("全部");
  const [page, setPage] = useState(1);
  const regions = ["全部", ...Array.from(new Set(companies.map((item) => item.region)))];
  const sectors = ["全部", ...Array.from(new Set(companies.map((item) => item.sector)))];
  const filtered = useMemo(
    () => companies.filter((item) =>
      (region === "全部" || item.region === region) &&
      (sector === "全部" || item.sector === sector) &&
      `${item.name}${item.englishName ?? ""}${item.summary}`.toLowerCase().includes(query.toLowerCase()),
    ),
    [query, region, sector],
  );
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);

  function resetPage(setter: () => void) {
    setter();
    setPage(1);
  }

  return (
    <>
      <div className="directory-filters">
        <label className="directory-search"><Search size={16} /><input value={query} onChange={(e) => resetPage(() => setQuery(e.target.value))} placeholder="公司名称、产品或关键词" aria-label="搜索创业公司" /></label>
        <select value={region} onChange={(e) => resetPage(() => setRegion(e.target.value))} aria-label="地区">{regions.map((item) => <option key={item}>{item}</option>)}</select>
        <select value={sector} onChange={(e) => resetPage(() => setSector(e.target.value))} aria-label="赛道">{sectors.map((item) => <option key={item}>{item}</option>)}</select>
        <span>共 {filtered.length} 家真实公司档案</span>
      </div>
      <div className="catalog-grid">
        {visible.map((company) => (
          <Link href={`/companies/${company.slug}`} className="catalog-card" key={company.slug}>
            <div className="catalog-top"><span>{company.region}</span><span>{company.status}</span></div>
            <div className="catalog-title"><i>{company.name.slice(0, 2).toUpperCase()}</i><div><h2>{company.name}</h2><p>{company.englishName}</p></div></div>
            <p>{company.summary}</p>
            <dl><div><dt>赛道</dt><dd>{company.sector}</dd></div><div><dt>阶段</dt><dd>{company.stage}</dd></div><div><dt>完整度</dt><dd>{Math.round(company.confidence * 100)}%</dd></div></dl>
            <span className="verified-source">来源 · {company.source.name}</span>
          </Link>
        ))}
      </div>
      {!visible.length && <div className="empty-state"><Search size={22}/><strong>没有匹配的公司</strong><p>换一个关键词，或清除地区与赛道筛选。</p></div>}
      <div className="pagination">
        <button disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button>
        <span>{page} / {pages}</span>
        <button disabled={page === pages} onClick={() => setPage(page + 1)}>下一页</button>
      </div>
    </>
  );
}
