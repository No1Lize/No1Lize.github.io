#!/usr/bin/env python3
"""Apply stricter team, product and entity-safe evidence semantics once."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "refine_venture_research_evidence.py"
TEST = ROOT / "tests" / "test_refine_venture_research_evidence.py"

REPLACEMENTS = [
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


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    for index, (old, new) in enumerate(REPLACEMENTS, start=1):
        source = replace_once(source, old, new, f"source replacement {index}")
    SOURCE.write_text(source, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    test = test.replace(
        "智元机器人启动港股上市",
        "智元机器人正式在港股上市",
    )
    test = replace_once(
        test,
        '"summary": "智元机器人参加产业大会。",',
        '"summary": "邓泰华出席智元机器人生态大会。",',
        "name-only team headline fixture",
    )
    test = replace_once(
        test,
        '        self.assertIn("尚未识别", products["灵犀"]["description"])\n',
        '        self.assertIn("尚未识别", products["灵犀"]["description"])\n'
        '        self.assertEqual(products["灵犀"]["technicalHighlights"], [])\n',
        "fallback highlight assertion",
    )
    TEST.write_text(test, encoding="utf-8")


if __name__ == "__main__":
    main()
