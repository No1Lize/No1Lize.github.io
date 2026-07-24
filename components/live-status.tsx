"use client";

import { useArticles } from "@/lib/use-articles";

export function LiveStatus() {
  const { generatedAt, isLive, error } = useArticles();
  return (
    <span
      className="updated"
      title={error instanceof Error ? error.message : undefined}
    >
      <i className={isLive ? "" : "muted-dot"} />
      {isLive ? "自动更新 JSON" : "内置快照"} {generatedAt.slice(0, 10)}
    </span>
  );
}
