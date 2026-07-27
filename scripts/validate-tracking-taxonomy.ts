import process from "node:process";

import { detectTrackOverlaps } from "../lib/tracking-taxonomy";
import { userTrackingConfig } from "../lib/user-tracking";

const overlaps = detectTrackOverlaps(userTrackingConfig.tracks);
const errors = overlaps.filter((item) => item.severity === "error");
const warnings = overlaps.filter((item) => item.severity === "warning");

for (const item of warnings) {
  console.warn(
    `TRACKING_TAXONOMY_WARNING: ${item.kind} “${item.value}” 同时属于 ${item.tracks
      .map((track) => track.name)
      .join("、")}；爬虫不会把共享公司或人物作为无约束的独立搜索词。`,
  );
}

if (errors.length) {
  for (const item of errors) {
    console.error(
      `TRACKING_TAXONOMY_ERROR: 等价赛道名称 “${item.value}” 同时属于 ${item.tracks
        .map((track) => `${track.name} (${track.slug})`)
        .join("、")}。请合并赛道或修改名称。`,
    );
  }
  process.exit(1);
}

console.log(
  `Tracking taxonomy valid: ${userTrackingConfig.tracks.length} tracks, ${warnings.length} non-blocking overlaps.`,
);
