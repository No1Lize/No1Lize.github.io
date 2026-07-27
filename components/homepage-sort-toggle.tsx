"use client";

import styles from "@/components/homepage-sort-toggle.module.css";

export type HomepageSortMode = "latest" | "importance";

export function HomepageSortToggle({
  value,
  onChange,
  ariaLabel = "情报排序方式",
}: {
  value: HomepageSortMode;
  onChange: (value: HomepageSortMode) => void;
  ariaLabel?: string;
}) {
  return (
    <div className={styles.toggle} role="group" aria-label={ariaLabel}>
      <button
        className={`${styles.button} ${value === "latest" ? styles.active : ""}`}
        type="button"
        aria-pressed={value === "latest"}
        onClick={() => onChange("latest")}
      >
        最新时间优先
      </button>
      <button
        className={`${styles.button} ${value === "importance" ? styles.active : ""}`}
        type="button"
        aria-pressed={value === "importance"}
        onClick={() => onChange("importance")}
      >
        重要性优先
      </button>
    </div>
  );
}
