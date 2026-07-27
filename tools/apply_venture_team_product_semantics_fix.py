#!/usr/bin/env python3
"""Apply stricter team-biography and product-highlight semantics once."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "refine_venture_research_evidence.py"
TEST = ROOT / "tests" / "test_refine_venture_research_evidence.py"

REPLACEMENTS = [
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
