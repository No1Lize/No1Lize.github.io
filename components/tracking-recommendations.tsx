"use client";

import { useMemo, useState } from "react";
import type { TrackingRecommendation } from "@/lib/tracking-recommendations";
import styles from "./tracking-recommendations.module.css";

const labels = {
  keywords: "推荐关键词",
  people: "推荐人物 / 账号",
  companies: "推荐样本公司",
} as const;

type RecommendationType = keyof typeof labels;

export function TrackingRecommendations({
  recommendations,
  onAdd,
}: {
  recommendations: Record<RecommendationType, TrackingRecommendation[]>;
  onAdd?: (type: RecommendationType, value: string) => Promise<void> | void;
}) {
  const [pending, setPending] = useState<string>("");
  const [hidden, setHidden] = useState<Record<string, boolean>>({});

  const sections = useMemo(
    () =>
      (Object.keys(labels) as RecommendationType[]).map((type) => ({
        type,
        title: labels[type],
        items: recommendations[type].slice(0, 8),
      })),
    [recommendations],
  );

  async function add(type: RecommendationType, item: TrackingRecommendation) {
    const key = `${type}-${item.value}`;
    setPending(key);
    try {
      await onAdd?.(type, item.value);
      setHidden((current) => ({ ...current, [key]: true }));
    } finally {
      setPending("");
    }
  }

  return (
    <section aria-label="智能推荐添加" className={styles.panel}>
      <div className={styles.header}>
        <strong>智能推荐</strong>
        <span>根据当前赛道情报自动生成</span>
      </div>

      {sections.map((section) => (
        <div key={section.type} className={styles.panel}>
          <div className={styles.header}>
            <strong>{section.title}</strong>
          </div>
          {section.items.length ? (
            <div className={styles.actions}>
              {section.items.map((item) => {
                const key = `${section.type}-${item.value}`;
                if (hidden[key]) return null;
                return (
                  <button
                    className={styles.item}
                    key={key}
                    disabled={pending === key}
                    onClick={() => void add(section.type, item)}
                    title={item.reason}
                  >
                    <strong>{item.label}</strong>
                    <small>{item.reason}</small>
                    <b>+添加</b>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className={styles.empty}>暂无推荐</p>
          )}
        </div>
      ))}
    </section>
  );
}
