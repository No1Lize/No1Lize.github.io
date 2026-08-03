import assert from "node:assert/strict";
import test from "node:test";

import { companies } from "../lib/catalog-data";
import {
  companyEntities,
  companyEntityBySlug,
  resolveArticleCompanyEntities,
} from "../lib/company-entity-registry";

test("official registry covers every formal company route", () => {
  const registrySlugs = new Set(companyEntities.map((entity) => entity.slug));
  const missing = companies
    .map((company) => company.slug)
    .filter((slug) => !registrySlugs.has(slug));
  assert.deepEqual(missing, []);
});

test("explicit company slugs resolve against the official registry", () => {
  const entities = resolveArticleCompanyEntities({ companySlug: "openai" });
  assert.deepEqual(entities.map((entity) => entity.slug), ["openai"]);
});

test("official company domains resolve without text matching", () => {
  const entities = resolveArticleCompanyEntities({
    source: { url: "https://openai.com/news/example" },
  });
  assert.deepEqual(entities.map((entity) => entity.slug), ["openai"]);
});

test("specific brand domains outrank a shared parent company domain", () => {
  const entities = resolveArticleCompanyEntities({
    source: { url: "https://seed.bytedance.com/zh/technology/example" },
  });
  assert.deepEqual(entities.map((entity) => entity.slug), ["doubao"]);
});

test("exact structured company names resolve", () => {
  const entities = resolveArticleCompanyEntities({ company: "ByteDance" });
  assert.deepEqual(entities.map((entity) => entity.slug), ["bytedance"]);
});

test("free text alone does not publish a company association", () => {
  const entities = resolveArticleCompanyEntities({
    company: "科技产业",
    source: { url: "https://example.com/openai-story" },
  });
  assert.deepEqual(entities, []);
});

test("low confidence stored matches do not enter the company channel", () => {
  const entities = resolveArticleCompanyEntities({
    companyMatches: [{ slug: "openai", method: "text-candidate", confidence: 0.65 }],
  });
  assert.deepEqual(entities, []);
});

test("single stored match remains supported", () => {
  const entities = resolveArticleCompanyEntities({
    companyMatch: { slug: "openai", method: "official-domain", confidence: 0.99 },
  });
  assert.deepEqual(entities.map((entity) => entity.slug), ["openai"]);
});

test("registry exposes the canonical company name", () => {
  assert.equal(companyEntityBySlug("openai")?.name, "OpenAI");
});
