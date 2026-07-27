"use client";

import { Bookmark, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useFavorites } from "@/components/use-favorites";
import { removeFavorite } from "@/lib/favorites";

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
            保存值得持续跟踪的内容，并把相关主题、关键词与原始信源作为智能推荐的高权重信号。
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
            {visible.map((item, index) => (
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
            ))}
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
          <strong>还没有收藏内容</strong>
          <p>进入任一独立阅读页，点击标题右上方的“收藏”即可加入这里。</p>
          <Link href="/technology">浏览新兴科技 →</Link>
        </div>
      )}
    </>
  );
}
