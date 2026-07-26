"use client";

import { ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  institutionDirectory,
  institutionRankingCategories,
  type InstitutionDirectoryEntry,
  type InstitutionRankingCategory,
} from "@/lib/institution-ranking-data";
import styles from "./institution-directory.module.css";

const PAGE_SIZE = 24;
const regions = ["全部", "中国", "美国"] as const;

function categoryMatches(
  item: InstitutionDirectoryEntry,
  category: InstitutionRankingCategory | "全部",
) {
  if (category === "全部") return true;
  if (category === "海外代表") return item.region === "美国" && item.rankings.length === 0;
  return item.rankings.some((ranking) => ranking.category === category);
}

export function InstitutionDirectory() {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<(typeof regions)[number]>("全部");
  const [category, setCategory] = useState<InstitutionRankingCategory | "全部">("全部");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return institutionDirectory.filter((item) => {
      if (region !== "全部" && item.region !== region) return false;
      if (!categoryMatches(item, category)) return false;
      if (!normalizedQuery) return true;
      const searchable = [
        item.name,
        item.fullName,
        item.type,
        item.stages,
        ...item.sectors,
        ...item.rankings.flatMap((ranking) => [
          ranking.publisher,
          ranking.category,
          ranking.title,
          ranking.rank ? String(ranking.rank) : "",
        ]),
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();
      return searchable.includes(normalizedQuery);
    });
  }, [category, query, region]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visible = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <>
      <div className={styles.filters}>
        <label className={styles.search}>
          <Search size={15} />
          <input
            aria-label="搜索投资机构"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="搜索机构简称、全称、类型或榜单"
          />
        </label>
        <select
          aria-label="地区筛选"
          value={region}
          onChange={(event) => {
            setRegion(event.target.value as (typeof regions)[number]);
            setPage(1);
          }}
        >
          {regions.map((item) => <option key={item}>{item}</option>)}
        </select>
        <select
          aria-label="榜单类型筛选"
          value={category}
          onChange={(event) => {
            setCategory(event.target.value as InstitutionRankingCategory | "全部");
            setPage(1);
          }}
        >
          <option>全部</option>
          {institutionRankingCategories.map((item) => <option key={item}>{item}</option>)}
        </select>
        <span>显示 {visible.length} / {filtered.length} 家</span>
      </div>

      {visible.length ? (
        <section className={styles.grid} aria-label="投资机构目录">
          {visible.map((institution) => (
            <InstitutionCard institution={institution} key={institution.name} />
          ))}
        </section>
      ) : (
        <div className={styles.empty}>
          <Search size={22} />
          <strong>当前筛选没有机构</strong>
          <p>可清空关键词，或切换地区和榜单类型。</p>
        </div>
      )}

      {pageCount > 1 && (
        <nav className={styles.pagination} aria-label="机构目录分页">
          <button disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
            上一页
          </button>
          <span>{currentPage} / {pageCount}</span>
          <button disabled={currentPage === pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>
            下一页
          </button>
        </nav>
      )}
    </>
  );
}

function InstitutionCard({ institution }: { institution: InstitutionDirectoryEntry }) {
  const title = (
    <>
      <i>{institution.name.slice(0, 2).toUpperCase()}</i>
      <div>
        <h2>{institution.name}</h2>
        {institution.fullName && <p>{institution.fullName}</p>}
      </div>
    </>
  );

  return (
    <article className={styles.card}>
      <div className={styles.top}>
        <span>{institution.region}</span>
        <span>{institution.type}</span>
      </div>
      {institution.profileSlug ? (
        <Link className={styles.title} href={`/institutions/${institution.profileSlug}`}>
          {title}
        </Link>
      ) : (
        <div className={styles.title}>{title}</div>
      )}

      <dl>
        <div><dt>榜单口径</dt><dd>{institution.stages}</dd></div>
        <div><dt>主题标签</dt><dd>{institution.sectors.slice(0, 3).join(" / ")}</dd></div>
      </dl>

      <div className={styles.badges}>
        {institution.rankings.length ? institution.rankings.map((ranking) => (
          <a
            href={ranking.sourceUrl}
            target="_blank"
            rel="noreferrer"
            key={`${ranking.category}-${ranking.rank ?? "unranked"}`}
            title={ranking.title}
          >
            清科 · {ranking.category}{ranking.rank ? ` #${ranking.rank}` : " · 入选"}
            <ArrowUpRight size={11} />
          </a>
        )) : (
          <span>海外代表机构 · 官网档案</span>
        )}
      </div>

      <div className={styles.actions}>
        {institution.profileSlug && <Link href={`/institutions/${institution.profileSlug}`}>研究档案</Link>}
        {institution.officialUrl && (
          <a href={institution.officialUrl} target="_blank" rel="noreferrer">
            机构官网 <ArrowUpRight size={12} />
          </a>
        )}
        {!institution.profileSlug && !institution.officialUrl && institution.rankings[0] && (
          <a href={institution.rankings[0].sourceUrl} target="_blank" rel="noreferrer">
            榜单来源 <ArrowUpRight size={12} />
          </a>
        )}
      </div>
    </article>
  );
}
