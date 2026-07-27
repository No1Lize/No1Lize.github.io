from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import sec_structured_disclosures as sec
from tools import us_ir_search_disclosures as search
from tools import us_ir_sec_disclosures as ir


class UsIrSearchDisclosuresTest(unittest.TestCase):
    def setUp(self) -> None:
        self.listing = sec.USListing("tempus-ai", "Tempus AI", "TEM", "生物科技")
        self.source = ir.IRSource(
            "tempus-ai",
            "Tempus AI Investor Relations",
            "https://investors.tempus.com/financials/sec-filings",
            "investors.tempus.com",
            "q4",
        )

    def test_query_is_restricted_to_the_official_ir_host(self) -> None:
        query = search.search_query(self.listing, self.source)
        self.assertIn("site:investors.tempus.com", query)
        self.assertIn('"10-Q"', query)
        self.assertIn('"Tempus AI"', query)

    def test_detail_page_produces_verified_official_event(self) -> None:
        candidate = base.Candidate(
            "0001193125-26-206356 | 10-Q | Tempus AI",
            "https://investors.tempus.com/sec-filings/sec-filing/10-q/0001193125-26-206356",
            "Quarterly report",
            "",
            search.PROVIDER,
        )
        body = """
        <main>
          <h1>SEC Filing Details</h1>
          <div>Form 10-Q</div>
          <div>Filing Date May 5, 2026</div>
          <div>Document Date Mar 31, 2026</div>
          <div>Form Description Quarterly report which provides a continuing view of a company's financial position</div>
          <div>Filing Group Quarterly Filings</div>
          <div>Company Tempus AI</div>
        </main>
        """
        event = search.detail_event(self.listing, self.source, candidate, body)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["form"], "10-Q")
        self.assertEqual(event["publishedAt"], "2026-05-05")
        self.assertEqual(event["documentType"], "定期报告与业绩")
        self.assertEqual(event["source"]["name"], "Tempus AI Investor Relations")
        self.assertEqual(ir.normalized_host(event["source"]["url"]), self.source.host)

    def test_detail_page_rejects_non_official_host(self) -> None:
        candidate = base.Candidate(
            "10-Q | Tempus AI",
            "https://example.com/fake-filing",
            "Quarterly report",
            "2026-05-05",
            search.PROVIDER,
        )
        self.assertIsNone(
            search.detail_event(
                self.listing,
                self.source,
                candidate,
                "Form 10-Q Filing Date May 5, 2026",
            )
        )


if __name__ == "__main__":
    unittest.main()
