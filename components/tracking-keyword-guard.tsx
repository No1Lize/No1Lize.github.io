"use client";

/**
 * Input validation is handled directly by UserTrackingPanel.
 *
 * This compatibility component remains mounted by UserTrackingLoader so older
 * builds and imports do not break, but it intentionally renders no duplicate
 * UI or DOM observers.
 */
export function TrackingKeywordGuard() {
  return null;
}
