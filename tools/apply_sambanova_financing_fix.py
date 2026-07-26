#!/usr/bin/env python3
"""Retain explicit first-close financing evidence in the final publication gate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "finalize_venture_profiles.py"
TEST = ROOT / "tests" / "test_finalize_venture_profiles.py"


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    old = '''STRONG_FINANCING_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)|funding round|financing round|"
    r"seed round|pre-seed funding|secured .{0,40} funding|"
    r"backed by|led by|investment from|closes? .{0,40} round)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
'''
    new = '''STRONG_FINANCING_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)|funding round|financing round|"
    r"seed round|pre-seed funding|secured .{0,40} funding|"
    r"first close.{0,80}(?:funding|financing)|"
    r"complet(?:e|ed|es|ing).{0,80}(?:funding|financing)|"
    r"backed by|led by|investment from|closes? .{0,40} round)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
'''
    if new not in source:
        if old not in source:
            raise SystemExit("finalizer financing regex block not found")
        SOURCE.write_text(source.replace(old, new, 1), encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    if "test_financing_keeps_explicit_first_close" not in test:
        marker = "    def test_recent_investments_use_actual_one_year_window(self) -> None:\n"
        method = '''    def test_financing_keeps_explicit_first_close(self) -> None:
        rows = finalizer.finalize_financing(
            [
                {
                    "date": "2026-07-08",
                    "type": "融资",
                    "title": "SambaNova Completes First Close of $1B Financing at $11B Valuation",
                    "summary": "SambaNova completed the first close of $1 billion in strategic financing.",
                    "round": "strategic",
                    "sourceUrl": "https://sambanova.ai/press/financing",
                }
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("First Close", rows[0]["title"])

'''
        if marker not in test:
            raise SystemExit("finalizer test insertion marker not found")
        TEST.write_text(test.replace(marker, method + marker, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
