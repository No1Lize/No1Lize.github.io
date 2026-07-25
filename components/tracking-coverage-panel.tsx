import {
  fallbackTrackCoverage,
  trackCoverage,
  trackingEnrichedAt,
} from "@/lib/tracking-snapshot";
import { userTrackingConfig } from "@/lib/user-tracking";
import styles from "./tracking-coverage-panel.module.css";

export function TrackingCoveragePanel() {
  const tracks = userTrackingConfig.tracks.filter((track) => track.enabled);
  const rows = tracks.map((track) => ({
    track,
    coverage:
      trackCoverage[track.slug] ?? fallbackTrackCoverage(track.slug, track.name),
  }));
  const ready = rows.filter((item) => item.coverage.status === "ready").length;
  const attention = rows.filter((item) =>
    ["partial", "empty", "error", "pending"].includes(item.coverage.status),
  ).length;

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <div>
          <p className="section-index">TRACK CRAWL COVERAGE</p>
          <h1>赛道爬取覆盖</h1>
          <p>
            每个赛道固定运行 Bing、Google News 中文和 Google News 英文三路发现，
            并对现有文章执行关键词与主体回填。
          </p>
        </div>
        <div className={styles.summary}>
          <span>{ready} 个已完成</span>
          <strong>{attention}</strong>
          <small>个需要关注</small>
        </div>
      </div>

      <div className={styles.grid}>
        {rows.map(({ track, coverage }) => (
          <article
            className={styles.card}
            data-status={coverage.status}
            key={track.slug}
          >
            <div className={styles.cardHeader}>
              <div>
                <span className={styles.status}>{coverage.label}</span>
                <h2>{track.name}</h2>
              </div>
              <strong>
                {coverage.completedSources}/{coverage.expectedSources}
              </strong>
            </div>
            <p>{coverage.message}</p>
            <dl>
              <div>
                <dt>扫描</dt>
                <dd>{coverage.scanned}</dd>
              </div>
              <div>
                <dt>接收</dt>
                <dd>{coverage.accepted}</dd>
              </div>
              <div>
                <dt>页面事件</dt>
                <dd>{coverage.matchedArticles}</dd>
              </div>
              <div>
                <dt>历史回填</dt>
                <dd>{coverage.backfilledArticles}</dd>
              </div>
              <div>
                <dt>独立来源</dt>
                <dd>{coverage.independentSources}</dd>
              </div>
              <div>
                <dt>失败源</dt>
                <dd>{coverage.failedSources}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>

      <p className={styles.footer}>
        最近覆盖计算：{trackingEnrichedAt || "等待首次爬取快照"}
      </p>
    </section>
  );
}
