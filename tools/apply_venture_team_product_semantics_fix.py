#!/usr/bin/env python3
"""Apply stricter team, product and entity-safe evidence semantics once."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "refine_venture_research_evidence.py"
SOURCE_TEST = ROOT / "tests" / "test_refine_venture_research_evidence.py"
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
SEMANTICS_TEST = ROOT / "tests" / "test_venture_entity_semantics.py"
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
CATALOG = ROOT / "lib" / "catalog-data.ts"

SOURCE_REPLACEMENTS = [
    (
        '''try:
    from .sanitize_venture_narratives import sanitize_narrative
''',
        '''try:
    from .enforce_venture_entity_semantics import enforce_snapshot
    from .sanitize_venture_narratives import sanitize_narrative
''',
    ),
    (
        '''except ImportError:
    from sanitize_venture_narratives import sanitize_narrative
''',
        '''except ImportError:
    from enforce_venture_entity_semantics import enforce_snapshot
    from sanitize_venture_narratives import sanitize_narrative
''',
    ),
    (
        '''    evidence_values = [
        profile.get("researchTechnology", ""),
        profile.get("technology", ""),
        profile.get("background", ""),
        *(_article_text(article) for article in articles[:40]),
    ]
''',
        '''    # Product descriptions must use immutable source evidence. Reading
    # normalized profile narratives here creates a two-state oscillation because
    # the terminal semantic gate may replace those narratives after this pass.
    evidence_values = [
        *(_article_text(article) for article in articles[:40]),
    ]
''',
    ),
    (
        '''            if _contains_any(sentence, TECH_TERMS)
            and any(alias.casefold() in sentence.casefold() for alias in aliases)
''',
        '''            if _contains_any(sentence, TECH_TERMS)
            and any(alias.casefold() in sentence.casefold() for alias in aliases)
            and "尚未识别到可独立核对的技术说明" not in sentence
''',
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
    # Evidence refinement must not reintroduce facts rejected by the terminal
    # entity-semantic gate. Reusing the canonical gate keeps product, team and
    # capital-event semantics identical across every publication stage.
    cleaned, _ = enforce_snapshot(cleaned, catalog_text)
    return cleaned, diagnostics
''',
    ),
]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"expected {label} block not found")
    return text.replace(old, new, 1)


def update_file(path: Path, replacements: list[tuple[str, str]], label: str) -> None:
    text = path.read_text(encoding="utf-8")
    for index, (old, new) in enumerate(replacements, start=1):
        text = replace_once(text, old, new, f"{label} replacement {index}")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    update_file(SOURCE, SOURCE_REPLACEMENTS, "source")

    source_test = SOURCE_TEST.read_text(encoding="utf-8")
    source_test = source_test.replace(
        "智元机器人启动港股上市",
        "智元机器人正式在港股上市",
    )
    source_test = replace_once(
        source_test,
        '"summary": "智元机器人参加产业大会。",',
        '"summary": "邓泰华出席智元机器人生态大会。",',
        "name-only team headline fixture",
    )
    source_test = replace_once(
        source_test,
        '        self.assertIn("尚未识别", products["灵犀"]["description"])\n',
        '        self.assertIn("尚未识别", products["灵犀"]["description"])\n'
        '        self.assertEqual(products["灵犀"]["technicalHighlights"], [])\n',
        "fallback highlight assertion",
    )
    SOURCE_TEST.write_text(source_test, encoding="utf-8")

    semantics = SEMANTICS.read_text(encoding="utf-8")
    semantics = replace_once(
        semantics,
        '''PRODUCT_EXACT_NOISE = {
    "cost-effective drug discovery",
    "drug discovery",
    "nach01",
}
''',
        '''PRODUCT_EXACT_NOISE = {
    "api",
    "apis",
    "model",
    "models",
    "platform",
    "platforms",
    "service",
    "services",
    "software",
    "hardware",
    "system",
    "systems",
    "模型",
    "平台",
    "服务",
    "软件",
    "硬件",
    "系统",
    "cost-effective drug discovery",
    "drug discovery",
    "nach01",
}
''',
        "generic product exact-noise set",
    )
    semantics = replace_once(
        semantics,
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
    SEMANTICS.write_text(semantics, encoding="utf-8")

    finalizer = FINALIZER.read_text(encoding="utf-8")
    finalizer = replace_once(
        finalizer,
        '''                    6,
                    260,
''',
        '''                    6,
                    220,
''',
        "finalizer highlight limit",
    )
    FINALIZER.write_text(finalizer, encoding="utf-8")

    catalog = CATALOG.read_text(encoding="utf-8")
    catalog = replace_once(
        catalog,
        '{ slug:"sambanova", name:"SambaNova Systems", region:',
        '{ slug:"sambanova", name:"SambaNova Systems", englishName:"SambaNova", region:',
        "SambaNova brand alias",
    )
    CATALOG.write_text(catalog, encoding="utf-8")

    semantics_test = SEMANTICS_TEST.read_text(encoding="utf-8")
    if "test_rejects_bare_generic_product_names" not in semantics_test:
        marker = '\n    def test_trims_investor_relations_page_chrome(self) -> None:\n'
        method = '''
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
'''
        if marker not in semantics_test:
            raise SystemExit("entity semantic test insertion marker not found")
        semantics_test = semantics_test.replace(marker, method + marker, 1)
    SEMANTICS_TEST.write_text(semantics_test, encoding="utf-8")


if __name__ == "__main__":
    main()
