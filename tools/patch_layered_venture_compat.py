#!/usr/bin/env python3
"""Apply compatibility fixes required before the layered evidence migration."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
TESTS = ROOT / "tests" / "test_refine_venture_research_evidence.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        REFINER,
        '    r"投资|领投|跟投|参投|加码)",\n',
        '    r"投资|融资|领投|跟投|参投|参与.{0,24}融资|加码)",\n',
        "explicit investment participation",
    )
    replace_once(
        TESTS,
        "export const companies = [",
        "export type Company = {};\nexport const companies: Company[] = [",
        "typed company fixture",
    )
    replace_once(
        TESTS,
        "export const institutionCatalog = [",
        "export const institutionCatalog: Institution[] = [",
        "typed institution fixture",
    )
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
