import assert from "node:assert/strict";
import test from "node:test";
import {
  getInstitutionRankingEntry,
  institutionDirectory,
  institutionDirectoryStats,
  institutionRankingSources,
} from "../lib/institution-ranking-data";

test("professional institution directory keeps complete Qingke main lists", () => {
  assert.equal(institutionDirectoryStats.china, 206);
  assert.equal(institutionDirectoryStats.us, 10);
  assert.equal(institutionDirectoryStats.total, 216);
  assert.equal(institutionDirectoryStats.rankedRecords, 220);
  assert.equal(new Set(institutionDirectory.map((item) => item.name)).size, institutionDirectory.length);
});

test("ordered rankings retain exact published positions", () => {
  assert.equal(getInstitutionRankingEntry("中科创星")?.rankings[0]?.rank, 1);
  assert.equal(getInstitutionRankingEntry("IDG资本")?.rankings.find((item) => item.category === "创业投资")?.rank, 1);
  assert.equal(getInstitutionRankingEntry("红杉中国")?.rankings.find((item) => item.category === "私募股权")?.rank, 1);
  assert.equal(getInstitutionRankingEntry("华睿投资")?.rankings[0]?.rank, 50);
});

test("cross-list institutions are merged and linked to detailed profiles", () => {
  const hongshan = getInstitutionRankingEntry("红杉中国");
  assert.equal(hongshan?.profileSlug, "hongshan");
  assert.deepEqual(
    hongshan?.rankings.map((item) => item.category).sort(),
    ["并购投资", "私募股权"].sort(),
  );
  assert.equal(getInstitutionRankingEntry("深创投")?.profileSlug, "scgc");
  assert.equal(getInstitutionRankingEntry("高瓴")?.profileSlug, "hillhouse");
});

test("source metadata distinguishes names from category-only cross checks", () => {
  assert.equal(institutionRankingSources[0].publisher, "清科研究中心 / 投资界");
  assert.ok(institutionRankingSources[0].categories.includes("国资投资50强"));
  assert.equal(institutionRankingSources[1].publisher, "投中研究院 / 投中网");
  assert.ok(institutionRankingSources[1].categories.includes("人工智能与大数据"));
});
