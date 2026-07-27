from __future__ import annotations

import unittest

from tools import sec_structured_disclosures as sec
from tools import us_ir_sec_disclosures as ir


class UsIrSecDisclosuresTest(unittest.TestCase):
    def test_every_us_listing_has_an_official_ir_source(self) -> None:
        listings = sec.load_us_listings()
        sources = ir.load_ir_sources(listings)
        self.assertEqual(set(sources), {listing.catalog_slug for listing in listings})
        self.assertEqual(len(sources), 10)
        for source in sources.values():
            self.assertEqual(ir.normalized_host(source.url), source.host)
            self.assertIn(source.layout, {"q4", "corporate-ir"})

    def test_first_page_is_canonical_and_later_pages_are_bounded(self) -> None:
        source = ir.IRSource(
            "ionq",
            "IonQ Investor Relations",
            "https://investors.ionq.com/financials/sec-filings/",
            "investors.ionq.com",
            "q4",
        )
        self.assertEqual(ir.page_url(source, 0), source.url)
        url = ir.page_url(source, 2)
        self.assertIn("page=2", url)
        self.assertIn("items_per_page=100", url)
        self.assertIn("mobile=1", url)

    def test_parses_material_filing_rows_and_official_links(self) -> None:
        source = ir.IRSource(
            "ionq",
            "IonQ Investor Relations",
            "https://investors.ionq.com/financials/sec-filings/",
            "investors.ionq.com",
            "q4",
        )
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        body = """
        <table>
          <tr>
            <td>May 7, 2026</td>
            <td>10-Q</td>
            <td>Quarterly Report</td>
            <td><a href="/sec-filings/sec-filing/10-q/0001193125-26-000001">View HTML</a></td>
          </tr>
          <tr>
            <td>May 6, 2026</td>
            <td>8-K</td>
            <td>Current report filing</td>
            <td><a href="/sec-filings/sec-filing/8-k/0001193125-26-000002">View HTML</a></td>
          </tr>
          <tr>
            <td>May 5, 2026</td>
            <td>4</td>
            <td>Statement of Changes in Beneficial Ownership</td>
            <td><a href="/sec-filings/sec-filing/4/0001193125-26-000003">View HTML</a></td>
          </tr>
        </table>
        """
        events, scanned = ir.parse_page(body, source, listing)
        self.assertEqual(scanned, 3)
        self.assertEqual([event["form"] for event in events], ["10-Q", "8-K"])
        self.assertEqual(
            [event["documentType"] for event in events],
            ["定期报告与业绩", "重大经营与风险"],
        )
        for event in events:
            self.assertEqual(
                ir.normalized_host(event["source"]["url"]),
                "investors.ionq.com",
            )
            self.assertEqual(event["source"]["name"], "IonQ Investor Relations")
            self.assertTrue(event["regulatoryMirror"])

    def test_compact_form_labels_are_normalized(self) -> None:
        self.assertEqual(ir.extract_form("06/22/2026 Form8-K Current report"), "8-K")
        self.assertEqual(ir.extract_form("05/07/2026 Form10-Q Quarterly Report"), "10-Q")
        self.assertEqual(ir.extract_form("04/30/2026 FormDEF 14A Proxy"), "DEF 14A")

    def test_normalizes_schedule_ownership_forms(self) -> None:
        self.assertEqual(ir.extract_form("SCHEDULE 13G/A"), "SC 13G/A")
        self.assertEqual(
            sec.FORM_TYPES[ir.extract_form("Jun 5, 2026 SCHEDULE 13D/A")],
            "股权变动",
        )


if __name__ == "__main__":
    unittest.main()
