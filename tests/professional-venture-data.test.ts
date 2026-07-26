import assert from "node:assert/strict";
import test from "node:test";

import { companies } from "../lib/catalog-data";
import {
  getCompanyProfessionalVentureProfile,
  professionalVentureGeneratedAt,
} from "../lib/professional-venture-data";


test("professional venture getter is safe before and after the first source refresh", () => {
  assert.equal(getCompanyProfessionalVentureProfile("missing-company"), undefined);
  assert.ok(typeof professionalVentureGeneratedAt === "string");

  for (const company of companies) {
    const professional = getCompanyProfessionalVentureProfile(company.slug);
    if (!professional) continue;
    const equity = professional.equityProfile;
    if (equity) {
      assert.ok(["cross-verified", "single-source", "pending"].includes(equity.evidenceStatus));
      for (const shareholder of equity.shareholders) {
        assert.ok(shareholder.name);
        if (shareholder.sourceUrl) assert.match(shareholder.sourceUrl, /^https?:\/\//u);
      }
      for (const change of equity.changes) {
        assert.ok(change.item);
        if (change.sourceUrl) assert.match(change.sourceUrl, /^https?:\/\//u);
      }
      for (const investment of equity.externalInvestments) {
        assert.ok(investment.name);
        if (investment.sourceUrl) assert.match(investment.sourceUrl, /^https?:\/\//u);
      }
    }
    const names = professional.professionalSources.map((source) => source.name);
    assert.equal(new Set(names).size, names.length);
    for (const source of professional.professionalSources) {
      assert.match(source.url, /^https?:\/\//u);
      assert.ok(source.detail);
      assert.ok(source.records >= 0);
    }
  }
});
