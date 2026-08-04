import rawEntities from "@/public/data/institution_entities.json";
import rawEvents from "@/public/data/institution_events.json";
import rawEquity from "@/public/data/institution_equity_relationships.json";

export type InstitutionDataLayerReviewStatus =
  | "verified"
  | "needs_review"
  | "rejected";

export type InstitutionEventLayerRecord = {
  id: string;
  articleId: string;
  scope: "institution-event" | "capital-event";
  attributionStatus: "attributed" | "unattributed";
  eventType: string;
  title: string;
  summary: string;
  region: string;
  sector: string;
  company?: string;
  companySlug?: string;
  publishedAt: string;
  firstSeenAt?: string;
  firstSeenEstimated?: boolean;
  lastVerifiedAt?: string;
  lastVerifiedEstimated?: boolean;
  institutionIds: string[];
  institutionNames: string[];
  attributions: {
    institutionId: string;
    institutionName: string;
    methods: string[];
    evidence: string[];
  }[];
  sourceId?: string;
  source: {
    name: string;
    platform?: string;
    url: string;
    evidenceGrade?: "A" | "B" | "C" | "D";
    evidenceLabel?: string;
    evidencePolicy?: string;
  };
};

type EntityLayerPayload = {
  schemaVersion: number;
  dataVersion: string;
  generatedAt: string;
  stats: {
    entities: number;
    aliases?: number;
    officialDomains?: number;
    china: number;
    us: number;
    detailedProfiles: number;
    rankingRecords: number;
  };
  entities: unknown[];
};

type EventLayerPayload = {
  schemaVersion: number;
  generatedAt: string;
  eventCount: number;
  institutionEventCount: number;
  capitalEventCount: number;
  attributedInstitutionCount?: number;
  events: InstitutionEventLayerRecord[];
};

type EquityLayerPayload = {
  schemaVersion: number;
  generatedAt: string;
  verifiedRelationshipCount: number;
  needsReviewCount: number;
  rejectedCount: number;
  relationships: unknown[];
  candidates: unknown[];
  rejected: unknown[];
};

const entityLayer = rawEntities as EntityLayerPayload;
const eventLayer = rawEvents as EventLayerPayload;
const equityLayer = rawEquity as EquityLayerPayload;

export const institutionDataLayerVersions = {
  rankingsAndEntities: entityLayer.dataVersion,
  entitiesGeneratedAt: entityLayer.generatedAt,
  eventsGeneratedAt: eventLayer.generatedAt,
  equityGeneratedAt: equityLayer.generatedAt,
};

export const institutionDataLayerStats = {
  entities: entityLayer.stats.entities,
  chinaEntities: entityLayer.stats.china,
  usEntities: entityLayer.stats.us,
  detailedProfiles: entityLayer.stats.detailedProfiles,
  rankingRecords: entityLayer.stats.rankingRecords,
  events: eventLayer.eventCount,
  institutionEvents: eventLayer.institutionEventCount,
  capitalEvents: eventLayer.capitalEventCount,
  attributedInstitutions: eventLayer.attributedInstitutionCount ?? 0,
  verifiedEquityRelationships: equityLayer.verifiedRelationshipCount,
  needsReviewEquityCandidates: equityLayer.needsReviewCount,
  rejectedEquityCandidates: equityLayer.rejectedCount,
};

export const institutionEventLayerRecords = eventLayer.events;

export function validateInstitutionDataLayers() {
  const errors: string[] = [];
  if (entityLayer.schemaVersion !== 1) errors.push("invalid:entity-schema");
  if (eventLayer.schemaVersion !== 1) errors.push("invalid:event-schema");
  if (equityLayer.schemaVersion !== 1) errors.push("invalid:equity-schema");
  if (entityLayer.stats.entities !== entityLayer.entities.length) {
    errors.push("invalid:entity-count");
  }
  if (eventLayer.eventCount !== eventLayer.events.length) {
    errors.push("invalid:event-count");
  }
  if (equityLayer.verifiedRelationshipCount !== equityLayer.relationships.length) {
    errors.push("invalid:verified-equity-count");
  }
  if (equityLayer.needsReviewCount !== equityLayer.candidates.length) {
    errors.push("invalid:needs-review-equity-count");
  }
  if (equityLayer.rejectedCount !== equityLayer.rejected.length) {
    errors.push("invalid:rejected-equity-count");
  }
  return errors;
}
