#!/usr/bin/env python3
"""Rebuild technology summaries when their source text contains editorial or URL noise."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        TARGET,
        '''        technology = _relevant_clauses(
            profile.get("technology", ""), aliases, products, limit=900
        )
        if not technology and products:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
''',
        '''        raw_technology = clean_text(profile.get("technology", ""), 1400)
        technology = _relevant_clauses(
            raw_technology, aliases, products, limit=900
        )
        if products and (
            not technology
            or PRODUCT_EDITORIAL_RE.search(raw_technology)
            or PRODUCT_URL_RE.search(raw_technology)
        ):
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
''',
        "noisy technology reconstruction",
    )
    replace_once(
        TESTS,
        '''                    "technology": "Anthropic develops Claude Platform.",
''',
        '''                    "technology": "核心技术与产品包括Claude Platform、https:、www.example.com、英特尔深化智能生态合作。",
''',
        "noisy technology regression fixture",
    )
    replace_once(
        TESTS,
        '''        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Claude Platform"],
        )
''',
        '''        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Claude Platform"],
        )
        self.assertEqual(
            cleaned["companies"]["anthropic"]["technology"],
            "核心技术与产品包括Claude Platform。",
        )
''',
        "clean technology regression assertion",
    )


if __name__ == "__main__":
    main()
