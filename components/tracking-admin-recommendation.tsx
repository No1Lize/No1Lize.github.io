"use client";

import { useMemo, useState } from "react";
import styles from "./tracking-recommendations.module.css";

export type AdminRecommendationItem = {
  value: string;
  label: string;
  reason: string;
  score: number;
};

export function TrackingAdminRecommendation<T extends AdminRecommendationItem>({
  title,
  items,
  onAdd,
}: {
  title: string;
  items: T[];
  onAdd: (item: T) => Promise<void> | void;
}) {
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");

  const visible = useMemo(
    () => items.filter((item) => !hidden[item.value]),
    [hidden, items],
  );
  const current = visible[0];
  if (!current) return null;

  function dismiss() {
    setError("");
    setHidden((state) => ({ ...state, [current.value]: true }));
  }

  async function add() {
    setPending(current.value);
    setError("");
    try {
      await onAdd(current);
      setHidden((state) => ({ ...state, [current.value]: true }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPending("");
    }
  }

  return (
    <section aria-label={title} className={styles.panel}>
      <div className={styles.header}>
        <strong>{title}</strong>
        <span>按相关度排序 · 逐条处理</span>
      </div>
      {error ? (
        <p className={styles.error} role="alert">
          添加失败：{error}
        </p>
      ) : null}
      <article className={styles.item} title={current.reason}>
        <div className={styles.itemText}>
          <strong>{current.label}</strong>
          <small>{current.reason}</small>
        </div>
        <div className={styles.controls}>
          <button
            aria-label={`忽略推荐：${current.label}`}
            className={styles.dismiss}
            disabled={Boolean(pending)}
            onClick={dismiss}
            title="忽略并显示下一条"
            type="button"
          >
            ×
          </button>
          <button
            className={styles.add}
            disabled={Boolean(pending)}
            onClick={() => void add()}
            type="button"
          >
            {pending === current.value ? "添加中" : "+ 添加"}
          </button>
        </div>
      </article>
    </section>
  );
}
