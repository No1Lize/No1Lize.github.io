#!/usr/bin/env python3
"""Reject weak third-party transaction roundups and placeholder highlights."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
TEST = ROOT / "tests" / "test_venture_semantic_rebase.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"expected {label} block not found")
    return text.replace(old, new, 1)


def main() -> None:
    semantics = SEMANTICS.read_text(encoding="utf-8")
    semantics = replace_once(
        semantics,
        '''RELATIONAL_MENTION_RE = re.compile(
    r"\\b(?:researchers? from|investors? including|including|from|backed by|"
    r"advisers? from|employees? from)\\b",
    re.IGNORECASE,
)
''',
        '''RELATIONAL_MENTION_RE = re.compile(
    r"\\b(?:researchers? from|investors? including|including|from|backed by|"
    r"advisers? from|employees? from)\\b",
    re.IGNORECASE,
)
THIRD_PARTY_ROUNDUP_RE = re.compile(
    r"\\b(?:weekly roundup|week in review|funding roundup|deal roundup)\\b|"
    r"(?:创投周报|投融资周报|融资周报|一周融资|本周融资)",
    re.IGNORECASE,
)
TRANSACTION_DETAIL_RE = re.compile(
    r"(?:[$€£¥]\\s?\\d|\\d+(?:\\.\\d+)?\\s?(?:million|billion|亿元|亿美元|万元)|"
    r"\\bseries\\s+[a-z0-9]+\\b|(?:天使|种子|pre[- ]?[a-z]|[a-z][0-9]?)轮|"
    r"first close|valuation|估值)",
    re.IGNORECASE,
)
TRANSPARENT_TECH_PLACEHOLDER_RE = re.compile(
    r"尚未识别到可独立核对的技术说明|具体技术参数以原始来源为准",
    re.IGNORECASE,
)
''',
        "transaction evidence constants",
    )
    semantics = replace_once(
        semantics,
        '''    # Third-party media rows must identify both the entity and event in the title.
    # This rejects clickbait headlines whose body merely mentions an acquisition.
    if not source_is_official and not (title_has_alias and title_has_action):
        return False
''',
        '''    # Third-party media rows must identify both the entity and event in the title,
    # avoid roundup headlines, and provide a concrete transaction detail or a
    # materially richer summary. Keyword-only weekly digests are not facts.
    if not source_is_official:
        if not (title_has_alias and title_has_action):
            return False
        if THIRD_PARTY_ROUNDUP_RE.search(title):
            return False
        investors = row.get("investors", []) if isinstance(row.get("investors"), list) else []
        has_detail = bool(
            clean_text(row.get("amount"), 80)
            or clean_text(row.get("round"), 80)
            or investors
            or TRANSACTION_DETAIL_RE.search(evidence)
        )
        title_key = _compact(title)
        summary_key = _compact(summary)
        has_distinct_summary = bool(
            summary_key
            and summary_key != title_key
            and len(summary_key) >= len(title_key) + 12
        )
        if not has_detail and not has_distinct_summary:
            return False
''',
        "strict third-party transaction evidence",
    )
    semantics = replace_once(
        semantics,
        '''            if clean_text(item, 220)
            and _contains_any(item, direct_terms)
''',
        '''            if clean_text(item, 220)
            and _contains_any(item, direct_terms)
            and not TRANSPARENT_TECH_PLACEHOLDER_RE.search(clean_text(item, 220))
''',
        "terminal placeholder highlight filter",
    )
    SEMANTICS.write_text(semantics, encoding="utf-8")

    refiner = REFINER.read_text(encoding="utf-8")
    refiner = replace_once(
        refiner,
        '''            and "尚未识别到可独立核对的技术说明" not in sentence
''',
        '''            and "尚未识别到可独立核对的技术说明" not in sentence
            and "具体技术参数以原始来源为准" not in sentence
''',
        "refiner placeholder highlight filter",
    )
    REFINER.write_text(refiner, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    if "test_rejects_weak_roundup_financing_and_placeholder_highlights" not in test:
        marker = "\n\nif __name__ == \"__main__\":\n"
        method = '''
    def test_rejects_weak_roundup_financing_and_placeholder_highlights(self) -> None:
        roundup = {
            "title": "DeepSeek 巨额融资落地 | 创投周报",
            "summary": "DeepSeek 巨额融资落地 | 创投周报",
            "sourceUrl": "https://news.example.com/weekly",
        }
        detailed = {
            "title": "Anthropic raises $2 billion in new funding",
            "summary": "Anthropic completed the transaction to expand model development.",
            "sourceUrl": "https://news.example.com/anthropic",
        }
        self.assertFalse(
            semantics._subject_evidence(
                roundup,
                ("DeepSeek",),
                "deepseek.com",
                semantics.FINANCING_ACTION_RE,
            )
        )
        self.assertTrue(
            semantics._subject_evidence(
                detailed,
                ("Anthropic",),
                "anthropic.com",
                semantics.FINANCING_ACTION_RE,
            )
        )
        cleaned = semantics._sanitize_technology_products(
            [{
                "name": "Claude 模型",
                "description": "公开资料将Claude 模型列为该公司的核心产品或技术平台，具体技术参数以原始来源为准。",
                "technicalHighlights": [
                    "公开资料将Claude 模型列为该公司的核心产品或技术平台，具体技术参数以原始来源为准。"
                ],
                "sourceUrl": "",
            }],
            ("Claude 模型",),
            ("Anthropic",),
        )
        self.assertEqual(cleaned[0]["technicalHighlights"], [])
'''
        if marker not in test:
            raise SystemExit("final test insertion marker not found")
        test = test.replace(marker, method + marker, 1)
    TEST.write_text(test, encoding="utf-8")


if __name__ == "__main__":
    main()
