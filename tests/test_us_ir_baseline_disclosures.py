from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import sec_structured_disclosures as sec
from tools import us_ir_baseline_disclosures as baselines
from tools import us_ir_sec_disclosures as ir


class UsIrBaselineDisclosuresTest(unittest.TestCase):
    def test_every_us_listing_has_one_verified_official_baseline(self) -> None:
        listings = sec.load_us_listings()
        config = base.load_config()
        registry = baselines.load_baselines(listings, config)
        sources = ir.load_ir_sources(listings, config)
        self.assertEqual(set(registry), {listing.catalog_slug for listing in listings})
        self.assertEqual(len(registry), 10)
        for listing in listings:
            row = registry[listing.catalog_slug]
            source = sources[listing.catalog_slug]
            self.assertIn(row["form"], sec.FORM_TYPES)
            self.assertEqual(ir.normalized_host(row["url"]), source.host)
            self.assertRegex(row["filingDate"], r"^20\d{2}-\d{2}-\d{2}$")

    def test_baseline_event_keeps_original_official_ir_url(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        source = ir.IRSource(
            "ionq",
            "IonQ Investor Relations",
            "https://investors.ionq.com/financials/sec-filings/",
            "investors.ionq.com",
            "q4",
        )
        row = {
            "form": "10-Q",
            "filingDate": "2026-05-07",
            "documentDate": "2026-03-31",
            "description": "Quarterly Report",
            "url": "https://investors.ionq.com/financials/sec-filings/sec-filings-details/default.aspx?FilingId=19421418",
        }
        event = baselines.baseline_event(listing, source, row)
        self.assertEqual(event["documentType"], "定期报告与业绩")
        self.assertEqual(event["source"]["url"], row["url"])
        self.assertEqual(event["source"]["name"], source.name)
        self.assertTrue(event["verifiedBaseline"])
        self.assertFalse(event["fallback"])

    def test_baseline_merge_survives_live_discovery_failure(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        source = ir.IRSource(
            "ionq",
            "IonQ Investor Relations",
            "https://investors.ionq.com/financials/sec-filings/",
            "investors.ionq.com",
            "q4",
        )
        original = baselines._ORIGINAL_CRAWL_SOURCE
        baseline_registry = baselines._BASELINES
        try:
            baselines._BASELINES = {
                "ionq": {
                    "form": "10-Q",
                    "filingDate": "2026-05-07",
                    "documentDate": "2026-03-31",
                    "description": "Quarterly Report",
                    "url": "https://investors.ionq.com/financials/sec-filings/sec-filings-details/default.aspx?FilingId=19421418",
                }
            }
            baselines._ORIGINAL_CRAWL_SOURCE = lambda listing, source, settings: (
                [],
                {
                    "id": "us-ir-disclosure-ionq-ionq",
                    "companySlug": "ionq",
                    "accepted": 0,
                    "status": "error",
                    "errors": ["timeout"],
                },
            )
            rows, status = baselines.crawl_source(
                listing,
                source,
                {"maxItemsPerListing": 18},
            )
        finally:
            baselines._ORIGINAL_CRAWL_SOURCE = original
            baselines._BASELINES = baseline_registry
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["verifiedBaseline"])
        self.assertEqual(status["accepted"], 1)
        self.assertEqual(status["baselineAccepted"], 1)
        self.assertEqual(status["status"], "ok")


if __name__ == "__main__":
    unittest.main()
