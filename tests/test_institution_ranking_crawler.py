from __future__ import annotations

import unittest

from tools.crawl_institution_rankings import (
    CHINAVENTURE_MARKERS,
    EXPECTED_TABLES,
    EXPECTED_TEXT_MARKERS,
    validate_pages,
)


def ranking_table(title: str, count: int) -> str:
    rows = "".join(
        f"<tr><td>{index}</td><td>机构全称{index}</td><td>机构{index}</td></tr>"
        for index in range(1, count + 1)
    )
    return f"<h2>{title}</h2><table>{rows}</table>"


class InstitutionRankingCrawlerTests(unittest.TestCase):
    def test_accepts_complete_professional_source_pages(self) -> None:
        qingke = "<html>" + "".join(
            ranking_table(title, count)
            for title, count in EXPECTED_TABLES.items()
        ) + " ".join(EXPECTED_TEXT_MARKERS) + "</html>"
        chinaventure = "<html><body>" + " ".join(CHINAVENTURE_MARKERS) + "</body></html>"

        result = validate_pages(qingke, chinaventure)

        self.assertTrue(result["passed"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["counts"], EXPECTED_TABLES)

    def test_reports_incomplete_table_and_missing_category(self) -> None:
        qingke = ranking_table("2025年中国早期投资机构30强", 29)
        chinaventure = "<html><body>中国最佳创业投资机构TOP100</body></html>"

        result = validate_pages(qingke, chinaventure)

        self.assertFalse(result["passed"])
        failures = "\n".join(result["failures"])
        self.assertIn("expected 30, got 29", failures)
        self.assertIn("CVSource marker missing", failures)


if __name__ == "__main__":
    unittest.main()
