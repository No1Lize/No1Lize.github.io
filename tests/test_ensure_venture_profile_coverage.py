from __future__ import annotations

import unittest

from tools.crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH, load_snapshot
from tools.ensure_venture_profile_coverage import ensure_catalog_coverage
from tools.venture_profile_extraction import parse_catalog


CATALOG = '''
export const companies: Company[] = [
  { slug:"alpha", name:"Alpha", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", summary:"Alpha summary", product:"Alpha product", source:official("Alpha","https://alpha.example/") },
  { slug:"beta", name:"Beta", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", summary:"Beta summary", product:"Beta product", source:official("Beta","https://beta.example/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"sample-capital", name:"Sample Capital", region:"美国", type:"风险投资", stages:"种子至成长期", sectors:["AI"], source:official("Sample Capital","https://capital.example/") },
];
export type IpoCompany = {};
'''


class EnsureVentureProfileCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.companies, self.institutions = parse_catalog(CATALOG)

    def test_missing_catalog_entities_receive_traceable_fallback_skeletons(self) -> None:
        snapshot = {
            "companies": {
                "alpha": {
                    "slug": "alpha",
                    "name": "Alpha",
                    "updatedAt": "2026-08-01T00:00:00Z",
                    "status": "ok",
                    "background": "Existing evidence.",
                    "technology": "Existing technology.",
                    "products": ["Alpha product"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [{"url": "https://alpha.example/"}],
                }
            },
            "institutions": {},
            "sourceStatus": [
                {
                    "kind": "company",
                    "slug": "alpha",
                    "name": "Alpha",
                    "status": "ok",
                }
            ],
        }
        companies, institutions, statuses, quality, report = ensure_catalog_coverage(
            snapshot,
            self.companies,
            self.institutions,
            updated_at="2026-08-03T15:45:00+00:00",
        )
        self.assertEqual(set(companies), {"alpha", "beta"})
        self.assertEqual(set(institutions), {"sample-capital"})
        self.assertEqual(companies["alpha"]["background"], "Existing evidence.")
        self.assertEqual(companies["beta"]["status"], "fallback")
        self.assertEqual(institutions["sample-capital"]["status"], "fallback")
        self.assertEqual(report["addedCompanies"], ["beta"])
        self.assertEqual(report["addedInstitutions"], ["sample-capital"])
        self.assertEqual(len(statuses), 3)
        self.assertTrue(quality["passed"])

    def test_repair_is_idempotent_when_coverage_is_complete(self) -> None:
        empty = {"companies": {}, "institutions": {}, "sourceStatus": []}
        companies, institutions, statuses, quality, _ = ensure_catalog_coverage(
            empty,
            self.companies,
            self.institutions,
            updated_at="2026-08-03T15:45:00+00:00",
        )
        complete = {
            "companies": companies,
            "institutions": institutions,
            "sourceStatus": statuses,
        }
        _, _, second_statuses, second_quality, report = ensure_catalog_coverage(
            complete,
            self.companies,
            self.institutions,
            updated_at="2026-08-03T16:00:00+00:00",
        )
        self.assertEqual(report["addedCompanies"], [])
        self.assertEqual(report["addedInstitutions"], [])
        self.assertEqual(report["addedStatuses"], [])
        self.assertEqual(len(second_statuses), 3)
        self.assertTrue(quality["passed"])
        self.assertTrue(second_quality["passed"])

    def test_production_snapshot_repairs_to_complete_catalog_coverage(self) -> None:
        companies, institutions = parse_catalog(CATALOG_PATH.read_text(encoding="utf-8"))
        company_profiles, institution_profiles, statuses, quality, report = ensure_catalog_coverage(
            load_snapshot(OUTPUT_PATH),
            companies,
            institutions,
            updated_at="2026-08-03T16:00:00+00:00",
        )
        self.assertEqual(len(company_profiles), len(companies))
        self.assertEqual(len(institution_profiles), len(institutions))
        self.assertEqual(report["companyCoverage"], len(companies))
        self.assertEqual(report["institutionCoverage"], len(institutions))
        self.assertEqual(report["runtimeStatusCoverage"], len(statuses))
        self.assertTrue(quality["passed"])


if __name__ == "__main__":
    unittest.main()
