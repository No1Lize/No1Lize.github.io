import rawSnapshot from "@/public/data/articles.json";
import type { IntelligenceEvent } from "@/lib/intelligence-data";

export type TrackCoverageStatus =
  | "pending"
  | "partial"
  | "ready"
  | "empty"
  | "error";

export type TrackCoverage = {
  slug: string;
  name: string;
  status: TrackCoverageStatus;
  label: string;
  expectedSources: number;
  completedSources: number;
  healthySources: number;
  failedSources: number;
  scanned: number;
  accepted: number;
  matchedArticles: number;
  backfilledArticles: number;
  independentSources: number;
  lastRun: string;
  message: string;
};

type ExtendedEvent = IntelligenceEvent & {
  trackSlugs?: string[];
};

type TrackingSnapshot = {
  generatedAt?: string;
  trackingConfigHash?: string;
  trackingEnrichedAt?: string;
  trackCoverage?: Record<string, TrackCoverage>;
};

const snapshot = rawSnapshot as TrackingSnapshot;

export const trackingConfigHash = snapshot.trackingConfigHash ?? "";
export const trackingEnrichedAt = snapshot.trackingEnrichedAt ?? "";
export const trackingSnapshotGeneratedAt = snapshot.generatedAt ?? "";
export const trackCoverage: Record<string, TrackCoverage> =
  snapshot.trackCoverage ?? {};

export function eventTrackSlugs(event: IntelligenceEvent): string[] {
  const values = (event as ExtendedEvent).trackSlugs;
  return Array.isArray(values)
    ? values.filter((value): value is string => typeof value === "string")
    : [];
}

export function fallbackTrackCoverage(slug: string, name: string): TrackCoverage {
  return {
    slug,
    name,
    status: "pending",
    label: "等待爬取",
    expectedSources: 3,
    completedSources: 0,
    healthySources: 0,
    failedSources: 0,
    scanned: 0,
    accepted: 0,
    matchedArticles: 0,
    backfilledArticles: 0,
    independentSources: 0,
    lastRun: trackingSnapshotGeneratedAt,
    message: "当前快照尚未包含该赛道的首次爬取覆盖记录。",
  };
}
