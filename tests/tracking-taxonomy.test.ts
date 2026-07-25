import assert from "node:assert/strict";
import test from "node:test";

import {
  detectTrackOverlaps,
  trackIdentityTerms,
  trackNameAliases,
  uniqueActorTermsByTrack,
  uniqueIdentityTermsByTrack,
} from "../lib/tracking-taxonomy";
import type { TrackingTrack } from "../lib/user-tracking";

function track(
  slug: string,
  name: string,
  overrides: Partial<TrackingTrack> = {},
): TrackingTrack {
  return {
    slug,
    name,
    enabled: true,
    custom: true,
    keywords: [],
    people: [],
    sampleCompanies: [],
    ...overrides,
  };
}

test("track aliases are derived for bilingual and punctuation-rich names", () => {
  assert.deepEqual(trackNameAliases("AI / AGI"), ["AI / AGI", "AI/AGI", "AI", "AGI"]);
  assert.deepEqual(trackNameAliases("脑机接口（BCI）"), ["脑机接口(BCI)", "脑机接口", "BCI"]);
});

test("identity terms include arbitrary track names and configured keywords", () => {
  const terms = trackIdentityTerms(
    track("fusion", "可控核聚变", {
      keywords: ["聚变能源", "托卡马克"],
    }),
  );
  assert.ok(terms.includes("可控核聚变"));
  assert.ok(terms.includes("聚变能源"));
  assert.ok(terms.includes("托卡马克"));
});

test("equivalent track names are blocking taxonomy collisions", () => {
  const overlaps = detectTrackOverlaps([
    track("ai-agi", "AI / AGI"),
    track("agi", "AGI"),
  ]);
  assert.ok(
    overlaps.some(
      (item) =>
        item.kind === "identity" &&
        item.severity === "error" &&
        item.normalized === "agi",
    ),
  );
});

test("shared companies and keywords are warnings rather than hard failures", () => {
  const overlaps = detectTrackOverlaps([
    track("energy", "新能源", {
      keywords: ["聚变能源"],
      sampleCompanies: ["Helion Energy"],
    }),
    track("fusion", "可控核聚变", {
      keywords: ["聚变能源"],
      sampleCompanies: ["Helion Energy"],
    }),
  ]);
  assert.ok(
    overlaps.some(
      (item) => item.kind === "keyword" && item.severity === "warning",
    ),
  );
  assert.ok(
    overlaps.some(
      (item) => item.kind === "company" && item.severity === "warning",
    ),
  );
  assert.equal(overlaps.some((item) => item.severity === "error"), false);
});

test("shared keywords do not own event matching for multiple sectors", () => {
  const energy = track("energy", "新能源", {
    keywords: ["聚变能源", "长时储能"],
  });
  const fusion = track("fusion", "可控核聚变", {
    keywords: ["聚变能源", "托卡马克"],
  });
  const identities = uniqueIdentityTermsByTrack([energy, fusion]);
  assert.deepEqual(identities.get("energy"), ["新能源", "长时储能"]);
  assert.deepEqual(identities.get("fusion"), ["可控核聚变", "托卡马克"]);
});

test("only sector-unique actors expand standalone crawler discovery", () => {
  const energy = track("energy", "新能源", {
    sampleCompanies: ["Helion Energy", "宁德时代"],
  });
  const fusion = track("fusion", "可控核聚变", {
    sampleCompanies: ["Helion Energy", "Commonwealth Fusion Systems"],
  });
  const actors = uniqueActorTermsByTrack([energy, fusion]);
  assert.deepEqual(actors.get("energy"), ["宁德时代"]);
  assert.deepEqual(actors.get("fusion"), ["Commonwealth Fusion Systems"]);
});
