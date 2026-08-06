import assert from "node:assert/strict";
import test from "node:test";

import {
  companies,
  institutionCatalog,
  ipoCompanies,
  people,
  reports,
} from "../lib/catalog-data";
import { intelligenceEvents, sectors } from "../lib/intelligence-data";

test("production research and evidence catalogs meet coverage floors", () => {
  assert.ok(companies.length >= 50);
  assert.ok(institutionCatalog.length >= 20);
  assert.ok(
    ipoCompanies.length >= 15,
    "listed-company evidence remains available to core company lifecycle research",
  );
  assert.equal(sectors.length, 10);
  assert.ok(people.length >= 6);
  assert.ok(reports.length >= 5);
});

test("every production entity and evidence record has a real source URL", () => {
  const urls = [
    ...companies.map((item) => item.source.url),
    ...institutionCatalog.map((item) => item.source.url),
    ...ipoCompanies.map((item) => item.source.url),
    ...intelligenceEvents.map((item) => item.source.url),
  ];
  assert.ok(urls.every((url) => /^https?:\/\//.test(url)));
});

test("person pages expose at least five traceable materials", () => {
  assert.ok(people.every((person) => person.materials.length >= 5));
  assert.ok(
    people.flatMap((person) => person.materials).every((material) => /^https?:\/\//.test(material.url)),
  );
});

test("slugs are unique within each public route collection", () => {
  for (const collection of [companies, institutionCatalog, people, reports, sectors]) {
    const slugs = collection.map((item) => item.slug);
    assert.equal(new Set(slugs).size, slugs.length);
  }
});

test("listed-company evidence identities remain unique without public IPO routes", () => {
  const slugs = ipoCompanies.map((item) => item.slug);
  assert.equal(new Set(slugs).size, slugs.length);
});

test("every linked event company has a generated company route", () => {
  const companySlugs = new Set(companies.map((company) => company.slug));
  for (const event of intelligenceEvents) {
    if (event.companySlug) {
      assert.ok(
        companySlugs.has(event.companySlug),
        `missing company route for ${event.companySlug}`,
      );
    }
  }
});
