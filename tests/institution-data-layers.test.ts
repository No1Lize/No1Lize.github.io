import assert from "node:assert/strict";
import test from "node:test";

import rawRankings from "../config/institution_rankings.json";
import rawEntities from "../public/data/institution_entities.json";
import rawEvents from "../public/data/institution_events.json";
import rawEquity from "../public/data/institution_equity_relationships.json";
import {
  institutionDataLayerStats,
  validateInstitutionDataLayers,
} from "../lib/institution-data-layer-data";
import {
  institutionDirectoryStats,
  institutionRankingDataVersion,
} from "../lib/institution-ranking-data";

const rankings = rawRankings as {
  dataVersion: string;
  categories: { ordered: boolean; entries: { rank?: number }[] }[];
};
const entities = rawEntities as {
  dataVersion: string;
  stats: { entities: number; rankingRecords: number };
  entities: { id: string; rankings: unknown[] }[];
};
const events = rawEvents as {
  eventCount: number;
  institutionEventCount: number;
  capitalEventCount: number;
  events: {
    scope: string;
    attributionStatus: string;
    institutionIds: string[];
    attributions: { methods: string[]; evidence: string[] }[];
  }[];
};
const equity = rawEquity as {
  verifiedRelationshipCount: number;
  needsReviewCount: number;
  rejectedCount: number;
  relationships: unknown[];
  candidates: unknown[];
  rejected: unknown[];
};

test("audited ranking JSON preserves all 2025 Qingke records", () => {
  const rankingRecords = rankings.categories.reduce(
    (total, category) => total + category.entries.length,
    0,
  );
  assert.equal(rankings.dataVersion, "2025.1");
  assert.equal(rankingRecords, 220);
  for (const category of rankings.categories) {
    if (category.ordered) {
      assert.deepEqual(
        category.entries.map((entry) => entry.rank),
        category.entries.map((_, index) => index + 1),
      );
    } else {
      assert.ok(category.entries.every((entry) => entry.rank === undefined));
    }
  }
});

test("entity layer is consistent with the public institution directory", () => {
  assert.equal(institutionRankingDataVersion, entities.dataVersion);
  assert.equal(entities.stats.entities, 216);
  assert.equal(entities.stats.rankingRecords, 220);
  assert.equal(entities.stats.entities, institutionDirectoryStats.total);
  assert.equal(entities.stats.rankingRecords, institutionDirectoryStats.rankedRecords);
  assert.equal(new Set(entities.entities.map((entity) => entity.id)).size, 216);
});

test("event layer separates attributed institution events from generic capital events", () => {
  assert.equal(events.eventCount, events.events.length);
  assert.equal(
    events.institutionEventCount + events.capitalEventCount,
    events.eventCount,
  );
  for (const event of events.events) {
    if (event.scope === "institution-event") {
      assert.equal(event.attributionStatus, "attributed");
      assert.ok(event.institutionIds.length > 0);
      assert.ok(
        event.attributions.every(
          (attribution) =>
            attribution.methods.length > 0 && attribution.evidence.length > 0,
        ),
      );
    } else {
      assert.equal(event.scope, "capital-event");
      assert.equal(event.attributionStatus, "unattributed");
      assert.deepEqual(event.institutionIds, []);
    }
  }
});

test("equity relationships and review queues are isolated", () => {
  assert.equal(equity.verifiedRelationshipCount, equity.relationships.length);
  assert.equal(equity.needsReviewCount, equity.candidates.length);
  assert.equal(equity.rejectedCount, equity.rejected.length);
  assert.equal(
    equity.verifiedRelationshipCount + equity.needsReviewCount + equity.rejectedCount,
    33,
  );
});

test("published data layer stats pass cross-file validation", () => {
  assert.deepEqual(validateInstitutionDataLayers(), []);
  assert.equal(institutionDataLayerStats.entities, 216);
  assert.equal(institutionDataLayerStats.rankingRecords, 220);
  assert.equal(institutionDataLayerStats.events, events.eventCount);
});
