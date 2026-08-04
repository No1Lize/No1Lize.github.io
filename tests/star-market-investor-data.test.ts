import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeStarInvestorName,
  resolveStarInvestorInstitution,
  starInvestorInstitutionHref,
  type StarMarketInvestorRecord,
} from "../lib/star-market-investor-data";

test("STAR investor names normalize punctuation and legal-form spacing", () => {
  assert.equal(
    normalizeStarInvestorName("IDG 资本（中国）"),
    normalizeStarInvestorName("IDG资本(中国)"),
  );
  assert.equal(
    normalizeStarInvestorName("北京示例基金（有限合伙）"),
    "北京示例基金有限合伙",
  );
});

test("known prospectus investor resolves to the existing institution directory", () => {
  const institution = resolveStarInvestorInstitution({
    name: "IDG资本",
    normalizedName: normalizeStarInvestorName("IDG资本"),
  });
  assert.ok(institution);
  assert.equal(institution.name, "IDG资本");
});

test("unmatched prospectus investor opens a focused institution-directory search", () => {
  const record = {
    company: {
      slug: "sample",
      name: "示例科技",
      ticker: "688001",
      exchange: "上海证券交易所科创板",
      sector: "半导体",
      updatedAt: "2026-07-29T00:00:00Z",
      status: "ok",
      prospectus: {
        title: "示例科技招股说明书",
        url: "https://static.cninfo.com.cn/sample.pdf",
        publishedAt: "2020-01-01",
        announcementId: "sample",
        pageCount: 100,
        textPageCount: 100,
        sha256: "a".repeat(64),
        provider: "cninfo-prospectus",
      },
      institutionalInvestorCount: 1,
      naturalPersonContactsPublished: false,
      investors: [],
      errors: [],
    },
    investor: {
      id: "star-investor-sample",
      name: "北京未收录产业投资有限公司",
      normalizedName: normalizeStarInvestorName("北京未收录产业投资有限公司"),
      institutional: true,
      investorType: "产业投资者",
      sourcePage: 88,
      sourceSection: "发行前股本结构",
      evidence: "公开招股说明书股东表",
      contactStatus: "not-disclosed-in-prospectus",
      reviewStatus: "needs_review",
      reviewReasons: ["awaiting-human-review"],
    },
  } as StarMarketInvestorRecord;

  assert.equal(
    starInvestorInstitutionHref(record),
    `/institutions?institution=${encodeURIComponent(record.investor.name)}`,
  );
});
