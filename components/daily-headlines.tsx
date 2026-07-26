import { getDailyHeadlines } from "@/lib/daily-headlines";

export function DailyHeadlines() {
  const { generatedAt, headlines } = getDailyHeadlines();

  return (
    <aside className="headlines-column" aria-label="今日头条">
      <div className="section-heading compact">
        <div>
          <p className="section-index">02 / TODAY HEADLINES</p>
          <h2>今日头条</h2>
        </div>
        <span>{headlines.length} 条</span>
      </div>
      <p className="method-note">
        汇总本站信息源（微信公众号、今日头条、新浪财经、专业媒体、公司官网等）的每日头条，
        每个来源每天最多 5 条，滚动保留最新 {headlines.length} 条，随情报抓取同步更新。
      </p>
      <div className="headline-list" aria-label="每日头条列表">
        {headlines.map((headline, index) => (
          <a
            className="headline-item"
            href={headline.href}
            key={headline.id}
            rel="noreferrer"
            target="_blank"
          >
            <span className="headline-index">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="headline-body">
              <strong>{headline.title}</strong>
              <small>
                <b>{headline.label}</b> {headline.source}
                {headline.platform && headline.platform !== headline.source
                  ? ` · ${headline.platform}`
                  : ""}{" "}
                · {headline.date}
              </small>
            </span>
          </a>
        ))}
        {!headlines.length && (
          <p className="method-note">
            信息源头条等待下一次抓取（快照 {generatedAt.slice(0, 10) || "待更新"}）。
          </p>
        )}
      </div>
    </aside>
  );
}
