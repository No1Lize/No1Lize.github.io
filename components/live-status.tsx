"use client";

import { formatTaipeiDateTime } from "@/lib/snapshot-freshness";
import { useArticles } from "@/lib/use-articles";

export function LiveStatus() {
  const { generatedAt, refreshAudit, isLive, error } = useArticles();
  const syncedAt = formatTaipeiDateTime(refreshAudit?.completedAt || generatedAt);

  return (
    <a
      className="updated"
      title={error instanceof Error ? error.message : `最后成功发布：${syncedAt}`}
      href="https://github.com/VCIQ/VCIQ.github.io/actions/workflows/scheduled-sync.yml"
      target="_blank"
      rel="noreferrer"
    >
      <i className={isLive ? "" : "muted-dot"} />
      {isLive ? "资料已同步" : "资料快照"} {syncedAt}
    </a>
  );
}
