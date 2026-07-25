"use client";

import { useMemo, useState } from "react";
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

  const sections = useMemo(
    () =>
      (Object.keys(labels) as RecommendationType[])
        .filter((type) => !onlyType || type === onlyType)
        .map((type) => ({
          type,
          title: labels[type],
          items: recommendations[type].slice(0, 8) as AnyTrackingRecommendation[],
        })),
    [onlyType, recommendations],
  );

  async function add(type: RecommendationType, item: AnyTrackingRecommendation) {
    const key = `${type}-${item.value}`;
    setPending(key);
    try {
      await onAdd?.(type, item);
      setHidden((current) => ({ ...current, [key]: true }));
    } finally {
      setPending("");
    }
  }

  return (
    <section aria-label="智能推荐添加" className={styles.panel}>
      <div className={styles.header}>
        <strong>{onlyType ? labels[onlyType] : "智能推荐"}</strong>
        <span>根据当前赛道情报自动生成</span>
      </div>

      {sections.map((section) => {
        const visibleItems = section.items.filter(
          (item) => !hidden[`${section.type}-${item.value}`],
        );
        return (
          <div key={section.type}>
            {!onlyType && (
              <div className={styles.header}>
                <strong>{section.title}</strong>
              </div>
            )}
            {visibleItems.length ? (
              <div className={styles.actions}>
                {visibleItems.map((item) => {
                  const key = `${section.type}-${item.value}`;
                  return (
                    <button
                      className={styles.item}
                      key={key}
                      disabled={pending === key}
                      onClick={() => void add(section.type, item)}
                      title={item.reason}
                      type="button"
                    >
                      <strong>{item.label}</strong>
                      <small>{item.reason}</small>
                      <b>{pending === key ? "添加中" : "+添加"}</b>
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className={styles.empty}>当前没有新的高置信推荐</p>
            )}
          </div>
        );
      })}
    </section>
  );
}
