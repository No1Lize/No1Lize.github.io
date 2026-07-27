import json
import unittest

from tools import crawl_research_reports as reports
from tools import research_report_adapters as adapters


class ResearchReportCrawlerTests(unittest.TestCase):
    def test_parse_jsonp(self):
        payload = reports.parse_json_or_jsonp(
            b'callback({"data":[{"infoCode":"AP1"}]});'
        )
        self.assertEqual(payload["data"][0]["infoCode"], "AP1")

    def test_pdf_validation_rejects_html(self):
        with self.assertRaises(ValueError):
            reports.validate_pdf(b"<html>login required</html>" * 100)

    def test_pdf_validation_accepts_pdf_markers(self):
        body = b"%PDF-1.7\n" + (b"0" * 2048) + b"\n%%EOF"
        reports.validate_pdf(body)

    def test_normalizes_a_share_company(self):
        company = reports.normalize_company(
            {
                "id": "catalog-cambricon",
                "catalogSlug": "cambricon",
                "name": "寒武纪",
                "ticker": "688256.SH",
                "market": "A股",
                "sector": "半导体",
                "enabled": True,
            }
        )
        self.assertEqual(company["ticker"], "688256")
        self.assertEqual(company["slug"], "cambricon")
        self.assertEqual(company["market"], "A股")

    def test_normalizes_hong_kong_ticker_variants(self):
        for ticker in ["700", "0700", "00700", "0700.HK", "HK0700"]:
            with self.subTest(ticker=ticker):
                company = reports.normalize_company(
                    {
                        "id": "listed-hk-00700",
                        "name": "腾讯控股",
                        "ticker": ticker,
                        "market": "港股",
                        "sector": "AI / AGI",
                        "enabled": True,
                    }
                )
                self.assertIsNotNone(company)
                self.assertEqual(company["ticker"], "00700")

    def test_normalizes_us_ticker(self):
        company = reports.normalize_company(
            {
                "id": "listed-us-aapl",
                "name": "Apple",
                "ticker": "aapl",
                "market": "美股",
                "sector": "消费电子",
                "enabled": True,
            }
        )
        self.assertEqual(company["ticker"], "AAPL")
        self.assertEqual(company["market"], "美股")

    def test_disabled_and_invalid_companies_are_rejected(self):
        self.assertIsNone(
            reports.normalize_company(
                {
                    "id": "catalog-ionq",
                    "name": "IonQ",
                    "ticker": "IONQ",
                    "market": "美股",
                    "enabled": False,
                }
            )
        )
        self.assertIsNone(
            reports.normalize_company(
                {
                    "id": "bad",
                    "name": "Bad",
                    "ticker": "not a ticker!",
                    "market": "美股",
                    "enabled": True,
                }
            )
        )

    def test_research_candidate_requires_company_and_pdf_semantics(self):
        company = {
            "id": "catalog-ionq",
            "slug": "ionq",
            "name": "IonQ",
            "ticker": "IONQ",
            "market": "美股",
            "sector": "量子计算",
        }
        valid = {
            "title": "IonQ investor presentation 2026 PDF",
            "description": "IONQ investor materials",
            "url": "https://investors.example.com/ionq-presentation.pdf",
        }
        unrelated = {
            "title": "Another company annual report PDF",
            "description": "unrelated",
            "url": "https://example.com/other.pdf",
        }
        login_page = {
            "title": "IonQ equity research PDF",
            "description": "IONQ",
            "url": "https://www.scribd.com/document/123",
        }
        self.assertTrue(reports.is_research_candidate(valid, company, ""))
        self.assertFalse(reports.is_research_candidate(unrelated, company, ""))
        self.assertFalse(reports.is_research_candidate(login_page, company, ""))

    def test_company_domain_candidate_still_requires_research_keyword(self):
        company = {
            "id": "catalog-joby",
            "slug": "joby",
            "name": "Joby Aviation",
            "ticker": "JOBY",
            "market": "美股",
            "sector": "商业航天",
        }
        presentation = {
            "title": "Investor presentation",
            "description": "Company update",
            "url": "https://investors.jobyaviation.com/static-files/deck.pdf",
        }
        random_pdf = {
            "title": "Privacy policy",
            "description": "Legal",
            "url": "https://investors.jobyaviation.com/privacy.pdf",
        }
        website = "https://investors.jobyaviation.com/"
        self.assertTrue(
            reports.is_research_candidate(presentation, company, website)
        )
        self.assertFalse(reports.is_research_candidate(random_pdf, company, website))

    def test_report_classification(self):
        self.assertEqual(reports.classify_report("2025 Annual Report"), "年度报告")
        self.assertEqual(reports.classify_report("公司招股书"), "招股书")
        self.assertEqual(
            reports.classify_report("Q2 Investor Presentation"), "投资者演示"
        )
        self.assertEqual(reports.classify_report("半导体行业研究"), "行业研报")
        self.assertEqual(reports.classify_report("公司深度研究"), "个股研报")

    def test_extracts_hkex_annual_report_pdf(self):
        company = {
            "slug": "xtalpi",
            "name": "晶泰科技",
            "ticker": "02228",
            "market": "港股",
            "sector": "生物科技",
        }
        html = b'''
        <html><body>
          <a href="/listedco/listconews/sehk/2026/0417/annual-report-2025.pdf">
            Annual Report 2025
          </a>
        </body></html>
        '''
        items = adapters.extract_pdf_links(
            "https://www1.hkexnews.hk/search/titlesearch.xhtml?stockId=1",
            html,
            company,
            "https://www.xtalpi.com/",
        )
        self.assertEqual(len(items), 1)
        self.assertIn("annual-report-2025.pdf", items[0]["url"])

    def test_extracts_company_ir_presentation_pdf(self):
        company = {
            "slug": "ionq",
            "name": "IonQ",
            "ticker": "IONQ",
            "market": "美股",
            "sector": "量子计算",
        }
        html = b'''
        <html><body>
          <a href="/static-files/ionq-q1-2026-investor-presentation.pdf">
            First Quarter 2026 Earnings Presentation
          </a>
        </body></html>
        '''
        items = adapters.extract_pdf_links(
            "https://investors.ionq.com/events-and-presentations/",
            html,
            company,
            "https://ionq.com/",
        )
        self.assertEqual(len(items), 1)
        self.assertIn("investor-presentation.pdf", items[0]["url"])

    def test_discovers_sec_ars_pdf(self):
        company = {
            "slug": "ionq",
            "name": "IonQ",
            "ticker": "IONQ",
            "market": "美股",
            "sector": "量子计算",
        }
        payload = {
            "filings": {
                "recent": {
                    "form": ["ARS", "10-K"],
                    "primaryDocument": ["ionq-2025-annual-report.pdf", "ionq.htm"],
                    "accessionNumber": ["0001193125-26-197584", "0001193125-26-071562"],
                    "filingDate": ["2026-04-30", "2026-02-25"],
                    "primaryDocDescription": ["2025 Annual Report", "10-K"],
                }
            }
        }

        def fake_request(url, **kwargs):
            return json.dumps(payload).encode("utf-8")

        items = adapters.discover_sec_candidates(
            company,
            "0001824920",
            fake_request,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "2025 Annual Report")
        self.assertTrue(items[0]["url"].endswith("ionq-2025-annual-report.pdf"))


if __name__ == "__main__":
    unittest.main()
