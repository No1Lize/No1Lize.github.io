"use client";

import { useMemo, useState } from "react";
import { currentAdminStatus, waitForAdminSave } from "@/lib/tracking-admin-sync";
import { isAllowedDisplayedKeywordRecommendation } from "@/lib/tracking-recommendation-policy";
import type {
  TrackingRecommendation,
  TrackingRecommendationSet,
  TrackingSourceRecommendation,
} from "@/lib/tracking-recommendations";
import styles from "./tracking-recommendations.module.css";

const labels = {
  keywords: "推荐关键词",
  people: "推荐人物 / 账号",
  companies: "推荐样本公司",
  sources: "推荐信息源",
} as const;

export type RecommendationType = keyof typeof labels;
export type AnyTrackingRecommendation =
  | TrackingRecommendation
  | TrackingSourceRecommendation;

export function TrackingRecommendations({
  recommendations,
  onlyType,
  onAdd,
}: {
  recommendations: TrackingRecommendationSet;
  onlyType?: RecommendationType;
  onAdd?: (
    type: RecommendationType,
    item: AnyTrackingRecommendation,
  ) => Promise<void> | void;
}) {
  const [pending, setPending] = useState<string>("");
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");

  const sections = useMemo(
    () =>
      (Object.keys(labels) as RecommendationType[])
        .filter((type) => !onlyType || type === onlyType)
        .map((type) => {
          const items = recommendations[type] as AnyTrackingRecommendation[];
          return {
            type,
            title: labels[type],
            items:
              type === "keywords"
                ? items.filter((item) =>
                    isAllowedDisplayedKeywordRecommendation(
                      item as TrackingRecommendation,
                    ),
                  )
                : items,
          };
        }),
    [onlyType, recommendations],
  );

  const activeSections = sections
    .map((section) => {
      const visibleItems = section.items.filter(
        (item) => !hidden[`${section.type}-${item.value}`],
      );
      return {
        ...section,
        current: visibleItems[0],
        remaining: visibleItems.length,
      };
    })
    .filter((section) => Boolean(section.current));

  function dismiss(type: RecommendationType, item: AnyTrackingRecommendation) {
    const key = `${type}-${item.value}`;
    setError("");
    setHidden((current) => ({ ...current, [key]: true }));
  }

  async function add(type: RecommendationType, item: AnyTrackingRecommendation) {
    const key = `${type}-${item.value}`;
    setPending(key);
    setError("");
    const previousStatus = currentAdminStatus();
    try {
      await onAdd?.(type, item);
      await waitForAdminSave(previousStatus);
      setHidden((current) => ({ ...current, [key]: true }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPending("");
    }
  }

  if (!activeSections.length) return null;

  return (
    <section aria-label="智能推荐添加" className={styles.panel}>
      <div className={styles.header}>
        <strong>{onlyType ? labels[onlyType] : "智能推荐"}</strong>
        <span>按相关度排序 · 逐条处理</span>
      </div>

      {error ? (
        <p className={styles.error} role="alert">
          添加失败：{error}
        </p>
      ) : null}

      {activeSections.map((section) => {
        const item = section.current;
        if (!item) return null;
        const key = `${section.type}-${item.value}`;
        return (
          <div key={section.type}>
            {!onlyType && (
              <div className={styles.sectionTitle}>
                <strong>{section.title}</strong>
                <span>剩余 {section.remaining} 条</span>
              </div>
            )}
            <article className={styles.item} key={key} title={item.reason}>
              <div className={styles.itemText}>
                <strong>{item.label}</strong>
                <small>{item.reason}</small>
              </div>
              <div className={styles.controls}>
                <button
                  aria-label={`忽略推荐：${item.label}`}
                  className={styles.dismiss}
                  disabled={Boolean(pending)}
                  onClick={() => dismiss(section.type, item)}
                  title="忽略并显示下一条"
                  type="button"
                >
                  ×
                </button>
                <button
                  className={styles.add}
                  disabled={Boolean(pending)}
                  onClick={() => void add(section.type, item)}
                  type="button"
                >
                  {pending === key ? "添加中" : "+ 添加"}
                </button>
              </div>
            </article>
          </div>
        );
      })}
    </section>
  );
}
