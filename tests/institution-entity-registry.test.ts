import assert from "node:assert/strict";
import test from "node:test";

import {
  institutionEntities,
  institutionEntityByName,
  institutionEntityRegistryStats,
  resolveArticleInstitutionEntities,
} from "../lib/institution-entity-registry";
import { institutionDirectory } from "../lib/institution-ranking-data";

test("institution registry covers the complete public institution directory", () => {
  assert.equal(institutionEntities.length, institutionDirectory.length);
  assert.equal(institutionEntityRegistryStats.entities, institutionDirectory.length);
  assert.ok(institutionEntityRegistryStats.aliases >= institutionDirectory.length);
});

test("reviewed aliases resolve to one canonical institution", () => {
  assert.equal(institutionEntityByName("IDG 资本")?.name, "IDG资本");
  assert.equal(institutionEntityByName("深创投")?.name, "深创投集团");
  assert.equal(institutionEntityByName("Hillhouse")?.name, "高瓴投资");
});

test("structured institution fields resolve legal names to display entities", () => {
  const entities = resolveArticleInstitutionEntities({
    institutions: ["深圳市创新投资集团有限公司"],
  });

  assert.deepEqual(entities.map((entity) => entity.name), ["深创投集团"]);
});

test("text matching covers ranked institutions without detailed profiles", () => {
  const entities = resolveArticleInstitutionEntities({
    title: "蓝驰创投完成新一期人民币基金募集",
    summary: "该机构将继续投资早期科技项目。",
  });

  assert.ok(entities.some((entity) => entity.name === "蓝驰创投"));
});

test("official institution domains resolve the institution without a text mention", () => {
  const entities = resolveArticleInstitutionEntities({
    title: "New portfolio update",
    source: { url: "https://www.idgcapital.com/news/sample" },
  });

  assert.ok(entities.some((entity) => entity.name === "IDG资本"));
});

test("generic capital-event prose does not fabricate an institution entity", () => {
  const entities = resolveArticleInstitutionEntities({
    title: "某人工智能公司完成新一轮融资",
    summary: "本轮投资方尚未披露。",
  });

  assert.deepEqual(entities, []);
});
