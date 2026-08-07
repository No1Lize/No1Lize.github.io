import { formatTaipeiDateTime } from "@/lib/snapshot-freshness";
import rawArticles from "@/public/data/articles.json";

type StatusSnapshot = {
  generatedAt?: string;
  refreshAudit?: {
    completedAt?: string;
    pipelineCompleted?: boolean;
  };
  qualityGate?: {
    passed?: boolean;
  };
};

/**
 * Build-time status only. The previous client component called useArticles()
 * from the global header, which downloaded the entire public article database
 * on every route just to render this timestamp.
 */
export function LiveStatus() {
  const snapshot = rawArticles as StatusSnapshot;
  const syncedAt = formatTaipeiDateTime(
    snapshot.refreshAudit?.completedAt || snapshot.generatedAt || "",
  );
  const healthy =
    snapshot.refreshAudit?.pipelineCompleted !== false &&
    snapshot.qualityGate?.passed !== false;

  return (
    <a
      className="updated"
      title={`最后成功发布：${syncedAt}`}
      href="https://github.com/VCIQ/VCIQ.github.io/actions/workflows/scheduled-sync.yml"
      target="_blank"
      rel="noreferrer"
    >
      <i className={healthy ? "" : "muted-dot"} />
      {healthy ? "资料已同步" : "资料快照"} {syncedAt}
    </a>
  );
}
