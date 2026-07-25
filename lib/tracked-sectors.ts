import {
  intelligenceEvents,
  type IntelligenceEvent,
} from "@/lib/intelligence-data";
import {
  sectorDefinitions,
  type SectorDefinition,
} from "@/lib/sector-definitions";
import {
  resolveSectorDefinition,
  sectorCompleteness,
} from "@/lib/sector-profile-generator";
import {
  eventTrackSlugs,
  fallbackTrackCoverage,
  trackCoverage,
  type TrackCoverage,
} from "@/lib/tracking-snapshot";
import {
  normalizeTaxonomyTerm,
  uniqueIdentityTermsByTrack,
} from "@/lib/tracking-taxonomy";
import {
  userTrackingConfig,
  type TrackingTrack,
} from "@/lib/user-tracking";

export type TrackedSector = SectorDefinition & {
  heat: number;
  completeness: number;
  trend: "up" | "flat" | "down";
  events: number;
  institutions: number;
  financingEvents: number;
  sourceCount: number;
  fundingLabel: string;
  tracking: TrackingTrack;
  aliases: string[];
  coverage: TrackCoverage;
  baseName?: string;
  profileMode: "curated" | "generated";
};

type SectorRaw = {
  tracking: TrackingTrack;
  base?: SectorDefinition;
  aliases: string[];
  events: IntelligenceEvent[];
  coverage: TrackCoverage;
  financing: number;
  institutions: number;
  weightedEvents: number;
  ipo: number;
  research: number;
  current: number;
  previous: number;
};

function unique(values: string[], limit = 12): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const cleaned = value.trim();
    const key = normalizeTaxonomyTerm(cleaned);
    if (!cleaned || !key || seen.has(key)) continue;
    result.push(cleaned);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function dateValue(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizer(values: number[]): (value: number) => number {
  const maximum = Math.max(...values, 0);
  return (value) => (maximum > 0 ? Math.round((value / maximum) * 100) : 0);
}

function eventBelongsToTrack(
  event: IntelligenceEvent,
  slug: string,
  aliasKeys: Set<string>,
): boolean {
  const assignedSlugs = eventTrackSlugs(event);
  if (assignedSlugs.length) return assignedSlugs.includes(slug);
  return aliasKeys.has(normalizeTaxonomyTerm(event.sector));
}

function buildRaw(): SectorRaw[] {
  const baseBySlug = new Map(
    sectorDefinitions.map((sector) => [sector.slug, sector]),
  );
  const baseByName = new Map(
    sectorDefinitions.map((sector) => [sector.name, sector]),
  );
  const asOf = Math.max(
    Date.now(),
    ...intelligenceEvents.map((event) => dateValue(event.publishedAt)),
  );
  const yearAgo = asOf - 365 * 24 * 60 * 60 * 1000;
  const ninetyDaysAgo = asOf - 90 * 24 * 60 * 60 * 1000;
  const previousNinetyDays = asOf - 180 * 24 * 60 * 60 * 1000;
  const activeTracks = userTrackingConfig.tracks.filter((track) => track.enabled);
  const ownedIdentityTerms = uniqueIdentityTermsByTrack(activeTracks);

  return activeTracks.map((tracking) => {
    const base =
      baseBySlug.get(tracking.slug) ?? baseByName.get(tracking.name);
    const aliases = unique(
      [
        ...(ownedIdentityTerms.get(tracking.slug) ?? [tracking.name]),
        base?.name ?? "",
      ],
      24,
    );
    const aliasKeys = new Set(aliases.map(normalizeTaxonomyTerm));
    const events = intelligenceEvents.filter(
      (event) =>
        eventBelongsToTrack(event, tracking.slug, aliasKeys) &&
        dateValue(event.publishedAt) >= yearAgo,
    );
    const coverage =
      trackCoverage[tracking.slug] ??
      fallbackTrackCoverage(tracking.slug, tracking.name);
    const financing = events.filter((event) => event.type === "融资").length;
    const institutions = new Set(
      events.flatMap((event) => event.institutions ?? []),
    ).size;
    const weightedEvents = Math.round(
      events.reduce((sum, event) => sum + event.importance, 0) / 100,
    );
    const ipo = events.filter((event) =>
      ["IPO", "监管文件", "财报"].includes(event.type),
    ).length;
    const research = events.filter((event) =>
      ["技术突破", "政策", "产品发布", "论文"].includes(event.type),
    ).length;
    const current = events.filter(
      (event) => dateValue(event.publishedAt) >= ninetyDaysAgo,
    ).length;
    const previous = events.filter((event) => {
      const timestamp = dateValue(event.publishedAt);
      return timestamp >= previousNinetyDays && timestamp < ninetyDaysAgo;
    }).length;

    return {
      tracking,
      base,
      aliases,
      events,
      coverage,
      financing,
      institutions,
      weightedEvents,
      ipo,
      research,
      current,
      previous,
    };
  });
}

function buildTrackedSectors(): TrackedSector[] {
  const raw = buildRaw();
  const normalizeFinancing = normalizer(raw.map((item) => item.financing));
  const normalizeInstitutions = normalizer(raw.map((item) => item.institutions));
  const normalizeEvents = normalizer(raw.map((item) => item.weightedEvents));
  const normalizeIpo = normalizer(raw.map((item) => item.ipo));
  const normalizeResearch = normalizer(raw.map((item) => item.research));

  return raw.map((item) => {
    const { tracking, base, aliases, events, coverage } = item;
    const sourceCount = new Set(events.map((event) => event.source.url)).size;
    const definition = resolveSectorDefinition(tracking, events, base);
    const heat = Math.round(
      0.3 * normalizeFinancing(item.financing) +
        0.2 * normalizeInstitutions(item.institutions) +
        0.2 * normalizeEvents(item.weightedEvents) +
        0.15 * normalizeIpo(item.ipo) +
        0.15 * normalizeResearch(item.research),
    );

    return {
      ...definition,
      slug: tracking.slug,
      name: tracking.name,
      heat,
      completeness: sectorCompleteness(tracking, events, Boolean(base)),
      trend:
        item.current > item.previous
          ? "up"
          : item.current < item.previous
            ? "down"
            : "flat",
      events: events.length,
      institutions: item.institutions,
      financingEvents: item.financing,
      sourceCount,
      fundingLabel: `${item.financing} 笔融资披露`,
      tracking,
      aliases,
      coverage,
      baseName: base?.name,
      profileMode: base ? "curated" : "generated",
    };
  });
}

export const trackedSectors: TrackedSector[] = buildTrackedSectors();

export function getTrackedSector(slug: string): TrackedSector | undefined {
  return trackedSectors.find((sector) => sector.slug === slug);
}

export function eventsForTrackedSector(
  sector: Pick<TrackedSector, "aliases" | "slug">,
): IntelligenceEvent[] {
  const aliasKeys = new Set(sector.aliases.map(normalizeTaxonomyTerm));
  return intelligenceEvents.filter((event) =>
    eventBelongsToTrack(event, sector.slug, aliasKeys),
  );
}
