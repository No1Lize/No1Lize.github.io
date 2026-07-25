import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export function EventQualityIndicator({ item }: { item: LiveIntelligenceEvent }) {
  if (!item.qualityStatus && typeof item.qualityScore !== "number" && !item.duplicateCount) {
    return null;
  }

  return (
    <div className="event-quality" aria-label="信息质量">
      {item.qualityStatus && (
        <span className={`quality-status quality-${item.qualityStatus}`}>
          {item.qualityStatus}
        </span>
      )}
      {typeof item.qualityScore === "number" && (
        <span>质量分 {item.qualityScore}</span>
      )}
      {typeof item.duplicateCount === "number" && item.duplicateCount > 0 && (
        <span>关联来源 {item.duplicateCount}</span>
      )}
      {item.qualitySignals?.length ? (
        <span title={item.qualitySignals.join("；")}>
          {item.qualitySignals[0]}
        </span>
      ) : null}
    </div>
  );
}
