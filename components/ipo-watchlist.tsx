import Link from "next/link";
import type { ListedCompanyView } from "@/lib/listed-companies";
import styles from "./ipo-watchlist.module.css";

const MARKETS = ["A股", "港股", "美股"] as const;
type Market = (typeof MARKETS)[number];

type IpoWatchlistProps = {
  companies: ListedCompanyView[];
};

export function IpoWatchlist({ companies }: IpoWatchlistProps) {
  const counts = Object.fromEntries(
    MARKETS.map((market) => [
      market,
      companies.filter((company) => company.market === market).length,
    ]),
  ) as Record<Market, number>;

  return (
    <section className={styles.workspace} aria-labelledby="watchlist-title">
      <div className={styles.marketTabs}>
        {MARKETS.map((market) => (
          <div key={market}>
            <span>{market}</span>
            <strong>{counts[market]}</strong>
            <small>启用关注公司</small>
          </div>
        ))}
      </div>

      <div className={styles.manager}>
        <div className={styles.managerHeader}>
          <div>
            <p className="eyebrow">REPOSITORY-BACKED WATCHLIST</p>
            <h2 id="watchlist-title">上市公司关注列表</h2>
            <p>
              当前页面只展示齿轮后台中已启用的公司。添加后立即生成静态详情页，行情与公司数据由定时任务补齐。
            </p>
          </div>
          <div>
            <strong>{companies.length} 家</strong>
            <Link className="text-link" href="/tracking">
              管理关注公司 →
            </Link>
          </div>
        </div>
      </div>

      {!companies.length ? (
        <div className={styles.empty}>
          <strong>当前没有启用的上市公司</strong>
          <p>进入齿轮后台添加公司，或重新启用已有关注项。</p>
          <Link className="text-link" href="/tracking">
            打开上市公司关注管理 →
          </Link>
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
              </tr>
            </thead>
            <tbody>
              {companies.map((company) => (
                <tr key={company.id}>
                  <td>
                    <Link href={`/ipo/${company.slug}`}>{company.name}</Link>
                    {company.custom && (
                      <small className={styles.storageNote}>自定义关注</small>
                    )}
                  </td>
                  <td>
                    {company.market} · {company.ticker}
                  </td>
                  <td>{company.sector}</td>
                  <td>
                    <span
                      className={company.source ? "status-label" : styles.pendingLabel}
                    >
                      {company.status}
                    </span>
                  </td>
                  <td>{company.latest}</td>
                  <td>
                    {company.source ? (
                      <a
                        href={company.source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {company.source.name}
                      </a>
                    ) : (
                      <span className={styles.pendingLabel}>待接入数据源</span>
                    )}
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
