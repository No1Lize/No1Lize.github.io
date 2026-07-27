import { ArrowUpRight } from "lucide-react";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";
import styles from "./dashboard-quality.module.css";

export function EventQualityIndicator({ item }: { item: LiveIntelligenceEvent }) {
  const relatedSources = item.relatedSources ?? [];
  const relatedCount = Math.max(item.duplicateCount ?? 0, relatedSources.length);
  const hasQuality =
    Boolean(item.qualityStatus) ||
    typeof item.qualityScore === "number" ||
    relatedCount > 0 ||
    Boolean(item.qualitySignals?.length);

  if (!hasQuality) return null;

  return (
    <div className={styles.sourceRow} aria-label="信息质量与关联证据">
      {item.qualityStatus && (
        <span
          className={styles.qualityBadge}
          data-status={item.qualityStatus}
          title={item.qualitySignals?.join("；") || "用户追踪结果质量等级"}
        >
          {item.qualityStatus}
          {typeof item.qualityScore === "number" ? ` · ${item.qualityScore}` : ""}
        </span>
      )}

      {!item.qualityStatus && typeof item.qualityScore === "number" && (
        <span className={styles.qualityBadge}>质量分 {item.qualityScore}</span>
      )}

      {relatedCount > 0 && (
        <details className={styles.evidence}>
          <summary>关联来源 {relatedCount}</summary>
          {relatedSources.length > 0 && (
            <div className={styles.evidenceList}>
              {relatedSources.map((source, index) => (
                <a
                  href={source.url}
                  key={`${source.url}-${index}`}
                  target="_blank"
                  rel="noreferrer"
                  title={source.title}
                >
                  <strong>{source.title || source.name}</strong>
                  <span>
                    {source.level || source.platform || source.name}
                    <ArrowUpRight size={11} />
                  </span>
                </a>
              ))}
            </div>
          )}
        </details>
      )}

      {item.qualitySignals?.length ? (
        <span title={item.qualitySignals.join("；")}>
          {item.qualitySignals[0]}
        </span>
      ) : null}
    </div>
  );
}
