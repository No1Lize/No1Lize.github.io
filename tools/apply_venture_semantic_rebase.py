#!/usr/bin/env python3
"""Apply the validated venture semantic fixes to the latest main branch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
CATALOG = ROOT / "lib" / "catalog-data.ts"
REFINER_TEST = ROOT / "tests" / "test_refine_venture_research_evidence.py"
FINALIZER_TEST = ROOT / "tests" / "test_finalize_venture_profiles.py"
NEW_TEST = ROOT / "tests" / "test_venture_semantic_rebase.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"expected {label} block not found")
    return text.replace(old, new, 1)


def patch_refiner() -> None:
    text = REFINER.read_text(encoding="utf-8")
    replacements = [
        (
            "try:\n    from .sanitize_venture_narratives import sanitize_narrative\n",
            "try:\n    from .enforce_venture_entity_semantics import enforce_snapshot\n    from .sanitize_venture_narratives import sanitize_narrative\n",
            "refiner package import",
        ),
        (
            "except ImportError:\n    from sanitize_venture_narratives import sanitize_narrative\n",
            "except ImportError:\n    from enforce_venture_entity_semantics import enforce_snapshot\n    from sanitize_venture_narratives import sanitize_narrative\n",
            "refiner script import",
        ),
        (
            '''    evidence_values = [
        profile.get("researchTechnology", ""),
        profile.get("technology", ""),
        profile.get("background", ""),
        *(_article_text(article) for article in articles[:40]),
    ]
''',
            '''    # Product descriptions use immutable article evidence first. Reading
    # normalized profile narratives here creates a cross-gate two-state cycle.
    evidence_values = [
        *(_article_text(article) for article in articles[:40]),
    ]
''',
            "stable product evidence",
        ),
        (
            '''            if _contains_any(sentence, TECH_TERMS)
            and any(alias.casefold() in sentence.casefold() for alias in aliases)
''',
            '''            if _contains_any(sentence, TECH_TERMS)
            and any(alias.casefold() in sentence.casefold() for alias in aliases)
            and "尚未识别到可独立核对的技术说明" not in sentence
''',
            "placeholder highlight filter",
        ),
        (
            '''        if candidate and name.casefold() not in candidate.casefold() and not BIOGRAPHY_RE.search(candidate):
            candidate = ""
''',
            '''        if candidate and (
            name.casefold() not in candidate.casefold()
            or not BIOGRAPHY_RE.search(candidate)
        ):
            candidate = ""
''',
            "team summary biography condition",
        ),
        (
            '''            if value and name.casefold() not in value.casefold() and not BIOGRAPHY_RE.search(value):
                value = ""
''',
            '''            if value and (
                name.casefold() not in value.casefold()
                or not BIOGRAPHY_RE.search(value)
            ):
                value = ""
''',
            "team experience biography condition",
        ),
        (
            '''    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    return cleaned, diagnostics
''',
            '''    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    # Evidence refinement must not reintroduce facts rejected by the canonical
    # entity-semantic publication gate.
    cleaned, _ = enforce_snapshot(cleaned, catalog_text)
    return cleaned, diagnostics
''',
            "canonical entity gate reuse",
        ),
        (
            '''    rendered = json.dumps(refined, ensure_ascii=False, indent=2) + "\\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    if args.check:
        if rendered != current:
            print("Venture profile snapshot requires evidence alignment.")
            return 1
        print("Venture profile snapshot passed evidence alignment checks.")
        return 0
    if rendered == current:
        print("No venture evidence alignment changes.")
        return 0
''',
            '''    rendered = json.dumps(refined, ensure_ascii=False, indent=2) + "\\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    if args.check:
        if refined != snapshot:
            print("Venture profile snapshot requires evidence alignment.")
            return 1
        print("Venture profile snapshot passed evidence alignment checks.")
        return 0
    if refined == snapshot:
        print("No venture evidence alignment changes.")
        return 0
''',
            "semantic evidence check",
        ),
    ]
    for old, new, label in replacements:
        text = replace_once(text, old, new, label)
    REFINER.write_text(text, encoding="utf-8")


def patch_finalizer() -> None:
    text = FINALIZER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''STRONG_FINANCING_RE = re.compile(
    r"\\b(?:rais(?:e|ed|es|ing)|funding round|financing round|"
    r"seed round|pre-seed funding|secured .{0,40} funding|"
    r"backed by|led by|investment from|closes? .{0,40} round)\\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
''',
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
        "first-close financing regex",
    )
    text = replace_once(
        text,
        '''                    6,
                    260,
''',
        '''                    6,
                    220,
''',
        "finalizer highlight limit",
    )
    FINALIZER.write_text(text, encoding="utf-8")


def patch_semantics() -> None:
    text = SEMANTICS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''PRODUCT_EXACT_NOISE = {
    "cost-effective drug discovery",
    "drug discovery",
    "nach01",
}
''',
        '''PRODUCT_EXACT_NOISE = {
    "api", "apis", "model", "models", "platform", "platforms",
    "service", "services", "software", "hardware", "system", "systems",
    "模型", "平台", "服务", "软件", "硬件", "系统",
    "cost-effective drug discovery",
    "drug discovery",
    "nach01",
}
''',
        "generic exact product noise",
    )
    text = replace_once(
        text,
        '''            clean_text(item, 260)
            for item in highlights
            if clean_text(item, 260)
''',
        '''            clean_text(item, 220)
            for item in highlights
            if clean_text(item, 220)
''',
        "semantic highlight limit",
    )
    SEMANTICS.write_text(text, encoding="utf-8")


def patch_catalog_and_tests() -> None:
    catalog = CATALOG.read_text(encoding="utf-8")
    catalog = replace_once(
        catalog,
        '{ slug:"sambanova", name:"SambaNova Systems", region:',
        '{ slug:"sambanova", name:"SambaNova Systems", englishName:"SambaNova", region:',
        "SambaNova short brand alias",
    )
    CATALOG.write_text(catalog, encoding="utf-8")

    test = REFINER_TEST.read_text(encoding="utf-8")
    test = test.replace("智元机器人启动港股上市", "智元机器人正式在港股上市")
    test = replace_once(
        test,
        '"summary": "智元机器人参加产业大会。",',
        '"summary": "邓泰华出席智元机器人生态大会。",',
        "name-only team fixture",
    )
    test = replace_once(
        test,
        '        self.assertIn("尚未识别", products["灵犀"]["description"])\n',
        '        self.assertIn("尚未识别", products["灵犀"]["description"])\n'
        '        self.assertEqual(products["灵犀"]["technicalHighlights"], [])\n',
        "fallback highlight assertion",
    )
    REFINER_TEST.write_text(test, encoding="utf-8")

    finalizer_test = FINALIZER_TEST.read_text(encoding="utf-8")
    if "test_financing_keeps_explicit_first_close" not in finalizer_test:
        marker = "    def test_recent_investments_use_actual_one_year_window(self) -> None:\n"
        method = '''    def test_financing_keeps_explicit_first_close(self) -> None:
        rows = finalizer.finalize_financing(
            [{
                "date": "2026-07-08",
                "type": "融资",
                "title": "SambaNova Completes First Close of $1B Financing at $11B Valuation",
                "summary": "SambaNova completed the first close of $1 billion in strategic financing.",
                "round": "strategic",
                "sourceUrl": "https://sambanova.ai/press/financing",
            }]
        )
        self.assertEqual(len(rows), 1)

'''
        if marker not in finalizer_test:
            raise SystemExit("finalizer test insertion marker not found")
        finalizer_test = finalizer_test.replace(marker, method + marker, 1)
        FINALIZER_TEST.write_text(finalizer_test, encoding="utf-8")

    NEW_TEST.write_text('''from __future__ import annotations

import unittest

from tools import enforce_venture_entity_semantics as semantics


class VentureSemanticRebaseTests(unittest.TestCase):
    def test_rejects_bare_generic_product_names(self) -> None:
        self.assertFalse(semantics._valid_product("API"))
        self.assertFalse(semantics._valid_product("Platform"))
        self.assertTrue(semantics._valid_product("企业 API"))
        self.assertTrue(semantics._valid_product("Claude Platform"))

    def test_accepts_official_short_brand_financing_subject(self) -> None:
        row = {
            "title": "SambaNova Completes First Close of $1B Financing",
            "summary": "SambaNova completed the financing at an $11B valuation.",
            "sourceUrl": "https://sambanova.ai/news/financing",
        }
        self.assertTrue(
            semantics._subject_evidence(
                row,
                ("SambaNova Systems", "SambaNova"),
                "sambanova.ai",
                semantics.FINANCING_ACTION_RE,
            )
        )


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")


def main() -> None:
    patch_refiner()
    patch_finalizer()
    patch_semantics()
    patch_catalog_and_tests()


if __name__ == "__main__":
    main()
