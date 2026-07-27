from __future__ import annotations

import unittest
from datetime import UTC, datetime

from tools import crawl_venture_profiles as crawler
from tools import venture_profile_extraction as extraction


CATALOG = '''
export const companies: Company[] = [
  { slug:"acme-ai", name:"Acme AI", englishName:"Acme Artificial Intelligence", region:"美国", sector:"AI / AGI", stage:"Series B", status:"运营中", founded:"2022", headquarters:"San Francisco", summary:"开发企业智能体。", product:"Acme Agent、Acme API 与模型评测平台。", source:official("Acme AI","https://acme.example/about") },
  { slug:"public-robot", name:"公开机器人", englishName:"Public Robot", region:"中国", sector:"机器人", stage:"已上市", status:"已上市", founded:"2018", headquarters:"上海", summary:"研发工业机器人。", product:"工业机器人与控制系统。", source:official("公开机器人","https://robot.example/") },
];

export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"sample-capital", name:"Sample Capital", englishName:"样本资本", region:"美国", type:"风险投资", stages:"种子至成长期", sectors:["AI","机器人"], source:official("Sample Capital","https://capital.example/") },
];
export type IpoCompany = {};
'''

COMPANY_HTML = '''
<html><head>
<title>About Acme AI</title>
<meta name="description" content="Acme AI was founded in 2022 in San Francisco to build reliable enterprise agents.">
<script type="application/ld+json">{
  "@context":"https://schema.org",
  "@type":"Organization",
  "founder":{"@type":"Person","name":"Ada Example","jobTitle":"Founder and CEO"}
}</script>
</head><body>
<h1>Acme AI</h1>
<p>Our technology combines a multimodal foundation model, retrieval architecture and an evaluation platform for regulated enterprises.</p>
<p>Acme Agent and Acme API are deployed in customer support and research workflows.</p>
<p>Acme AI raised $120 million in a Series B financing led by Sample Capital on 2026-03-10.</p>
<a href="/team">Leadership Team</a>
<a href="/technology">Technology</a>
<a href="https://external.example/story">External story</a>
</body></html>
'''

INSTITUTION_HTML = '''
<html><head>
<title>Sample Capital Portfolio</title>
<meta property="article:published_time" content="2026-03-12T08:00:00Z">
<meta name="description" content="Sample Capital is a venture capital firm partnering with technical founders from seed to growth.">
<script type="application/ld+json">{
  "@type":"Person","name":"Grace Partner","jobTitle":"Managing Partner"
}</script>
</head><body>
<h1>Portfolio and recent investments</h1>
<p>Sample Capital led the Series B investment in Acme AI to expand its enterprise agent platform.</p>
<p>Sample Capital invested in Public Robot before its public listing and continued to support industrial expansion.</p>
<a href="https://capital.example/portfolio/acme-ai">Acme AI</a>
<a href="https://capital.example/portfolio/public-robot">Public Robot</a>
</body></html>
'''


class VentureProfileExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.companies, self.institutions = extraction.parse_catalog(CATALOG)

    def test_catalog_parser_reads_both_entity_kinds(self) -> None:
        self.assertEqual([item.slug for item in self.companies], ["acme-ai", "public-robot"])
        self.assertEqual([item.slug for item in self.institutions], ["sample-capital"])
        self.assertEqual(self.institutions[0].sectors, ("AI", "机器人"))
        self.assertEqual(self.companies[0].source_url, "https://acme.example/about")

    def test_public_page_extracts_json_ld_team_and_classifies_links(self) -> None:
        page = extraction.parse_public_page(
            "https://acme.example/about", COMPANY_HTML, "company"
        )
        self.assertEqual(page.people[0]["name"], "Ada Example")
        self.assertIn("background", page.sections)
        links = extraction.score_discovered_links(
            page, "https://acme.example/about", "company"
        )
        urls = [url for _, url in links]
        self.assertIn("https://acme.example/team", urls)
        self.assertIn("https://acme.example/technology", urls)
        self.assertNotIn("https://external.example/story", urls)

    def test_company_profile_extracts_background_products_team_and_financing(self) -> None:
        page = extraction.parse_public_page(
            "https://acme.example/about", COMPANY_HTML, "company"
        )
        profile = crawler.build_company_profile(
            self.companies[0], [page], [], "2026-07-25T00:00:00+00:00"
        )
        self.assertIn("enterprise agents", profile["background"])
        self.assertIn("multimodal foundation model", profile["technology"])
        self.assertTrue(any("Acme Agent" in item for item in profile["products"]))
        self.assertEqual(profile["team"][0]["name"], "Ada Example")
        self.assertEqual(profile["financing"][0]["amount"], "$120 million")
        self.assertEqual(profile["financing"][0]["round"].casefold(), "series b")

    def test_listed_company_receives_transparent_capital_market_fallback(self) -> None:
        profile = crawler.build_company_profile(
            self.companies[1], [], ["blocked"], "2026-07-25T00:00:00+00:00"
        )
        self.assertEqual(profile["status"], "fallback")
        self.assertEqual(profile["capitalMarkets"][0]["type"], "上市")
        self.assertIn("公开市场", profile["capitalMarkets"][0]["title"])

    def test_institution_profile_extracts_team_recent_investments_and_classics(self) -> None:
        page = extraction.parse_public_page(
            "https://capital.example/portfolio", INSTITUTION_HTML, "institution"
        )
        profile = crawler.build_institution_profile(
            self.institutions[0],
            [page],
            self.companies,
            [],
            "2026-07-25T00:00:00+00:00",
        )
        self.assertEqual(profile["team"][0]["name"], "Grace Partner")
        self.assertEqual(
            {item["companySlug"] for item in profile["portfolio"]},
            {"acme-ai", "public-robot"},
        )
        self.assertTrue(profile["recentInvestments"])
        public_case = next(
            item for item in profile["classicCases"] if item["companySlug"] == "public-robot"
        )
        self.assertIn("公开市场", public_case["analysis"])

    def test_chinese_amount_and_round_are_extracted(self) -> None:
        body = '''<html><head><title>融资动态</title></head><body>
        <p>公司于2026年4月完成10亿元C轮融资，由样本资本领投。</p>
        </body></html>'''
        page = extraction.parse_public_page("https://acme.example/news/c", body, "company")
        events = extraction.extract_capital_events(page and [page], ("公司",))
        self.assertEqual(events[0]["amount"], "10亿元")
        self.assertEqual(events[0]["round"].casefold(), "c轮")

    def test_previous_richer_profile_is_retained(self) -> None:
        current = {
            "slug": "acme-ai",
            "name": "Acme AI",
            "status": "fallback",
            "background": "短。",
            "technology": "",
            "products": [],
            "team": [],
            "financing": [],
            "capitalMarkets": [],
            "sources": [],
            "warnings": ["blocked"],
            "evidenceScore": 5,
        }
        previous = {
            **current,
            "status": "ok",
            "background": "更完整的公司背景与公开证据。",
            "technology": "完整技术信息。",
            "products": ["Acme Agent"],
            "sources": [{"url": "https://acme.example/about"}],
            "evidenceScore": 72,
        }
        merged, retained = crawler.retain_richer_profile(current, previous, "company")
        self.assertTrue(retained)
        self.assertEqual(merged["status"], "retained")
        self.assertEqual(merged["technology"], "完整技术信息。")
        self.assertEqual(merged["products"], ["Acme Agent"])

    def test_quality_gate_requires_complete_catalog_coverage(self) -> None:
        company_profiles = {
            company.slug: {"sources": []} for company in self.companies
        }
        institution_profiles = {
            institution.slug: {"sources": []} for institution in self.institutions
        }
        statuses = [
            {"kind": "company", "slug": company.slug} for company in self.companies
        ] + [
            {"kind": "institution", "slug": institution.slug}
            for institution in self.institutions
        ]
        quality = crawler.evaluate_quality(
            company_profiles,
            institution_profiles,
            len(self.companies),
            len(self.institutions),
            statuses,
        )
        self.assertTrue(quality["passed"])
        broken = crawler.evaluate_quality(
            {"acme-ai": {"sources": []}},
            institution_profiles,
            len(self.companies),
            len(self.institutions),
            statuses,
        )
        self.assertFalse(broken["passed"])


if __name__ == "__main__":
    unittest.main()
