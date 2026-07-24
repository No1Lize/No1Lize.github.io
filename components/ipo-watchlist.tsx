"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import type { IpoCompany } from "@/lib/catalog-data";
import styles from "./ipo-watchlist.module.css";

const STORAGE_KEY = "lize-road-one:ipo-watchlist:v1";
const MARKETS = ["A股", "港股", "美股"] as const;

type Market = (typeof MARKETS)[number];

type CustomCompany = {
  id: string;
  name: string;
  ticker: string;
  market: Market;
};

type StoredWatchlist = {
  followedSlugs: string[];
  customCompanies: CustomCompany[];
};

type IpoWatchlistProps = {
  companies: IpoCompany[];
};

function normalizeTicker(value: string) {
  return value.trim().toUpperCase().replace(/\s+/g, "");
}

function readWatchlist(companies: IpoCompany[]): StoredWatchlist {
  const fallback = {
    followedSlugs: companies.map((company) => company.slug),
    customCompanies: [],
  };

  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return fallback;
    const parsed = JSON.parse(saved) as Partial<StoredWatchlist>;
    return {
      followedSlugs: Array.isArray(parsed.followedSlugs)
        ? parsed.followedSlugs.filter((slug): slug is string => typeof slug === "string")
        : fallback.followedSlugs,
      customCompanies: Array.isArray(parsed.customCompanies)
        ? parsed.customCompanies.filter(
            (company): company is CustomCompany =>
              typeof company?.id === "string" &&
              typeof company?.name === "string" &&
              typeof company?.ticker === "string" &&
              MARKETS.includes(company?.market as Market),
          )
        : [],
    };
  } catch {
    return fallback;
  }
}

export function IpoWatchlist({ companies }: IpoWatchlistProps) {
  const [followedSlugs, setFollowedSlugs] = useState<string[]>([]);
  const [customCompanies, setCustomCompanies] = useState<CustomCompany[]>([]);
  const [ready, setReady] = useState(false);
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [ticker, setTicker] = useState("");
  const [market, setMarket] = useState<Market>("美股");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      const saved = readWatchlist(companies);
      setFollowedSlugs(saved.followedSlugs);
      setCustomCompanies(saved.customCompanies);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, [companies]);

  useEffect(() => {
    if (!ready) return;
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ followedSlugs, customCompanies } satisfies StoredWatchlist),
    );
  }, [customCompanies, followedSlugs, ready]);

  const followedSet = useMemo(() => new Set(followedSlugs), [followedSlugs]);
  const followedCompanies = useMemo(
    () => companies.filter((company) => followedSet.has(company.slug)),
    [companies, followedSet],
  );
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const candidates = useMemo(
    () =>
      companies.filter((company) => {
        if (!normalizedQuery) return true;
        return [company.name, company.ticker, company.market, company.sector]
          .join(" ")
          .toLocaleLowerCase()
          .includes(normalizedQuery);
      }),
    [companies, normalizedQuery],
  );

  const counts = useMemo(
    () =>
      Object.fromEntries(
        MARKETS.map((item) => [
          item,
          followedCompanies.filter((company) => company.market === item).length +
            customCompanies.filter((company) => company.market === item).length,
        ]),
      ) as Record<Market, number>,
    [customCompanies, followedCompanies],
  );

  function toggleCompany(company: IpoCompany) {
    setFollowedSlugs((current) => {
      const isFollowed = current.includes(company.slug);
      setNotice(`${isFollowed ? "已取消关注" : "已加入关注"}：${company.name}`);
      return isFollowed
        ? current.filter((slug) => slug !== company.slug)
        : [...current, company.slug];
    });
  }

  function addCustomCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = name.trim();
    const cleanTicker = normalizeTicker(ticker);
    if (!cleanName || !cleanTicker) {
      setNotice("请填写公司名称和股票代码。");
      return;
    }

    const known = companies.find(
      (company) =>
        company.market === market &&
        normalizeTicker(company.ticker) === cleanTicker,
    );
    if (known) {
      setFollowedSlugs((current) =>
        current.includes(known.slug) ? current : [...current, known.slug],
      );
      setNotice(`已加入关注：${known.name}`);
    } else {
      const id = `${market}:${cleanTicker}`;
      setCustomCompanies((current) => {
        const next = current.filter((company) => company.id !== id);
        return [...next, { id, name: cleanName, ticker: cleanTicker, market }];
      });
      setNotice(`已加入自定义关注：${cleanName}`);
    }
    setName("");
    setTicker("");
  }

  function removeCustomCompany(company: CustomCompany) {
    setCustomCompanies((current) =>
      current.filter((item) => item.id !== company.id),
    );
    setNotice(`已取消关注：${company.name}`);
  }

  const total = followedCompanies.length + customCompanies.length;

  return (
    <section className={styles.workspace} aria-labelledby="watchlist-title">
      <div className={styles.marketTabs}>
        {MARKETS.map((item) => (
          <div key={item}>
            <span>{item}</span>
            <strong>{ready ? counts[item] : "—"}</strong>
            <small>已关注公司</small>
          </div>
        ))}
      </div>

      <div className={styles.manager}>
        <div className={styles.managerHeader}>
          <div>
            <p className="eyebrow">MY WATCHLIST</p>
            <h2 id="watchlist-title">我的上市公司关注</h2>
            <p>选择已有档案，或按市场和股票代码加入自定义公司。</p>
          </div>
          <strong>{ready ? total : "—"} 家</strong>
        </div>

        <div className={styles.catalogPicker}>
          <label>
            <span>从已有档案添加</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索公司、代码、市场或赛道"
            />
          </label>
          <div className={styles.candidates}>
            {candidates.map((company) => {
              const active = followedSet.has(company.slug);
              return (
                <button
                  type="button"
                  className={active ? styles.activeCandidate : undefined}
                  onClick={() => toggleCompany(company)}
                  aria-pressed={active}
                  key={company.slug}
                >
                  <span>{active ? "✓" : "+"}</span>
                  {company.name}
                  <small>{company.ticker}</small>
                </button>
              );
            })}
          </div>
        </div>

        <form className={styles.customForm} onSubmit={addCustomCompany}>
          <label>
            <span>市场</span>
            <select
              value={market}
              onChange={(event) => setMarket(event.target.value as Market)}
            >
              {MARKETS.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>公司名称</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：英伟达"
              maxLength={60}
            />
          </label>
          <label>
            <span>股票代码</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="例如：NVDA"
              maxLength={20}
              autoCapitalize="characters"
            />
          </label>
          <button type="submit">加入关注</button>
        </form>
        <p className={styles.storageNote}>
          关注设置仅保存在当前浏览器。自定义公司尚未接入公共抓取时，会明确标记为“待接入数据”。
        </p>
        <p className={styles.notice} aria-live="polite">
          {notice}
        </p>
      </div>

      {ready && total === 0 ? (
        <div className={styles.empty}>
          <strong>当前没有关注公司</strong>
          <p>可从上方已有档案中选择，或输入公司名称和股票代码。</p>
          <button
            type="button"
            onClick={() => {
              setFollowedSlugs(companies.map((company) => company.slug));
              setNotice("已恢复全部已有公司。");
            }}
          >
            恢复全部已有公司
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>企业</th>
                <th>市场 / 代码</th>
                <th>赛道</th>
                <th>当前状态</th>
                <th>最近跟踪</th>
                <th>来源</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {followedCompanies.map((company) => (
                <tr key={company.slug}>
                  <td>
                    <Link href={`/ipo/${company.slug}`}>{company.name}</Link>
                  </td>
                  <td>
                    {company.market} · {company.ticker}
                  </td>
                  <td>{company.sector}</td>
                  <td>
                    <span className="status-label">{company.status}</span>
                  </td>
                  <td>{company.latest}</td>
                  <td>
                    <a
                      href={company.source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {company.source.name}
                    </a>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={styles.removeButton}
                      onClick={() => toggleCompany(company)}
                      aria-label={`取消关注 ${company.name}`}
                    >
                      取消关注
                    </button>
                  </td>
                </tr>
              ))}
              {customCompanies.map((company) => (
                <tr key={company.id}>
                  <td>
                    <strong>{company.name}</strong>
                  </td>
                  <td>
                    {company.market} · {company.ticker}
                  </td>
                  <td>自定义</td>
                  <td>
                    <span className={styles.pendingLabel}>待接入数据</span>
                  </td>
                  <td>仅加入本机关注列表</td>
                  <td>—</td>
                  <td>
                    <button
                      type="button"
                      className={styles.removeButton}
                      onClick={() => removeCustomCompany(company)}
                      aria-label={`取消关注 ${company.name}`}
                    >
                      取消关注
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
