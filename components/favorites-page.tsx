"use client";

import { Bookmark, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useFavorites } from "@/components/use-favorites";
import { removeFavorite, type FavoriteItem } from "@/lib/favorites";

function isIntelligenceCard(item: FavoriteItem): boolean {
  return Boolean(item.publishedAt || item.eventType || item.importance !== undefined);
}

function IntelligenceFavoriteCard({ item }: { item: FavoriteItem }) {
  const date = item.publishedAt || item.savedAt.slice(0, 10);
  const source = item.sources[0];
  const tags = [...new Set([
    item.eventType,
    item.region,
    ...item.sectors,
  ].filter(Boolean))] as string[];

  return (
    <article className="favorite-intelligence-card">
      <a
        className="favorite-intelligence-link"
        href={item.href}
        target="_blank"
        rel="noreferrer"
        aria-label={`打开原始情报：${item.title}`}
      >
        <div className="event-date">
          <strong>{date.slice(5)}</strong>
          <span>{date.slice(0, 4)}</span>
        </div>

        <div className="event-main">
          <div className="event-tags">
            {tags.map((tag, index) => (
              <span className={index === 0 ? `tag tag-${tag}` : undefined} key={tag}>
                {tag}
              </span>
            ))}
          </div>
          <h3>{item.title}</h3>
          <p>{item.summary || "打开原始链接查看完整内容。"}</p>
          <span className="source-link favorite-source-link">
            {source
              ? `${source.level ? `${source.level} · ` : ""}${source.name}`
              : "打开原始链接"}
            <span aria-hidden="true">↗</span>
          </span>
        </div>

        <div className="importance">
          {item.importance !== undefined ? (
            <>
              <span>重要度</span>
              <strong>{item.importance}</strong>
            </>
          ) : (
            <span>原始情报 ↗</span>
          )}
        </div>
      </a>

      <button
        type="button"
        className="favorite-remove favorite-intelligence-remove"
        onClick={() => removeFavorite(item.id)}
        aria-label={`移除收藏：${item.title}`}
        title="移除收藏"
      >
        <Trash2 size={15} />
      </button>
    </article>
  );
}

export function FavoritesPage() {
  const favorites = useFavorites();
  const [channel, setChannel] = useState("全部频道");
  const [query, setQuery] = useState("");
  const channels = useMemo(
    () => [
      "全部频道",
      ...new Set(favorites.map((item) => item.channelLabel).filter(Boolean)),
    ],
    [favorites],
  );
  const visible = useMemo(() => {
    const needle = query.normalize("NFKC").trim().toLocaleLowerCase("zh-CN");
    return favorites.filter((item) => {
      if (channel !== "全部频道" && item.channelLabel !== channel) return false;
      if (!needle) return true;
      return [
        item.title,
        item.summary,
        item.channelLabel,
        item.eventType ?? "",
        ...item.keywords,
        ...item.sectors,
      ].some((value) => value.toLocaleLowerCase("zh-CN").includes(needle));
    });
  }, [channel, favorites, query]);

  return (
    <>
      <header className="page-header favorites-header">
        <p className="eyebrow">08 / FAVORITES</p>
        <div>
          <h1>收藏</h1>
          <p className="intro-copy">
            保存值得持续跟踪的情报卡片，并把相关主题、关键词与原始信源作为智能推荐的高权重信号。
          </p>
        </div>
        <div className="favorites-signal-card">
          <span>当前浏览器</span>
          <strong>{favorites.length}</strong>
          <p>项收藏 · 本地长期保存</p>
        </div>
      </header>

      {favorites.length ? (
        <>
          <div className="favorites-toolbar">
            <div className="favorites-tabs" aria-label="按频道筛选收藏">
              {channels.map((item) => (
                <button
                  type="button"
                  className={channel === item ? "active" : ""}
                  onClick={() => setChannel(item)}
                  key={item}
                >
                  {item}
                </button>
              ))}
            </div>
            <label className="favorites-search">
              <Search size={15} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索收藏标题、摘要或关键词"
                aria-label="搜索收藏"
              />
            </label>
          </div>

          <div className="favorites-list">
            {visible.map((item, index) =>
              isIntelligenceCard(item) ? (
                <IntelligenceFavoriteCard item={item} key={item.id} />
              ) : (
                <article className="favorite-card" key={item.id}>
                  <span className="favorite-card-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <Link href={item.href} className="favorite-card-main">
                    <div className="favorite-card-meta">
                      <span>{item.channelLabel}</span>
                      <time>{new Date(item.savedAt).toLocaleDateString("zh-CN")}</time>
                    </div>
                    <h2>{item.title}</h2>
                    <p>{item.summary || "打开原页面继续阅读。"}</p>
                    <div className="favorite-card-tags">
                      {[...new Set([...item.sectors, ...item.keywords])]
                        .slice(0, 6)
                        .map((tag) => (
                          <span key={tag}>{tag}</span>
                        ))}
                      {item.sources.length ? (
                        <span>{item.sources.length} 个参考信源</span>
                      ) : null}
                    </div>
                  </Link>
                  <button
                    type="button"
                    className="favorite-remove"
                    onClick={() => removeFavorite(item.id)}
                    aria-label={`移除收藏：${item.title}`}
                    title="移除收藏"
                  >
                    <Trash2 size={16} />
                  </button>
                </article>
              ),
            )}
          </div>

          {!visible.length ? (
            <div className="favorites-empty compact">
              <Search size={24} />
              <strong>没有符合当前条件的收藏</strong>
              <p>更换频道或搜索词后再试。</p>
            </div>
          ) : null}
        </>
      ) : (
        <div className="favorites-empty">
          <Bookmark size={30} />
          <strong>还没有收藏情报</strong>
          <p>在首页任一“关键事件”情报卡片右上角点击“收藏”，即可把整张卡片保存到这里。</p>
          <Link href="/">返回首页浏览情报 →</Link>
        </div>
      )}

      <style jsx global>{`
        .favorite-intelligence-card {
          position: relative;
          border-bottom: 1px solid var(--border);
          transition: background 0.2s ease;
        }

        .favorite-intelligence-card:hover {
          background: color-mix(in srgb, var(--surface) 70%, transparent);
        }

        .favorite-intelligence-link {
          display: grid;
          grid-template-columns: 74px minmax(0, 1fr) 64px;
          gap: 19px;
          padding: 20px 4px;
        }

        .favorite-intelligence-link:hover h3 {
          color: var(--green-bright);
        }

        .favorite-intelligence-card .event-main {
          min-width: 0;
          padding-right: 4px;
        }

        .favorite-intelligence-card .event-main h3 {
          margin: 0 0 6px;
          font-size: 17px;
          line-height: 1.4;
        }

        .favorite-intelligence-card .event-main p {
          margin: 0 0 8px;
        }

        .favorite-source-link {
          pointer-events: none;
        }

        .favorite-intelligence-card .importance {
          padding-right: 4px;
        }

        .favorite-intelligence-remove {
          position: absolute;
          right: 7px;
          bottom: 16px;
          z-index: 2;
          width: 29px;
          height: 29px;
          background: color-mix(in srgb, var(--bg) 88%, transparent);
        }

        @media (max-width: 720px) {
          .favorite-intelligence-link {
            grid-template-columns: 54px minmax(0, 1fr) 46px;
            gap: 12px;
          }

          .favorite-intelligence-card .event-tags {
            flex-wrap: wrap;
          }

          .favorite-intelligence-card .event-main h3 {
            font-size: 15px;
          }
        }
      `}</style>
    </>
  );
}
