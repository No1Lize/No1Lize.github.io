from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import sec_configured_disclosures as configured
from tools import sec_structured_disclosures as sec


class SecConfiguredDisclosuresTest(unittest.TestCase):
    def test_all_current_us_listings_have_configured_ciks(self) -> None:
        listings = sec.load_us_listings()
        config = base.load_config()
        resolved, missing = configured.configured_ticker_ciks(listings, config)
        self.assertEqual(missing, [])
        self.assertEqual(len(resolved), len(listings))
        self.assertEqual(resolved["IONQ"], "0001824920")
        self.assertEqual(resolved["RKLB"], "0001819994")
        self.assertTrue(all(len(cik) == 10 and cik.isdigit() for cik in resolved.values()))

    def test_complete_registry_skips_blocked_sec_ticker_index(self) -> None:
        listings = [sec.USListing("ionq", "IonQ", "IONQ", "量子计算")]
        config = {
            "settings": {"requestTimeout": 18, "requestAttempts": 2},
            "secCiks": {"ionq": "1824920"},
        }

        def blocked_fetcher(*args, **kwargs):
            raise AssertionError("dynamic SEC ticker index must not be requested")

        resolved, metadata = configured.resolve_ticker_ciks(
            listings,
            config,
            index_fetcher=blocked_fetcher,
        )
        self.assertEqual(resolved, {"IONQ": "0001824920"})
        self.assertEqual(metadata["configuredListingCount"], 1)
        self.assertFalse(metadata["dynamicLookupAttempted"])
        self.assertEqual(metadata["dynamicLookupErrors"], [])

    def test_missing_future_listing_can_use_dynamic_lookup(self) -> None:
        listings = [sec.USListing("future-company", "Future Company", "FUTR", "AI / AGI")]
        config = {
            "settings": {"requestTimeout": 18, "requestAttempts": 2},
            "secCiks": {},
        }

        def index_fetcher(url, timeout, attempts):
            self.assertEqual(url, sec.TICKER_INDEX_URL)
            return {
                "0": {
                    "cik_str": 1234567,
                    "ticker": "FUTR",
                    "title": "Future Company",
                }
            }

        resolved, metadata = configured.resolve_ticker_ciks(
            listings,
            config,
            index_fetcher=index_fetcher,
        )
        self.assertEqual(resolved, {"FUTR": "0001234567"})
        self.assertTrue(metadata["dynamicLookupAttempted"])
        self.assertEqual(metadata["dynamicResolvedCount"], 1)

    def test_registry_metadata_marks_configured_cik_source(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        snapshot = {
            "sourceStatus": [
                {
                    "id": listing.source_id,
                    "accepted": 1,
                    "cikResolved": True,
                }
            ],
            "secStructured": {
                "schemaVersion": 1,
                "provider": sec.PROVIDER,
                "attemptedListingCount": 1,
                "acceptedEventCount": 1,
            },
        }
        result = configured.apply_registry_metadata(
            snapshot,
            [listing],
            {"IONQ": "0001824920"},
            {
                "configuredListingCount": 1,
                "dynamicLookupAttempted": False,
                "dynamicResolvedCount": 0,
                "dynamicLookupErrors": [],
            },
        )
        self.assertEqual(
            result["sourceStatus"][0]["cikSource"],
            "configured-official-registry",
        )
        self.assertEqual(
            result["secStructured"]["cikRegistry"]["configuredListingCount"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
