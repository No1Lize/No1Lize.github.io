import { HomepageSortableFeed } from "@/components/homepage-sortable-feed";
import {
  DAILY_HEADLINES_LIMIT,
  DAILY_HEADLINES_PER_SOURCE_PER_DAY,
  getDailyHeadlines,
} from "@/lib/daily-headlines";
import styles from "@/components/homepage-columns.module.css";

export function DailyHeadlines() {
  const { generatedAt, headlines } = getDailyHeadlines();
  const items = headlines.map((headline) => ({
    id: headline.id,
    title: headline.title,
    href: headline.href,
    tag: headline.label,
    context:
      headline.platform && headline.platform !== headline.source
        ? `${headline.source} · ${headline.platform}`
        : headline.source,
    date: headline.date,
    time: headline.time,
    asideLabel: headline.label,
    sortAt: headline.publishedAt,
    importance: headline.importance,
  }));

  return (
    <aside className={`headlines-column ${styles.column}`} aria-label="最新头条">
      <div className="section-heading compact">
        <div>
          <p className="section-index">02 / LATEST HEADLINES</p>
          <h2>最新头条</h2>
        </div>
        <span>{headlines.length} 条</span>
      </div>

      <HomepageSortableFeed
        items={items}
        limit={DAILY_HEADLINES_LIMIT}
        ariaLabel="最新头条列表"
        initialSort="latest"
        description={`汇总本站信息源（微信公众号、今日头条、新浪财经、专业媒体、公司官网等）的滚动最新头条，每个来源每天最多 ${DAILY_HEADLINES_PER_SOURCE_PER_DAY} 条，保留最新 ${DAILY_HEADLINES_LIMIT} 条；可切换按最新时间或重要性排序。`}
        emptyMessage={`信息源头条等待下一次抓取（快照 ${generatedAt.slice(0, 10) || "待更新"}）。`}
      />
    </aside>
  );
}
