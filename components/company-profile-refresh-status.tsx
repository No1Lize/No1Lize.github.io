import Link from "next/link";
import { RefreshCw } from "lucide-react";
import {
  companyProfileRefreshQueue,
  formatCompanyProfileQueueTime,
} from "@/lib/company-profile-refresh-queue";
import styles from "./company-profile-refresh-status.module.css";

export function CompanyProfileRefreshStatus() {
  const queue = companyProfileRefreshQueue;
  const topEntries = queue.entries.slice(0, 3);

  return (
    <section className={styles.panel} aria-labelledby="company-profile-refresh-title">
      <div className={styles.heading}>
        <RefreshCw size={18} aria-hidden="true" />
        <div>
          <p>PROFILE REFRESH QUEUE</p>
          <h2 id="company-profile-refresh-title">增量档案刷新</h2>
          <span>
            重大融资、并购、IPO、监管、技术和产品事件进入限量队列；每天 13:35、17:35、21:35（UTC+8）处理。
          </span>
        </div>
      </div>

      <dl className={styles.metrics}>
        <div>
          <dt>待处理公司</dt>
          <dd>{queue.pendingCount}</dd>
        </div>
        <div>
          <dt>下一批</dt>
          <dd>{queue.selectedCount}</dd>
        </div>
        <div>
          <dt>最近处理</dt>
          <dd className={styles.time}>{formatCompanyProfileQueueTime(queue.lastProcessedAt)}</dd>
        </div>
      </dl>

      {topEntries.length > 0 ? (
        <div className={styles.entries}>
          {topEntries.map((entry) => (
            <article key={entry.companySlug}>
              <div>
                <strong>{entry.companyName}</strong>
                <span>优先级 {entry.priority}</span>
              </div>
              <p>{entry.reasons.join(" · ")}</p>
              <Link href={`/companies/${entry.companySlug}`}>查看现有档案 →</Link>
            </article>
          ))}
        </div>
      ) : (
        <p className={styles.empty}>当前没有需要增量处理的重大公司事件。</p>
      )}
    </section>
  );
}
