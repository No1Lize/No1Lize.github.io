#!/usr/bin/env python3
"""Validate the published institution directory against Qingke and CVSource pages."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

QINGKE_URL = "https://news.pedaily.cn/202512/559270.shtml"
CHINAVENTURE_URL = "https://www.chinaventure.com.cn/rank/210/list.html"

EXPECTED_TABLES: dict[str, dict[str, Any]] = {
    "2025年中国早期投资机构30强": {
        "count": 30, "first": "中科创星", "last": "初心资本", "ordered": True,
    },
    "2025年中国创业投资机构50强": {
        "count": 50, "first": "IDG资本", "last": "华睿投资", "ordered": True,
    },
    "2025年中国私募股权投资机构50强": {
        "count": 50, "first": "红杉中国", "last": "联新资本", "ordered": True,
    },
    "2025年中国国资投资机构50强": {
        "count": 50, "first": "北京国管", "last": "南山战新投", "ordered": False,
    },
}
EXPECTED_TEXT_MARKERS = (
    "2025年中国战略投资者/CVC30强",
    "2025年中国并购投资机构10强",
)
CHINAVENTURE_MARKERS = (
    "中国最佳创业投资机构TOP100",
    "中国最佳私募股权投资机构TOP100",
    "中国最佳早期创业投资机构TOP50",
    "中国最佳中资创业投资机构TOP50",
    "中国最佳外资创业投资机构TOP50",
    "人工智能与大数据产业",
    "半导体与集成电路产业",
    "商业航天与军民融合产业",
)


@dataclass(frozen=True)
class Table:
    heading: str
    rows: tuple[tuple[str, ...], ...]


class RankingHTMLParser(HTMLParser):
    """Collect physical HTML tables without depending on article heading tags."""

    def __init__(self) -> None:
        super().__init__()
        self._capture_heading = False
        self._heading_parts: list[str] = []
        self.current_heading = ""
        self._table_depth = 0
        self._table_heading = ""
        self._table_rows: list[tuple[str, ...]] = []
        self._in_row = False
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._row: list[str] = []
        self.tables: list[Table] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "strong"}:
            self._capture_heading = True
            self._heading_parts = []
        elif tag == "table":
            if self._table_depth == 0:
                self._table_heading = self.current_heading
                self._table_rows = []
            self._table_depth += 1
        elif tag == "tr" and self._table_depth:
            self._in_row = True
            self._row = []
        elif tag in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3", "strong"} and self._capture_heading:
            heading = clean("".join(self._heading_parts))
            if heading:
                self.current_heading = heading
            self._capture_heading = False
        elif tag in {"td", "th"} and self._in_cell:
            self._row.append(clean("".join(self._cell_parts)))
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            row = tuple(cell for cell in self._row if cell)
            if row:
                self._table_rows.append(row)
            self._in_row = False
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._table_rows:
                self.tables.append(Table(self._table_heading, tuple(self._table_rows)))
                self._table_rows = []

    def handle_data(self, data: str) -> None:
        value = clean(data)
        if not value:
            return
        self.text_parts.append(value)
        if self._capture_heading:
            self._heading_parts.append(value)
        if self._in_cell:
            self._cell_parts.append(value)

    def finish(self) -> tuple[list[Table], str]:
        return self.tables, " ".join(self.text_parts)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fetch(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; VCIQInstitutionBot/1.0; "
                "+https://github.com/VCIQ/VCIQ.github.io)"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_page(html: str) -> tuple[list[Table], str]:
    parser = RankingHTMLParser()
    parser.feed(html)
    return parser.finish()


def is_header(row: tuple[str, ...]) -> bool:
    text = " ".join(row)
    return "机构全称" in text or "机构简称" in text or "名次" in text


def table_count(tables: list[Table], spec: dict[str, Any]) -> int:
    for table in tables:
        rendered = " ".join(" ".join(row) for row in table.rows)
        if spec["first"] not in rendered or spec["last"] not in rendered:
            continue
        if spec["ordered"]:
            return sum(1 for row in table.rows if row and re.fullmatch(r"\d+", row[0]))
        return sum(1 for row in table.rows if len(row) >= 2 and not is_header(row))
    return 0


def validate_pages(qingke_html: str, chinaventure_html: str) -> dict[str, object]:
    qingke_tables, qingke_text = parse_page(qingke_html)
    _, chinaventure_text = parse_page(chinaventure_html)
    counts: dict[str, int] = {}
    failures: list[str] = []

    for heading, spec in EXPECTED_TABLES.items():
        actual = table_count(qingke_tables, spec)
        expected = int(spec["count"])
        counts[heading] = actual
        if actual != expected:
            failures.append(f"{heading}: expected {expected}, got {actual}")

    for marker in EXPECTED_TEXT_MARKERS:
        if marker not in qingke_text:
            failures.append(f"Qingke marker missing: {marker}")

    for marker in CHINAVENTURE_MARKERS:
        if marker not in chinaventure_text:
            failures.append(f"CVSource marker missing: {marker}")

    return {
        "passed": not failures,
        "counts": counts,
        "tableCount": len(qingke_tables),
        "failures": failures,
        "sources": [
            {"publisher": "清科研究中心 / 投资界", "url": QINGKE_URL},
            {"publisher": "投中研究院 / 投中网", "url": CHINAVENTURE_URL},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qingke-html", type=Path)
    parser.add_argument("--chinaventure-html", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    qingke_html = args.qingke_html.read_text(encoding="utf-8") if args.qingke_html else fetch(QINGKE_URL)
    chinaventure_html = args.chinaventure_html.read_text(encoding="utf-8") if args.chinaventure_html else fetch(CHINAVENTURE_URL)
    result = validate_pages(qingke_html, chinaventure_html)
    result["checkedAt"] = datetime.now(UTC).isoformat()

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
