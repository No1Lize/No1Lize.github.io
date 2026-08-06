import assert from "node:assert/strict";
import test from "node:test";

import {
  isSubstantiveTrackingResearchEntity,
  publishedTrackingResearchEntities,
  publishedTrackingResearchEntity,
  publishedTrackingResearchStats,
} from "../lib/published-tracking-entity-research";
import { trackingResearchEntities } from "../lib/tracking-entity-research";

test("public tracking research excludes config-only placeholders", () => {
  assert.ok(trackingResearchEntities.length > publishedTrackingResearchEntities.length);
  assert.ok(publishedTrackingResearchEntities.length > 0);

  for (const entity of publishedTrackingResearchEntities) {
    assert.equal(
      isSubstantiveTrackingResearchEntity(entity),
      true,
      `${entity.id} has no substantive public research content`,
    );
  }

  const placeholders = trackingResearchEntities.filter(
    (entity) => !isSubstantiveTrackingResearchEntity(entity),
  );
  assert.ok(placeholders.length > 0);
  assert.ok(
    placeholders.every(
      (entity) =>
        entity.captureCount === 0 &&
        entity.articleCount === 0 &&
        entity.priority === 0 &&
        !entity.researchRecord,
    ),
  );
});

test("evidence and analyst work always publish an entity route", () => {
  for (const entity of trackingResearchEntities) {
    const mustPublish =
      entity.captureCount > 0 ||
      entity.articleCount > 0 ||
      entity.priority > 0 ||
      Boolean(entity.researchRecord) ||
      Boolean(entity.researchThesis) ||
      entity.analystNotes.length > 0;
    if (!mustPublish) continue;
    assert.ok(
      publishedTrackingResearchEntities.some((candidate) => candidate.id === entity.id),
      `missing substantive entity ${entity.id}`,
    );
  }
});

test("published route lookup and statistics match the public collection", () => {
  const routeKeys = publishedTrackingResearchEntities.map(
    (entity) => `${entity.entityType}:${entity.slug}`,
  );
  assert.equal(new Set(routeKeys).size, routeKeys.length);

  for (const entity of publishedTrackingResearchEntities) {
    assert.equal(
      publishedTrackingResearchEntity(entity.entityType, entity.slug)?.id,
      entity.id,
    );
  }

  assert.equal(
    publishedTrackingResearchStats.entityCount,
    publishedTrackingResearchEntities.length,
  );
  assert.equal(
    publishedTrackingResearchStats.companyCount +
      publishedTrackingResearchStats.personCount +
      publishedTrackingResearchStats.topicCount,
    publishedTrackingResearchStats.entityCount,
  );
});
