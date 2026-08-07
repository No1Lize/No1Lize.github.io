"use client";

import { Bookmark, Search, Share2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  HomepageSortToggle,
  type HomepageSortMode,
} from "@/components/homepage-sort-toggle";
import { useFavorites } from "@/components/use-favorites";
import { removeFavorite, type FavoriteItem } from "@/lib/favorites";

export const FAVORITE_SHARE_REQUEST_EVENT = "vciq:favorite-share-request";
const FAVORITES_BATCH_SIZE = 60;

export type FavoriteShareRequest = {
  title: string;
  summary: string;
  url: string;
};

function isIntelligenceCard(item: FavoriteItem): boolean {
  return Boolean(
    item.id.startsWith("homepage:article:") ||
      item.publishedAt ||
      item.eventType ||
      item.importance !== undefined,
  );
}

function favoriteSortAt(item: FavoriteItem): string {
  return item.publishedAt ?? item.savedAt;
}

function sortFavorites(
  items: FavoriteItem[],
  mode: HomepageSortMode,
): FavoriteItem[] {
  return [...items].sort((left, right) => {
    const leftTime = favoriteSortAt(left);
    const rightTime = favoriteSortAt(right);
    const leftImportance = left.importance ?? -1;
    const rightImportance = right.importance ?? -1;

    if (mode === "importance") {
      return (
        rightImportance - leftImportance ||
        rightTime.localeCompare(leftTime) ||
        left.title.localeCompare(right.title, "zh-CN")
      );
    }

    return (
      rightTime.localeCompare(leftTime) ||
      rightImportance - leftImportance ||
      left.title.localeCompare(right.title, "zh-CN")
    );
  });
}

function absoluteShareUrl(href: string): string {
  if (typeof window === "undefined") return href;
  try {
    return new URL(href, window.location.origin).href;
  } catch {
    return href;
  }
}

function ShareFavoriteButton({ item }: { item: FavoriteItem }) {
  const openQrShare = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();

    const detail: FavoriteShareRequest = {
      title: item.title,
      summary: item.summary,
      url: absoluteShareUrl(item.href),
    };

    window.dispatchEvent(
      new CustomEvent<FavoriteShareRequest>(FAVORITE_SHARE_REQUEST_EVENT, { detail }),
    );
  };

  return (
    <div className="favorite-share-control">
      <button
        type="button"
        className="favorite-share"
        onClick={openQrShare}
        aria-label={`分享：${item.title}`}
        title="打开微信二维码分享"
      >
        <Share2 size={14} />
        <span>分享</span>
      </button>
    </div>
  );
}

function FavoriteCardActions({ item }: { item: FavoriteItem }) {
  return (
    <div className="favorite-card-actions">
      <ShareFavoriteButton item={item} />
      <button
        type="button"
        className="favorite-remove"
        onClick={() => removeFavorite(item.id)}
        aria-label={`移除收藏：${item.title}`}
        title="移除收藏"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}

function IntelligenceFavoriteCard({ item }: { item: FavoriteItem }) {
  const date = item.publishedAt || item.savedAt.slice(0, 10);
  const source = item.sources[0];
  const eventType = item.eventType || item.keywords[0];
  const tags = [...new Set([
    eventType,
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

      <FavoriteCardActions item={item} />
    </article>
  );
}

export function FavoritesPage() {
  const favorites = useFavorites();
  const [channel, setChannel] = useState("全部频道");
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<HomepageSortMode>("latest");
  const [visibleLimit, setVisibleLimit] = useState(FAVORITES_BATCH_SIZE);
  const channels = useMemo(
    () => [
      "全部频道",
      ...new Set(favorites.map((item) => item.channelLabel).filter(Boolean)),
    ],
    [favorites],
  );
  const visible = useMemo(() => {
    const needle = query.normalize("NFKC").trim().toLocaleLowerCase("zh-CN");
    const filtered = favorites.filter((item) => {
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
    return sortFavorites(filtered, sortMode);
  }, [channel, favorites, query, sortMode]);
  const renderedVisible = visible.slice(0, visibleLimit);
  const hasMore = renderedVisible.length < visible.length;

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
                  onClick={() => {
                    setChannel(item);
                    setVisibleLimit(FAVORITES_BATCH_SIZE);
                  }}
                  key={item}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="favorites-toolbar-actions">
              <HomepageSortToggle
                value={sortMode}
                onChange={(value) => {
                  setSortMode(value);
                  setVisibleLimit(FAVORITES_BATCH_SIZE);
                }}
                ariaLabel="收藏排序方式"
              />
              <label className="favorites-search">
                <Search size={15} />
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setVisibleLimit(FAVORITES_BATCH_SIZE);
                  }}
                  placeholder="搜索收藏标题、摘要或关键词"
                  aria-label="搜索收藏"
                />
              </label>
            </div>
          </div>

          <div className="favorites-list">
            {renderedVisible.map((item, index) =>
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
                  <FavoriteCardActions item={item} />
                </article>
              ),
            )}
          </div>

          {hasMore ? (
            <div className="favorites-load-more">
              <button
                type="button"
                onClick={() => setVisibleLimit((current) => current + FAVORITES_BATCH_SIZE)}
              >
                显示更多 · 已显示 {renderedVisible.length}/{visible.length}
              </button>
            </div>
          ) : null}

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
          <p>在任一条目式情报卡片右上角点击“收藏”，即可把整张卡片保存到这里。</p>
          <Link href="/">返回首页浏览情报 →</Link>
        </div>
      )}

      <style jsx global>{`
        .favorites-toolbar-actions {
          margin-left: auto;
          display: flex;
          flex: 0 0 auto;
          align-items: center;
          gap: 10px;
        }

        .favorites-toolbar-actions .favorites-search {
          margin-left: 0;
        }

        .favorite-intelligence-card,
        .favorite-card {
          content-visibility: auto;
          contain-intrinsic-size: 150px;
        }

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
          grid-template-columns: 74px minmax(0, 1fr) 76px;
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
          padding-top: 38px;
          padding-right: 4px;
        }

        .favorite-card {
          position: relative;
          grid-template-columns: 42px minmax(0, 1fr) 108px;
        }

        .favorite-card-actions {
          position: relative;
          z-index: 3;
          display: flex;
          align-items: flex-start;
          justify-content: flex-end;
          gap: 6px;
          align-self: start;
        }

        .favorite-intelligence-card > .favorite-card-actions {
          position: absolute;
          top: 14px;
          right: 7px;
        }

        .favorite-share-control {
          position: relative;
        }

        .favorite-share {
          min-height: 30px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          padding: 5px 9px;
          border: 1px solid color-mix(in srgb, var(--blue) 58%, var(--border));
          background: color-mix(in srgb, var(--blue) 8%, var(--surface));
          color: var(--blue);
          cursor: pointer;
          font: 500 10px/1 Inter, "Noto Sans SC", sans-serif;
          white-space: nowrap;
        }

        .favorite-share:hover {
          border-color: var(--blue);
          background: color-mix(in srgb, var(--blue) 14%, var(--surface));
          color: var(--text);
        }

        .favorite-share:focus-visible {
          outline: 1px solid var(--blue);
          outline-offset: 2px;
        }

        .favorite-card-actions .favorite-remove {
          flex: 0 0 auto;
          width: 30px;
          height: 30px;
        }

        .favorites-load-more {
          display: flex;
          justify-content: center;
          padding: 20px 0 6px;
        }

        .favorites-load-more button {
          min-height: 38px;
          padding: 8px 16px;
          border: 1px solid var(--border);
          background: var(--surface-2);
          color: var(--text);
          cursor: pointer;
          font: inherit;
          font-size: 12px;
        }

        .favorites-load-more button:hover {
          border-color: var(--green);
          color: var(--green-bright);
        }

        @media (max-width: 900px) {
          .favorites-toolbar-actions {
            width: 100%;
            margin-left: 0;
          }

          .favorites-toolbar-actions .favorites-search {
            flex: 1 1 260px;
            width: auto;
          }
        }

        @media (max-width: 720px) {
          .favorite-intelligence-link {
            grid-template-columns: 54px minmax(0, 1fr) 54px;
            gap: 12px;
          }

          .favorite-intelligence-card .event-tags {
            flex-wrap: wrap;
          }

          .favorite-intelligence-card .event-main h3 {
            font-size: 15px;
          }

          .favorite-card {
            grid-template-columns: 34px minmax(0, 1fr) 74px;
          }

          .favorite-share {
            width: 30px;
            min-width: 30px;
            padding: 5px;
          }

          .favorite-share span {
            display: none;
          }
        }

        @media (max-width: 560px) {
          .favorites-toolbar-actions {
            flex-direction: column;
            align-items: stretch;
          }

          .favorites-toolbar-actions .favorites-search {
            width: 100%;
          }
        }
      `}</style>
    </>
  );
}
