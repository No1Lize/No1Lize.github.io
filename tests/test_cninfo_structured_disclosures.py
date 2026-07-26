from __future__ import annotations

import unittest
from datetime import date

from tools import cninfo_structured_disclosures as cninfo
from tools import crawl_listed_company_disclosures as base


class CninfoStructuredDisclosuresTest(unittest.TestCase):
    def setUp(self) -> None:
        self.listing = base.Listing(
            "catl",
            "宁德时代",
            "A股",
            "300750",
            "新能源",
        )

    def test_stock_registry_resolves_cninfo_org_ids(self) -> None:
        result = cninfo.parse_org_ids(
            {
                "stockList": [
                    {"code": "300750", "orgId": "9900023766"},
                    {"code": "bad", "orgId": "ignored"},
                ]
            }
        )
        self.assertEqual(result, {"300750": "9900023766"})

    def test_query_payload_uses_exchange_column_and_bounded_dates(self) -> None:
        payload = cninfo.query_payload(
            self.listing,
            "9900023766",
            page_num=1,
            page_size=30,
            start_date=date(2025, 7, 26),
            end_date=date(2026, 7, 26),
        )
        self.assertEqual(payload["column"], "szse")
        self.assertEqual(payload["stock"], "300750,9900023766")
        self.assertEqual(payload["seDate"], "2025-07-26~2026-07-26")
        self.assertEqual(payload["tabName"], "fulltext")

    def test_structured_rows_resolve_original_cninfo_documents(self) -> None:
        candidates = cninfo.parse_announcements(
            {
                "announcements": [
                    {
                        "secCode": "300750",
                        "secName": "宁德时代",
                        "announcementTitle": "2025年年度报告",
                        "announcementTime": 1774396800000,
                        "announcementId": "1212345678",
                        "adjunctType": "PDF",
                        "adjunctUrl": "finalpage/2026-03-25/1212345678.PDF",
                    },
                    {
                        "secCode": "300676",
                        "secName": "华大基因",
                        "announcementTitle": "其他公司的年度报告",
                        "announcementTime": 1774396800000,
                        "adjunctUrl": "finalpage/2026-03-25/other.PDF",
                    },
                ]
            },
            self.listing,
        )
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.provider, "cninfo-structured-api")
        self.assertEqual(candidate.published_at, "2026-03-25")
        self.assertEqual(
            candidate.url,
            "https://static.cninfo.com.cn/finalpage/2026-03-25/1212345678.PDF",
        )
        event = base.to_event(self.listing, candidate, fallback=False)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["documentType"], "定期报告与业绩")
        self.assertEqual(event["source"]["name"], "巨潮资讯")
        self.assertEqual(event["source"]["level"], "监管文件")

    def test_enrichment_merges_a_share_events_without_removing_hk_events(self) -> None:
        hk_listing = base.Listing(
            "catl",
            "宁德时代",
            "港股",
            "03750",
            "新能源",
            "secondary",
        )
        existing_hk = {
            "id": "hk-event",
            "companySlug": "catl",
            "companyName": "宁德时代",
            "market": "港股",
            "ticker": "03750",
            "exchange": "香港交易所",
            "listingRole": "secondary",
            "publishedAt": "2026-07-24",
            "documentType": "证券发行与融资",
            "title": "HKEX placing announcement",
            "summary": "HKEX disclosure",
            "source": {
                "name": "香港交易所披露易",
                "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0724/example.pdf",
                "level": "监管文件",
            },
            "discoveredVia": "official-direct-index",
            "fallback": False,
        }
        incoming_a = {
            "id": "a-event",
            "companySlug": "catl",
            "companyName": "宁德时代",
            "market": "A股",
            "ticker": "300750",
            "exchange": "深圳证券交易所",
            "listingRole": "primary",
            "publishedAt": "2026-04-15",
            "documentType": "定期报告与业绩",
            "title": "2026年一季度报告",
            "summary": "巨潮资讯结构化公告",
            "source": {
                "name": "巨潮资讯",
                "url": "https://static.cninfo.com.cn/finalpage/2026-04-15/a.PDF",
                "level": "监管文件",
            },
            "discoveredVia": "cninfo-structured-api",
            "fallback": False,
        }
        snapshot = {
            "schemaVersion": 1,
            "companies": {
                "catl": {
                    "slug": "catl",
                    "name": "宁德时代",
                    "events": [existing_hk],
                    "listings": [],
                }
            },
            "sourceStatus": [
                {
                    "id": self.listing.source_id,
                    "companySlug": "catl",
                    "name": "宁德时代",
                    "market": "A股",
                    "ticker": "300750",
                    "exchange": "深圳证券交易所",
                    "provider": "official",
                    "status": "error",
                    "scanned": 72,
                    "accepted": 0,
                    "fallback": False,
                    "errors": [],
                },
                {
                    "id": hk_listing.source_id,
                    "companySlug": "catl",
                    "name": "宁德时代",
                    "market": "港股",
                    "ticker": "03750",
                    "exchange": "香港交易所",
                    "provider": "official",
                    "status": "ok",
                    "scanned": 10,
                    "accepted": 1,
                    "fallback": False,
                    "errors": [],
                },
            ],
        }

        def query_fn(listing, org_id, settings):
            self.assertEqual(listing.ticker, "300750")
            self.assertEqual(org_id, "9900023766")
            return [incoming_a], {
                "attempted": True,
                "provider": "cninfo-structured-api",
                "orgIdResolved": True,
                "scanned": 30,
                "accepted": 1,
                "errors": [],
            }

        enriched = cninfo.enrich_snapshot(
            snapshot,
            [self.listing, hk_listing],
            {"300750": "9900023766"},
            {"maxItemsPerListing": 18},
            query_fn=query_fn,
        )
        events = enriched["companies"]["catl"]["events"]
        self.assertEqual({_event["id"] for _event in events}, {"hk-event", "a-event"})
        status = next(
            row for row in enriched["sourceStatus"] if row["id"] == self.listing.source_id
        )
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["structuredAccepted"], 1)
        self.assertEqual(enriched["cninfoStructured"]["acceptedEventCount"], 1)
        self.assertEqual(
            cninfo.validate_enrichment(
                enriched,
                [self.listing, hk_listing],
                require_events=True,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
