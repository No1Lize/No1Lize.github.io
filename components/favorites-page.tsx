"use client";

import { Bookmark, Search, Share2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useFavorites } from "@/components/use-favorites";
import { removeFavorite, type FavoriteItem } from "@/lib/favorites";

function isIntelligenceCard(item: FavoriteItem): boolean {
  return Boolean(
    item.id.startsWith("homepage:article:") ||
      item.publishedAt ||
      item.eventType ||
      item.importance !== undefined,
  );
}

function absoluteShareUrl(href: string): string {
  if (typeof window === "undefined") return href;
  try {
    return new URL(href, window.location.origin).href;
  } catch {
    return href;
  }
}

async function copyShareText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }
}

function ShareFavoriteButton({ item }: { item: FavoriteItem }) {
  const [notice, setNotice] = useState("");
  const timerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const showNotice = (message: string) => {
    setNotice(message);
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setNotice(""), 4800);
  };

  const share = async () => {
    const url = absoluteShareUrl(item.href);
    const summary = item.summary.trim().slice(0, 140);
    const text = summary ? `${item.title}\n${summary}` : item.title;
    const shareData: ShareData = { title: item.title, text, url };
    const shareText = `${text}\n${url}`;
    const inWechat = /MicroMessenger/i.test(navigator.userAgent);

    // Ordinary web pages cannot directly open WeChat Moments' composer.
    // Inside WeChat, copy the direct source link and guide the user to the
    // browser menu; outside WeChat, prefer the operating system share sheet.
    if (inWechat) {
      const copied = await copyShareText(shareText);
      showNotice(
        copied
          ? "原链接已复制，请点微信右上角“…”并选择“分享到朋友圈”"
          : "请点微信右上角“…”并选择“分享到朋友圈”",
      );
      return;
    }

    if (typeof navigator.share === "function") {
      try {
        if (typeof navigator.canShare !== "function" || navigator.canShare(shareData)) {
          await navigator.share(shareData);
          showNotice("已打开系统分享面板");
          return;
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
      }
    }

    const copied = await copyShareText(shareText);
    showNotice(copied ? "标题和原链接已复制" : "浏览器暂不支持分享，请手动复制原链接");
  };

  return (
    <div className="favorite-share-control">
      <button
        type="button"
        className="favorite-share"
        onClick={share}
        aria-label={`分享：${item.title}`}
        title="分享原始情报链接"
      >
        <Share2 size={14} />
        <span>分享</span>
      </button>
      {notice ? (
        <span className="favorite-share-notice" role="status">
          {notice}
        </span>
      ) : null}
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
                  <FavoriteCardActions item={item} />
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
          <p>在任一条目式情报卡片右上角点击“收藏”，即可把整张卡片保存到这里。</p>
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

        .favorite-share-notice {
          position: absolute;
          top: 36px;
          right: 0;
          width: max-content;
          max-width: min(290px, 72vw);
          padding: 8px 10px;
          border: 1px solid var(--border);
          background: var(--surface-2);
          box-shadow: var(--shadow);
          color: var(--text);
          font-size: 10px;
          line-height: 1.55;
          white-space: normal;
          pointer-events: none;
        }

        .favorite-card-actions .favorite-remove {
          flex: 0 0 auto;
          width: 30px;
          height: 30px;
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
      `}</style>
    </>
  );
}
