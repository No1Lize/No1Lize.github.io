#!/usr/bin/env python3
"""Resume layered migration after aligning version and capital event semantics."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
TESTS = ROOT / "tests" / "test_venture_profile_enrichment.py"


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
        TESTS,
        '        self.assertEqual(result["researchModelVersion"], 2)\n',
        '        self.assertEqual(result["researchModelVersion"], 3)\n',
        "research model version assertion",
    )
    replace_once(
        REFINER,
        '''        if CAPITAL_MARKET_RE.search(text):
            capital.append(row)
''',
        '''        if CAPITAL_MARKET_RE.search(text):
            capital_row = copy.deepcopy(row)
            capital_row["type"] = (
                "并购/退出"
                if re.search(
                    r"acquired|acquisition|merger|并购|收购|退出",
                    text,
                    re.IGNORECASE,
                )
                else "上市"
            )
            capital.append(capital_row)
''',
        "capital event type normalization",
    )
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
