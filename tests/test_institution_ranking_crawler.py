from __future__ import annotations

import unittest

from tools.crawl_institution_rankings import (
    CHINAVENTURE_MARKERS,
    EXPECTED_TABLES,
    EXPECTED_TEXT_MARKERS,
    validate_pages,
)


def ranking_table(title: str, spec: dict[str, object], count: int | None = None) -> str:
    expected = int(spec["count"] if count is None else count)
    ordered = bool(spec["ordered"])
    rows: list[str] = []
    for index in range(1, expected + 1):
        name = (
            str(spec["first"]) if index == 1
            else str(spec["last"]) if index == expected
            else f"机构{index}"
        )
        if ordered:
            rows.append(f"<tr><td>{index}</td><td>机构全称{index}</td><td>{name}</td></tr>")
        else:
            rows.append(f"<tr><td>机构全称{index}</td><td>{name}</td></tr>")
    return f"<h2>{title}</h2><table>{''.join(rows)}</table>"


class InstitutionRankingCrawlerTests(unittest.TestCase):
    def test_accepts_complete_professional_source_pages(self) -> None:
        qingke = "<html>" + "".join(
            ranking_table(title, spec)
            for title, spec in EXPECTED_TABLES.items()
        ) + " ".join(EXPECTED_TEXT_MARKERS) + "</html>"
        chinaventure = "<html><body>" + " ".join(CHINAVENTURE_MARKERS) + "</body></html>"

        result = validate_pages(qingke, chinaventure)

        self.assertTrue(result["passed"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(
            result["counts"],
            {title: int(spec["count"]) for title, spec in EXPECTED_TABLES.items()},
        )

    def test_reports_incomplete_table_and_missing_category(self) -> None:
        title = "2025年中国早期投资机构30强"
        qingke = ranking_table(title, EXPECTED_TABLES[title], count=29)
        chinaventure = "<html><body>中国最佳创业投资机构TOP100</body></html>"

        result = validate_pages(qingke, chinaventure)

        self.assertFalse(result["passed"])
        failures = "\n".join(result["failures"])
        self.assertIn("expected 30, got 0", failures)
        self.assertIn("CVSource marker missing", failures)


if __name__ == "__main__":
    unittest.main()
