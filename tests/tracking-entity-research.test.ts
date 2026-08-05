import assert from "node:assert/strict";
import test from "node:test";

import {
  trackingResearchEntities,
  trackingResearchEntity,
  trackingResearchHref,
} from "../lib/tracking-entity-research";
import {
  trackingEntityRouteDescriptor,
  trackingEntityResearchHref,
} from "../lib/tracking-entity-route";
import { userTrackingConfig } from "../lib/user-tracking";

test("tracked entity research routes are unique and resolvable", () => {
  assert.ok(trackingResearchEntities.length > 0);
  const routes = trackingResearchEntities.map(
    (entity) => `${entity.entityType}:${entity.slug}`,
  );
  assert.equal(new Set(routes).size, routes.length);
  for (const entity of trackingResearchEntities) {
    assert.equal(
      trackingResearchEntity(entity.entityType, entity.slug)?.id,
      entity.id,
    );
    assert.equal(
      trackingResearchHref(entity),
      `/tracking/entities/${entity.entityType}/${entity.slug}`,
    );
  }
});

test("enabled tracks expose their companies, people and track topic", () => {
  for (const track of userTrackingConfig.tracks.filter((item) => item.enabled)) {
    for (const company of track.sampleCompanies) {
      const route = trackingEntityRouteDescriptor("company", company);
      assert.ok(
        trackingResearchEntities.some((entity) => entity.id === route.id),
        `missing tracked company ${company}`,
      );
    }
    for (const person of track.people) {
      const route = trackingEntityRouteDescriptor("person", person);
      assert.ok(
        trackingResearchEntities.some((entity) => entity.id === route.id),
        `missing tracked person ${person}`,
      );
    }
    const topic = trackingEntityRouteDescriptor("topic", track.name);
    assert.ok(
      trackingResearchEntities.some((entity) => entity.id === topic.id),
      `missing track topic ${track.name}`,
    );
  }
});

test("route helper matches generated entity routes", () => {
  for (const entity of trackingResearchEntities.slice(0, 60)) {
    assert.equal(
      trackingEntityResearchHref(entity.entityType, entity.name),
      trackingResearchHref(entity),
    );
  }
});

test("research timelines are reverse chronological and deduplicate URLs", () => {
  for (const entity of trackingResearchEntities) {
    for (let index = 1; index < entity.timeline.length; index += 1) {
      assert.ok(
        entity.timeline[index - 1].sortAt >= entity.timeline[index].sortAt,
        `${entity.name} timeline is not reverse chronological`,
      );
    }
    const urls = entity.timeline.map((item) => item.url);
    assert.equal(
      new Set(urls).size,
      urls.length,
      `${entity.name} timeline contains duplicate source URLs`,
    );
  }
});

test("formal entities expose their existing research routes", () => {
  const formal = trackingResearchEntities.filter((entity) => entity.state === "formal");
  assert.ok(formal.length > 0);
  for (const entity of formal) {
    assert.ok(entity.formalHref.startsWith("/companies/") || entity.formalHref.startsWith("/people/"));
    assert.ok(entity.formalLabel);
  }
});
