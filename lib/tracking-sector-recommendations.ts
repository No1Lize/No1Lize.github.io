import type { LiveIntelligenceEvent } from "@/lib/use-articles";
import {
  recommendTrackingAdditions as recommendBaseTrackingAdditions,
  type TrackingRecommendationSet,
} from "@/lib/tracking-recommendations";
import {
  isKnownTrackingSeedTerm,
  isTrackingTermAllowedForSector,
  trackingSectorsMatch,
} from "@/lib/tracking-sector-policy";

type ExistingTrackingValues = {
  keywords?: string[];
  people?: string[];
  companies?: string[];
  sources?: string[];
};

/**
 * Production recommendation boundary.
 *
 * The base extractor remains deliberately recall-oriented. This wrapper makes
 * the user-visible result precision-oriented by applying strict sector
 * isolation before and after extraction.
 */
export function recommendSectorTrackingAdditions(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: ExistingTrackingValues = {},
): TrackingRecommendationSet {
  const sectorArticles = articles.filter((article) =>
    trackingSectorsMatch(article.sector, selectedSector),
  );
  const result = recommendBaseTrackingAdditions(
    sectorArticles,
    selectedSector,
    existing,
  );

  return {
    ...result,
    keywords: result.keywords.filter((item) => {
      if (!isKnownTrackingSeedTerm(item.value)) return true;
      return isTrackingTermAllowedForSector(item.value, selectedSector);
    }),
  };
}
