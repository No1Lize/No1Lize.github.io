#!/usr/bin/env python3
"""One-time patch for venture evidence alignment regressions."""

from __future__ import annotations

from pathlib import Path


REFINER = Path(__file__).with_name("refine_venture_research_evidence.py")
TESTS = Path(__file__).resolve().parents[1] / "tests" / "test_refine_venture_research_evidence.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"{label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source anchor, found {count}")
    print(f"{label}: applied")
    return text.replace(old, new, 1)


def main() -> None:
    text = REFINER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    r"投资|领投|跟投|参投|加码)",\n',
        '    r"投资|融资|领投|跟投|参投|参与.{0,24}融资|加码)",\n',
        "explicit investment participation",
    )
    text = replace_once(
        text,
        '    catalog_summary = sanitize_narrative(company.summary, limit=760)\n',
        '    catalog_summary = (\n'
        '        sanitize_narrative(company.summary, limit=760)\n'
        '        or clean_text(company.summary, 760)\n'
        '    )\n',
        "short catalog summary fallback",
    )
    REFINER.write_text(text, encoding="utf-8")

    tests = TESTS.read_text(encoding="utf-8")
    tests = replace_once(
        tests,
        'export const companies = [',
        'export type Company = {};\nexport const companies: Company[] = [',
        "typed company fixture",
    )
    tests = replace_once(
        tests,
        'export const institutionCatalog = [',
        'export const institutionCatalog: Institution[] = [',
        "typed institution fixture",
    )
    TESTS.write_text(tests, encoding="utf-8")


if __name__ == "__main__":
    main()
