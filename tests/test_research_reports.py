import unittest

from tools import crawl_research_reports as reports


class ResearchReportCrawlerTests(unittest.TestCase):
    def test_parse_jsonp(self):
        payload = reports.parse_json_or_jsonp(b'callback({"data":[{"infoCode":"AP1"}]});')
        self.assertEqual(payload["data"][0]["infoCode"], "AP1")

    def test_pdf_validation_rejects_html(self):
        with self.assertRaises(ValueError):
            reports.validate_pdf(b"<html>login required</html>" * 100)

    def test_pdf_validation_accepts_pdf_markers(self):
        body = b"%PDF-1.7\n" + (b"0" * 2048) + b"\n%%EOF"
        reports.validate_pdf(body)

    def test_only_enabled_a_share_companies_are_supported(self):
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
        self.assertIsNone(
            reports.normalize_company(
                {
                    "id": "catalog-ionq",
                    "name": "IonQ",
                    "ticker": "IONQ",
                    "market": "美股",
                    "enabled": True,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
