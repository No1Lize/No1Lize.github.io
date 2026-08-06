import {
  trackingResearchEntities,
  type TrackingResearchEntity,
  type TrackingResearchEntityType,
} from "@/lib/tracking-entity-research";

/**
 * Public research pages are reserved for entities with actual research value.
 * Seed/config-only entities remain available to the internal tracking system
 * and become public automatically once evidence or an analyst record exists.
 */
export function isSubstantiveTrackingResearchEntity(
  entity: TrackingResearchEntity,
) {
  return (
    entity.captureCount > 0 ||
    entity.articleCount > 0 ||
    entity.priority > 0 ||
    Boolean(entity.researchRecord) ||
    Boolean(entity.researchThesis) ||
    entity.analystNotes.length > 0
  );
}

export const publishedTrackingResearchEntities = trackingResearchEntities.filter(
  isSubstantiveTrackingResearchEntity,
);

const publishedEntityByRoute = new Map(
  publishedTrackingResearchEntities.map((entity) => [
    `${entity.entityType}:${entity.slug}`,
    entity,
  ]),
);

export function publishedTrackingResearchEntity(
  entityType: TrackingResearchEntityType,
  slug: string,
) {
  return publishedEntityByRoute.get(`${entityType}:${slug}`);
}

export const publishedTrackingResearchStats = {
  entityCount: publishedTrackingResearchEntities.length,
  companyCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.entityType === "company",
  ).length,
  personCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.entityType === "person",
  ).length,
  topicCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.entityType === "topic",
  ).length,
  formalCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.state === "formal",
  ).length,
  candidateCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.state === "candidate",
  ).length,
  capturedCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.captureCount > 0,
  ).length,
  priorityCount: publishedTrackingResearchEntities.filter(
    (entity) => entity.priority >= 4,
  ).length,
  noteCount: publishedTrackingResearchEntities.reduce(
    (total, entity) => total + entity.analystNotes.length,
    0,
  ),
};
