#!/usr/bin/env python3
"""Prevent earnings guidance and time-series copy from becoming financing facts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
TEST = ROOT / "tests" / "test_venture_semantic_rebase.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"expected {label} block not found")
    return text.replace(old, new, 1)


def main() -> None:
    refiner = REFINER.read_text(encoding="utf-8")
    refiner = replace_once(
        refiner,
        '''FINANCING_RE = re.compile(
    r"(?:\\brais(?:e|ed|es|ing)\\b|\\bfunding round\\b|\\bfinancing round\\b|"
    r"\\bseries\\s+[a-z0-9]+\\b|\\bseed round\\b|\\bpre-seed\\b|\\bbacked by\\b|"
    r"\\bled by\\b|\\binvestment from\\b|\\bsecured .{0,40} funding\\b|"
    r"融资|募资|领投|跟投|战略投资|完成.{0,18}(?:轮|融资)|获得.{0,18}投资)",
    re.IGNORECASE,
)
''',
        '''FINANCING_RE = re.compile(
    r"(?:\\brais(?:e|ed|es|ing)\\b(?!\\s+(?:full[- ]year\\s+)?guidance\\b)|"
    r"\\bfunding round\\b|\\bfinancing round\\b|"
    r"\\bseries\\s+[a-z0-9]+\\s+(?:funding|financing|round)\\b|"
    r"\\bfirst close.{0,80}(?:funding|financing)\\b|"
    r"\\bcomplet(?:e|ed|es|ing).{0,80}(?:funding|financing)\\b|"
    r"\\bseed round\\b|\\bpre-seed\\b|\\bbacked by\\b|\\bled by\\b|"
    r"\\binvestment from\\b|\\bsecured .{0,40} funding\\b|"
    r"融资|募资|领投|跟投|战略投资|完成.{0,18}(?:轮|融资)|获得.{0,18}投资)",
    re.IGNORECASE,
)
''',
        "refiner financing context",
    )
    refiner = replace_once(
        refiner,
        '''ROUND_RE = re.compile(
    r"(?:Series\\s+[A-Z][0-9]?|Pre[- ]?Seed|Seed|Angel|Growth|Strategic|"
    r"天使轮|种子轮|Pre[- ]?[A-Z]轮|[A-Z][0-9]?轮|战略融资|股权融资)",
    re.IGNORECASE,
)
''',
        '''ROUND_RE = re.compile(
    r"(?:Series\\s+[A-Z][0-9]?\\b|Pre[- ]?Seed|Seed|Angel|Growth|Strategic|"
    r"天使轮|种子轮|Pre[- ]?[A-Z]轮|[A-Z][0-9]?轮|战略融资|股权融资)",
    re.IGNORECASE,
)
''',
        "round token boundary",
    )
    REFINER.write_text(refiner, encoding="utf-8")

    semantics = SEMANTICS.read_text(encoding="utf-8")
    semantics = replace_once(
        semantics,
        '''FINANCING_ACTION_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)|funding round|financing round|"
    r"series\\s+[a-z0-9]+|seed round|pre-seed|secured .{0,40} funding|"
    r"closes? .{0,40} round|investment in|invests? in|valuation)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
''',
        '''FINANCING_ACTION_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)(?!\\s+(?:full[- ]year\\s+)?guidance\\b)|"
    r"funding round|financing round|"
    r"series\\s+[a-z0-9]+\\s+(?:funding|financing|round)|"
    r"first close.{0,80}(?:funding|financing)|"
    r"complet(?:e|ed|es|ing).{0,80}(?:funding|financing)|"
    r"seed round|pre-seed|secured .{0,40} funding|"
    r"closes? .{0,40} round|investment in|invests? in|valuation)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
''',
        "semantic financing context",
    )
    SEMANTICS.write_text(semantics, encoding="utf-8")

    finalizer = FINALIZER.read_text(encoding="utf-8")
    finalizer = replace_once(
        finalizer,
        '''STRONG_FINANCING_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)|funding round|financing round|"
    r"seed round|pre-seed funding|secured .{0,40} funding|"
    r"first close.{0,80}(?:funding|financing)|"
    r"complet(?:e|ed|es|ing).{0,80}(?:funding|financing)|"
    r"backed by|led by|investment from|closes? .{0,40} round)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
''',
        '''STRONG_FINANCING_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)(?!\\s+(?:full[- ]year\\s+)?guidance\\b)|"
    r"funding round|financing round|"
    r"seed round|pre-seed funding|secured .{0,40} funding|"
    r"first close.{0,80}(?:funding|financing)|"
    r"complet(?:e|ed|es|ing).{0,80}(?:funding|financing)|"
    r"backed by|led by|investment from|closes? .{0,40} round)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
''',
        "finalizer raised-guidance exclusion",
    )
    FINALIZER.write_text(finalizer, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    test = replace_once(
        test,
        "from tools import enforce_venture_entity_semantics as semantics\n",
        "from tools import enforce_venture_entity_semantics as semantics\n"
        "from tools import finalize_venture_profiles as finalizer\n"
        "from tools import refine_venture_research_evidence as refiner\n",
        "semantic test imports",
    )
    if "test_rejects_earnings_guidance_and_time_series_as_financing" not in test:
        marker = "\n\nif __name__ == \"__main__\":\n"
        method = '''
    def test_rejects_earnings_guidance_and_time_series_as_financing(self) -> None:
        earnings = (
            "IonQ Posts Q1 Earnings. The company raised full year guidance."
        )
        insar = (
            "IonQ launches automated 3-day repeat InSAR time series data."
        )
        self.assertIsNone(refiner.FINANCING_RE.search(earnings))
        self.assertIsNone(refiner.FINANCING_RE.search(insar))
        self.assertIsNone(refiner.ROUND_RE.search(insar))
        self.assertIsNone(semantics.FINANCING_ACTION_RE.search(earnings))
        self.assertIsNone(semantics.FINANCING_ACTION_RE.search(insar))
        self.assertEqual(
            finalizer.finalize_financing([
                {
                    "date": "2026-06-10",
                    "type": "融资",
                    "title": "IonQ Posts Q1 2026 Earnings with Record Revenue",
                    "summary": "IonQ raised full year guidance after record revenue.",
                    "round": "Growth",
                    "sourceUrl": "https://ionq.com/news/results",
                }
            ]),
            [],
        )
'''
        if marker not in test:
            raise SystemExit("test insertion marker not found")
        test = test.replace(marker, method + marker, 1)
    TEST.write_text(test, encoding="utf-8")


if __name__ == "__main__":
    main()
