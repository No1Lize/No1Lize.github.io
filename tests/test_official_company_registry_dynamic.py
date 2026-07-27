import json
import tempfile
import unittest
from pathlib import Path

from tools.crawl_official_companies import load_registry


CATALOG_TEMPLATE = """export type Company = unknown;
export const companies: Company[] = [
{slug:"alpha", name:"Alpha", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2020", headquarters:"A", summary:"A", product:"A", source:{} as never, confidence:1},
{slug:"beta", name:"Beta", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2021", headquarters:"B", summary:"B", product:"B", source:{} as never, confidence:1},
];
"""


class DynamicOfficialCompanyRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.catalog = root / "catalog-data.ts"
        self.registry = root / "official-company-sources.json"
        self.catalog.write_text(CATALOG_TEMPLATE, encoding="utf-8")
        self.rows = [
            {"slug": "alpha", "name": "Alpha", "region": "美国", "sector": "AI / AGI", "homepage": "https://alpha.example.com/"},
            {"slug": "beta", "name": "Beta", "region": "中国", "sector": "机器人", "homepage": "https://beta.example.com/"},
        ]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_registry(self, rows) -> None:
        self.registry.write_text(
            json.dumps({"schemaVersion": 1, "defaults": {}, "companies": rows}),
            encoding="utf-8",
        )

    def test_catalog_growth_needs_no_separate_expected_count(self) -> None:
        self.write_registry(self.rows)
        specs = load_registry(self.registry, self.catalog)
        self.assertEqual([spec.slug for spec in specs], ["alpha", "beta"])

    def test_slug_set_mismatch_still_fails(self) -> None:
        self.write_registry(self.rows[:1])
        with self.assertRaisesRegex(ValueError, "missing=\['beta'\]"):
            load_registry(self.registry, self.catalog)


if __name__ == "__main__":
    unittest.main()
