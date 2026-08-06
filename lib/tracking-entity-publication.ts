import type { TrackingCaptureRecord } from "@/lib/tracking-capture";

export type PublishedTrackingCaptureDescriptor = Pick<
  TrackingCaptureRecord,
  "entityType" | "canonicalName"
>;

/**
 * A capture may enter the public research graph only after the review workflow
 * has produced a final resolved identity. The historical "applied without a
 * resolution" fallback is intentionally rejected because it can preserve the
 * originally requested, and potentially incorrect, entity type.
 */
export function isPublishableTrackingCapture(capture: TrackingCaptureRecord) {
  return (
    capture.status === "applied" &&
    capture.resolution?.status === "resolved"
  );
}

/**
 * Publish the resolved canonical identity, never the originally requested
 * type/name. Review, rejected, queued, dismissed and legacy unresolved records
 * stay internal.
 */
export function publishedTrackingCaptureDescriptor(
  capture: TrackingCaptureRecord,
): PublishedTrackingCaptureDescriptor | undefined {
  const resolution = capture.resolution;
  if (!isPublishableTrackingCapture(capture) || resolution?.status !== "resolved") {
    return undefined;
  }
  return {
    entityType: resolution.entityType,
    canonicalName: resolution.canonicalName,
  };
}
