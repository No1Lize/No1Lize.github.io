import type { TrackingCaptureEntityType } from "@/lib/tracking-capture";
import type { TrackingEntityResearchRecord } from "@/lib/tracking-entity-records";

/**
 * Public Pages builds are deliberately read-only. Research record maintenance
 * belongs in the repository review workflow and must not ship GitHub write
 * clients, token fields or mutation controls to the public static artifact.
 *
 * The compatibility export remains temporarily so detail pages can drop the
 * former editor without a broad layout refactor.
 */
export function TrackingEntityResearchEditor(_props: {
  entityId: string;
  entityType: TrackingCaptureEntityType;
  entityName: string;
  initialRecord?: TrackingEntityResearchRecord;
}) {
  return null;
}
