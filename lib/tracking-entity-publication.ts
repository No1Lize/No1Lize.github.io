import type { TrackingCaptureRecord } from "@/lib/tracking-capture";

export type PublishedTrackingCaptureDescriptor = Pick<
  TrackingCaptureRecord,
  "entityType" | "canonicalName"
>;

/**
 * Only records that have actually been applied may enter the public research
 * entity graph. Legacy applied records without a resolution remain publishable;
 * once a resolution exists it must be final and resolved.
 */
export function isPublishableTrackingCapture(capture: TrackingCaptureRecord) {
  if (capture.status !== "applied") return false;
  return !capture.resolution || capture.resolution.status === "resolved";
}

/**
 * Publish the resolved canonical identity, never the originally requested
 * type/name. Review, rejected, queued and dismissed records stay internal.
 */
export function publishedTrackingCaptureDescriptor(
  capture: TrackingCaptureRecord,
): PublishedTrackingCaptureDescriptor | undefined {
  if (!isPublishableTrackingCapture(capture)) return undefined;
  if (capture.resolution?.status === "resolved") {
    return {
      entityType: capture.resolution.entityType,
      canonicalName: capture.resolution.canonicalName,
    };
  }
  return {
    entityType: capture.entityType,
    canonicalName: capture.canonicalName,
  };
}
