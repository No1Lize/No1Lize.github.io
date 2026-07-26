from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import sec_structured_disclosures as sec


class SecStructuredDisclosuresTest(unittest.TestCase):
    def test_all_enabled_us_listings_are_registered(self) -> None:
        listings = sec.load_us_listings()
        identities = {(row.catalog_slug, row.ticker) for row in listings}
        expected = {
            ("pony-ai", "PONY"),
            ("weride", "WRD"),
            ("rigetti", "RGTI"),
            ("ionq", "IONQ"),
            ("rocket-lab", "RKLB"),
            ("tempus-ai", "TEM"),
            ("recursion", "RXRX"),
            ("mobileye", "MBLY"),
            ("aurora", "AUR"),
            ("joby", "JOBY"),
        }
        self.assertEqual(identities, expected)

    def test_ticker_index_resolves_zero_padded_cik(self) -> None:
        payload = {
            "0": {"cik_str": 1819399, "ticker": "PONY", "title": "Pony AI Inc."},
            "1": {"cik_str": 1824920, "ticker": "WRD", "title": "WeRide Inc."},
        }
        result = sec.parse_ticker_index(payload)
        self.assertEqual(result["PONY"], "0001819399")
        self.assertEqual(result["WRD"], "0001824920")

    def test_parses_only_relevant_forms_to_original_edgar_urls(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        payload = {
            "filings": {
                "recent": {
                    "form": ["10-K", "8-K", "4", "S-3"],
                    "accessionNumber": [
                        "0001193125-26-000001",
                        "0001193125-26-000002",
                        "0001193125-26-000003",
                        "0001193125-26-000004",
                    ],
                    "filingDate": ["2026-03-01", "2026-02-20", "2026-02-10", "2026-01-15"],
                    "reportDate": ["2025-12-31", "2026-02-20", "", ""],
                    "primaryDocument": ["ionq-20251231.htm", "ionq-8k.htm", "xslF345X05/form4.xml", "ionq-s3.htm"],
                    "primaryDocDescription": ["Annual Report", "Current Report", "Ownership Form", "Registration Statement"],
                }
            }
        }
        events = sec.parse_submissions(
            payload,
            listing,
            "0001824920",
            max_age_days=2000,
            limit=10,
        )
        self.assertEqual([event["form"] for event in events], ["10-K", "8-K", "S-3"])
        self.assertEqual(
            [event["documentType"] for event in events],
            ["定期报告与业绩", "重大经营与风险", "证券发行与融资"],
        )
        for event in events:
            self.assertTrue(sec.is_sec_archive_url(event["source"]["url"]))
            self.assertEqual(event["source"]["name"], "美国证券交易委员会 SEC")
            self.assertFalse(event["fallback"])

    def test_enrichment_preserves_exchange_events_and_adds_sec_profile(self) -> None:
        exchange_listing = base.Listing(
            "cambricon", "寒武纪", "A股", "688256", "半导体"
        )
        exchange_event = {
            "id": "exchange-event",
            "companySlug": "cambricon",
            "companyName": "寒武纪",
            "market": "A股",
            "ticker": "688256",
            "exchange": "上海证券交易所",
            "listingRole": "primary",
            "publishedAt": "2026-01-02",
            "documentType": "定期报告与业绩",
            "title": "2025年年度报告",
            "summary": "寒武纪年度报告",
            "source": {
                "name": "巨潮资讯",
                "url": "https://static.cninfo.com.cn/finalpage/2026-01-02/example.PDF",
                "level": "监管文件",
            },
            "discoveredVia": "cninfo-structured-api",
            "fallback": False,
        }
        snapshot = {
            "schemaVersion": 1,
            "generatedAt": "2026-07-26T00:00:00+00:00",
            "companyCount": 1,
            "eventCount": 1,
            "companies": {
                "cambricon": {
                    "slug": "cambricon",
                    "name": "寒武纪",
                    "updatedAt": "2026-07-26T00:00:00+00:00",
                    "status": "ok",
                    "listings": [
                        {
                            "market": "A股",
                            "ticker": "688256",
                            "exchange": "上海证券交易所",
                            "listingRole": "primary",
                        }
                    ],
                    "events": [exchange_event],
                    "officialEventCount": 1,
                    "fallbackEventCount": 0,
                }
            },
            "sourceStatus": [
                {
                    "id": exchange_listing.source_id,
                    "companySlug": "cambricon",
                    "name": "寒武纪",
                    "market": "A股",
                    "ticker": "688256",
                    "exchange": "上海证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 30,
                    "accepted": 1,
                    "fallback": False,
                }
            ],
            "cninfoStructured": {
                "schemaVersion": 1,
                "provider": "cninfo-structured-api",
                "attemptedListingCount": 1,
                "acceptedEventCount": 1,
            },
        }
        us_listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0001193125-26-000001"],
                    "filingDate": ["2026-03-01"],
                    "reportDate": ["2025-12-31"],
                    "primaryDocument": ["ionq-20251231.htm"],
                    "primaryDocDescription": ["Annual Report"],
                }
            }
        }

        def fetcher(url, timeout, attempts):
            self.assertIn("CIK0001824920.json", url)
            return submissions

        enriched = sec.enrich_snapshot(
            snapshot,
            [us_listing],
            {"IONQ": "0001824920"},
            {"maxAgeDays": 1095, "maxItemsPerListing": 18},
            submissions_fetcher=fetcher,
        )
        self.assertIn("cambricon", enriched["companies"])
        self.assertIn("ionq", enriched["companies"])
        self.assertEqual(enriched["companyCount"], 2)
        self.assertEqual(enriched["secStructured"]["acceptedEventCount"], 1)
        self.assertEqual(
            sec.validate_enrichment(
                enriched,
                [us_listing],
                exchange_listings=[exchange_listing],
                require_events=True,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
