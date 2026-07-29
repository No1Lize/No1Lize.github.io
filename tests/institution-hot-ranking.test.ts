import assert from "node:assert/strict";
import test from "node:test";
import {
  rankInstitutionsByActivity,
  type InstitutionHotArticle,
} from "../lib/institution-hot-ranking";

function article(
  overrides: Partial<InstitutionHotArticle> & Pick<InstitutionHotArticle, "id" | "title">,
): InstitutionHotArticle {
  return {
    id: overrides.id,
    title: overrides.title,
    summary: overrides.summary ?? "机构公开活动测试",
    type: overrides.type ?? "融资",
    region: overrides.region ?? "中国",
    sector: overrides.sector ?? "风险投资",
    company: overrides.company ?? "测试公司",
    companySlug: overrides.companySlug,
    institutions: overrides.institutions,
    publishedAt: overrides.publishedAt ?? "2026-07-28",
    importance: overrides.importance ?? 80,
    qualityScore: overrides.qualityScore ?? 80,
    qualityStatus: overrides.qualityStatus,
    relatedSources: overrides.relatedSources,
    duplicateCount: overrides.duplicateCount,
    eventClusterId: overrides.eventClusterId,
    source: overrides.source ?? {
      name: "测试机构官网",
      url: `https://example.com/${overrides.id}`,
      level: "官方披露",
    },
  };
}

const AS_OF = Date.parse("2026-07-29T12:00:00Z");

test("recent direct official activity outranks stale media activity", () => {
  const ranked = rankInstitutionsByActivity(
    [
      article({
        id: "idg-recent",
        title: "IDG资本完成新一期投资",
        institutions: ["IDG 资本"],
        publishedAt: "2026-07-28",
        source: {
          name: "IDG资本",
          url: "https://example.com/idg-recent",
          level: "官方披露",
        },
      }),
      article({
        id: "sequoia-old",
        title: "Sequoia Capital portfolio update",
        institutions: ["Sequoia Capital"],
        publishedAt: "2025-12-01",
        importance: 100,
        qualityScore: 100,
        source: {
          name: "Old media",
          url: "https://example.com/sequoia-old",
          level: "媒体报道",
        },
      }),
    ],
    new Map(),
    AS_OF,
  );

  assert.equal(ranked[0]?.relation.institution.name, "IDG资本");
  assert.ok(ranked[0].crawlerScore > ranked[1].crawlerScore);
});

test("direct institution evidence outweighs portfolio-only company activity", () => {
  const ranked = rankInstitutionsByActivity(
    [
      article({
        id: "idg-direct",
        title: "IDG资本参与新融资",
        institutions: ["IDG资本"],
      }),
      article({
        id: "harvey-product",
        title: "Harvey 发布新产品",
        type: "产品发布",
        company: "Harvey",
        companySlug: "harvey",
        institutions: [],
      }),
    ],
    new Map(),
    AS_OF,
  );

  const idg = ranked.find((item) => item.relation.institution.name === "IDG资本");
  const sequoia = ranked.find(
    (item) => item.relation.institution.name === "Sequoia Capital",
  );
  assert.ok(idg);
  assert.ok(sequoia);
  assert.ok(idg.score > sequoia.score);
  assert.equal(idg.directArticleCount, 1);
  assert.equal(sequoia.portfolioArticleCount, 1);
});

test("duplicate crawler records in the same event cluster count once", () => {
  const ranked = rankInstitutionsByActivity(
    [
      article({
        id: "idg-cluster-a",
        title: "IDG资本参与A轮融资",
        institutions: ["IDG资本"],
        eventClusterId: "cluster-idg-a",
      }),
      article({
        id: "idg-cluster-b",
        title: "同一融资事件转载",
        institutions: ["IDG 资本"],
        eventClusterId: "cluster-idg-a",
        source: {
          name: "转载媒体",
          url: "https://example.com/idg-cluster-b",
          level: "媒体报道",
        },
      }),
    ],
    new Map(),
    AS_OF,
  );

  const idg = ranked.find((item) => item.relation.institution.name === "IDG资本");
  assert.ok(idg);
  assert.equal(idg.articleCount, 1);
  assert.equal(idg.directArticleCount, 1);
  assert.equal(idg.sourceCount, 1);
});

test("local attention only adjusts the crawler ranking instead of replacing it", () => {
  const idgUrl = "https://example.com/idg-strong";
  const sequoiaUrl = "https://example.com/sequoia-weaker";
  const articles = [
    article({
      id: "idg-strong",
      title: "IDG资本产业投资",
      type: "产业投资",
      institutions: ["IDG资本"],
      importance: 95,
      qualityScore: 95,
      source: { name: "IDG资本", url: idgUrl, level: "官方披露" },
    }),
    article({
      id: "sequoia-weaker",
      title: "Sequoia Capital media mention",
      type: "公司动态",
      institutions: ["Sequoia Capital"],
      importance: 55,
      qualityScore: 55,
      source: { name: "Media", url: sequoiaUrl, level: "媒体报道" },
    }),
  ];
  const engagement = new Map([
    [sequoiaUrl, { opens: 100, favorite: true, shares: 20 }],
  ]);

  const ranked = rankInstitutionsByActivity(articles, engagement, AS_OF);
  const idg = ranked.find((item) => item.relation.institution.name === "IDG资本");
  const sequoia = ranked.find(
    (item) => item.relation.institution.name === "Sequoia Capital",
  );
  assert.ok(idg);
  assert.ok(sequoia);
  assert.equal(idg.crawlerScore, 100);
  assert.equal(sequoia.attentionScore, 100);
  assert.ok(idg.score > sequoia.score);
});
