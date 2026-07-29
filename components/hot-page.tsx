"use client";

import { Bookmark, ExternalLink, Flame, Search, Share2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useFavorites } from "@/components/use-favorites";
import { useHotness } from "@/components/use-hotness";
import styles from "@/components/hot-page.module.css";
import {
  isFavorite,
  toggleFavorite,
  type FavoriteInput,
} from "@/lib/favorites";
import {
  HOTNESS_WEIGHTS,
  calculateHotnessScore,
  canonicalHotnessKey,
  metricsByHref,
  recordArticleOpen,
  recordArticleShare,
  setArticleFavorite,
  type HotnessInput,
} from "@/lib/hotness";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";
import { useArticles } from "@/lib/use-articles";

const SHARE_REQUEST_EVENT = "vciq:favorite-share-request";
const DISPLAY_LIMIT = 100;

type RankedArticle = {
  article: LiveIntelligenceEvent;
  score: number;
  opens: number;
  favorite: boolean;
  shares: number;
};

function favoriteInput(article: LiveIntelligenceEvent): FavoriteInput {
  return {
    id: article.id,
    href: article.source.url,
    title: article.title,
    summary: article.summary,
    channel: "technology",
    channelLabel: "09 热点",
    keywords: [article.type, article.region, article.sector],
    sectors: [article.sector],
    sources: [
      {
        name: article.source.name,
        url: article.source.url,
        level: article.source.level,
      },
    ],
    region: article.region,
    company: article.company,
    publishedAt: article.publishedAt,
    importance: article.importance,
    eventType: article.type,
  };
}

function hotnessInput(article: LiveIntelligenceEvent): HotnessInput {
  return {
    id: article.id,
    href: article.source.url,
    title: article.title,
    summary: article.summary,
    publishedAt: article.publishedAt,
    importance: article.importance,
    sourceName: article.source.name,
    channelLabel: "09 热点",
  };
}

function shareArticle(article: LiveIntelligenceEvent) {
  recordArticleShare(hotnessInput(article));
  window.dispatchEvent(
    new CustomEvent(SHARE_REQUEST_EVENT, {
      detail: {
        title: article.title,
        summary: article.summary,
        url: article.source.url,
      },
    }),
  );
}

export function HotPage() {
  const { articles, generatedAt, isLive } = useArticles();
  const hotness = useHotness();
  const favorites = useFavorites();
  const [query, setQuery] = useState("");
  const [onlyInteracted, setOnlyInteracted] = useState(false);

  const favoriteKeys = useMemo(
    () => new Set(favorites.map((item) => canonicalHotnessKey(item.href)).filter(Boolean)),
    [favorites],
  );

  const ranked = useMemo(() => {
    const metrics = metricsByHref(hotness);
    const needle = query.normalize("NFKC").trim().toLocaleLowerCase("zh-CN");

    return articles
      .map<RankedArticle>((article) => {
        const key = canonicalHotnessKey(article.source.url);
        const item = metrics.get(key);
        const favorite = favoriteKeys.has(key) || item?.favorite === true;
        const opens = item?.opens ?? 0;
        const shares = item?.shares ?? 0;
        return {
          article,
          opens,
          favorite,
          shares,
          score: calculateHotnessScore({ opens, favorite, shares }),
        };
      })
      .filter((item) => !onlyInteracted || item.score > 0)
      .filter((item) => {
        if (!needle) return true;
        const article = item.article;
        return [
          article.title,
          article.summary,
          article.company,
          article.sector,
          article.type,
          article.region,
          article.source.name,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase("zh-CN").includes(needle));
      })
      .sort(
        (left, right) =>
          right.score - left.score ||
          right.shares - left.shares ||
          Number(right.favorite) - Number(left.favorite) ||
          right.opens - left.opens ||
          right.article.importance - left.article.importance ||
          right.article.publishedAt.localeCompare(left.article.publishedAt) ||
          left.article.title.localeCompare(right.article.title, "zh-CN"),
      )
      .slice(0, DISPLAY_LIMIT);
  }, [articles, favoriteKeys, hotness, onlyInteracted, query]);

  const interactedCount = useMemo(
    () =>
      ranked.filter(
        (item) => item.opens > 0 || item.favorite || item.shares > 0,
      ).length,
    [ranked],
  );
  const totalOpens = hotness.reduce((sum, item) => sum + item.opens, 0);
  const totalShares = hotness.reduce((sum, item) => sum + item.shares, 0);

  return (
    <>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">09 / HOT RANKING</p>
          <h1>热点</h1>
          <p className="intro-copy">
            根据当前浏览器对原始文章的打开、收藏与分享行为实时排名。分享权重最高，收藏次之，打开用于累积阅读热度。
          </p>
        </div>
        <div className={styles.summary}>
          <span>{isLive ? "实时文章池" : "内置文章池"}</span>
          <strong>{ranked.length}</strong>
          <p>条候选 · 数据快照 {generatedAt.slice(0, 10)}</p>
        </div>
      </header>

      <section className={styles.weightBar} aria-label="热点排名权重">
        <div><ExternalLink size={15} /><span>打开</span><strong>× {HOTNESS_WEIGHTS.open}</strong></div>
        <div><Bookmark size={15} /><span>收藏</span><strong>× {HOTNESS_WEIGHTS.favorite}</strong></div>
        <div><Share2 size={15} /><span>分享</span><strong>× {HOTNESS_WEIGHTS.share}</strong></div>
        <p>当前浏览器累计打开 {totalOpens} 次、分享 {totalShares} 次；未产生行为的文章按重要度与发布时间打破并列。</p>
      </section>

      <div className={styles.toolbar}>
        <div className={styles.tabs} aria-label="热点榜范围">
          <button
            type="button"
            className={!onlyInteracted ? styles.active : ""}
            onClick={() => setOnlyInteracted(false)}
          >
            全部文章
          </button>
          <button
            type="button"
            className={onlyInteracted ? styles.active : ""}
            onClick={() => setOnlyInteracted(true)}
          >
            已互动 {interactedCount}
          </button>
        </div>
        <label className={styles.search}>
          <Search size={15} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索热点文章、公司或赛道"
            aria-label="搜索热点文章"
          />
        </label>
      </div>

      <section className={styles.ranking} aria-label="09 热点文章排名">
        {ranked.length ? (
          ranked.map(({ article, score, opens, favorite, shares }, index) => {
            const input = favoriteInput(article);
            return (
              <article className={styles.row} key={article.id}>
                <div className={styles.rank} data-top={index < 3 ? "true" : "false"}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <Flame size={15} aria-hidden="true" />
                </div>

                <a
                  className={styles.main}
                  href={article.source.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => recordArticleOpen(hotnessInput(article))}
                >
                  <div className={styles.meta}>
                    <span>{article.type}</span>
                    <span>{article.region}</span>
                    <span>{article.sector}</span>
                    <time>{article.publishedAt}</time>
                  </div>
                  <h2>{article.title}</h2>
                  <p>{article.summary}</p>
                  <small>{article.source.level} · {article.source.name} ↗</small>
                </a>

                <div className={styles.signals} aria-label={`热点分 ${score}`}>
                  <strong>{score}</strong>
                  <span>热点分</span>
                  <dl>
                    <div><dt>打开</dt><dd>{opens}</dd></div>
                    <div><dt>收藏</dt><dd>{favorite ? 1 : 0}</dd></div>
                    <div><dt>分享</dt><dd>{shares}</dd></div>
                  </dl>
                  <div className={styles.actions}>
                    <button
                      type="button"
                      data-active={favorite ? "true" : "false"}
                      onClick={() => {
                        const next = toggleFavorite(input);
                        setArticleFavorite(hotnessInput(article), next);
                      }}
                      aria-label={favorite ? `取消收藏：${article.title}` : `收藏：${article.title}`}
                    >
                      <Bookmark size={14} fill={favorite ? "currentColor" : "none"} />
                    </button>
                    <button
                      type="button"
                      onClick={() => shareArticle(article)}
                      aria-label={`分享：${article.title}`}
                    >
                      <Share2 size={14} />
                    </button>
                  </div>
                </div>
              </article>
            );
          })
        ) : (
          <div className={styles.empty}>
            <Flame size={28} />
            <strong>当前条件下没有热点文章</strong>
            <p>关闭“已互动”筛选或更换搜索词后再试。</p>
          </div>
        )}
      </section>

      <p className={styles.disclosure}>
        统计仅保存在当前浏览器，不上传个人阅读记录。清除浏览器站点数据后，打开、收藏和分享计数会重新开始。
      </p>
    </>
  );
}
