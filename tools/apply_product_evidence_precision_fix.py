#!/usr/bin/env python3
"""Require exact product evidence and technical context for product descriptions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
TEST = ROOT / "tests" / "test_venture_semantic_rebase.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"expected {label} block not found")
    return text.replace(old, new, 1)


def main() -> None:
    text = REFINER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''TECH_TERMS = (
    "模型", "算法", "架构", "平台", "系统", "芯片", "传感器", "训练", "推理",
    "多模态", "自主", "model", "algorithm", "architecture", "platform",
    "system", "chip", "training", "inference", "autonomous",
)
''',
        '''TECH_TERMS = (
    "模型", "算法", "架构", "平台", "系统", "芯片", "传感器", "训练", "推理",
    "多模态", "自主", "接口", "软件", "硬件", "量子", "聚变", "机器人", "无人驾驶",
    "model", "algorithm", "architecture", "platform", "system", "chip",
    "training", "inference", "autonomous", "api", "software", "hardware",
    "quantum", "fusion", "robot", "driverless", "gpu", "processor", "computing",
)
''',
        "technical evidence vocabulary",
    )
    text = replace_once(
        text,
        '''def _contains_any(value: str, terms: Sequence[str]) -> bool:
    lowered = value.casefold()
    return any(term.casefold() in lowered for term in terms)
''',
        '''def _contains_any(value: str, terms: Sequence[str]) -> bool:
    lowered = value.casefold()
    return any(term.casefold() in lowered for term in terms)


def _alias_in_text(alias: Any, value: Any) -> bool:
    """Match Latin aliases as complete tokens and CJK aliases as substrings."""
    token = clean_text(alias, 160)
    text = clean_text(value, 4000)
    if not token or not text:
        return False
    if re.fullmatch(r"[A-Za-z0-9.+_-]+", token):
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])",
                text,
                re.IGNORECASE,
            )
        )
    return token.casefold() in text.casefold()
''',
        "token-aware alias matcher",
    )
    text = replace_once(
        text,
        '''    aliases = [clean_text(alias, 120).casefold() for alias in required_aliases if clean_text(alias, 120)]
    candidates: list[tuple[int, str]] = []
''',
        '''    aliases = [clean_text(alias, 120) for alias in required_aliases if clean_text(alias, 120)]
    candidates: list[tuple[int, str]] = []
''',
        "preserve aliases for boundary matching",
    )
    text = replace_once(
        text,
        '''            alias_hits = sum(alias in lowered for alias in aliases)
            term_hits = sum(term.casefold() in lowered for term in required_terms)
''',
        '''            alias_hits = sum(_alias_in_text(alias, sentence) for alias in aliases)
            term_hits = sum(term.casefold() in lowered for term in required_terms)
''',
        "boundary-aware sentence scoring",
    )
    text = replace_once(
        text,
        '''def _product_aliases(product: str) -> list[str]:
    aliases = [clean_text(product, 160)]
    aliases.extend(
        match.group(0)
        for match in re.finditer(r"[A-Za-z][A-Za-z0-9.+_-]{1,}", product)
        if len(match.group(0)) >= 2
    )
    return list(dict.fromkeys(alias for alias in aliases if len(alias) >= 2))
''',
        '''def _product_aliases(product: str) -> list[str]:
    """Return the full label plus distinctive model codes, not brand fragments."""
    full = clean_text(product, 160)
    aliases = [full]
    generic = {
        "api", "model", "platform", "system", "engine", "chip", "robot",
        "agent", "software", "hardware", "station", "cloud", "data", "ai",
        "gpu", "cpu", "npu", "lpu",
    }
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9.+_-]{1,}", full):
        token = match.group(0)
        lowered = token.casefold()
        if lowered in generic:
            continue
        if any(char.isdigit() for char in token) or (token.isupper() and len(token) >= 2):
            aliases.append(token)
    return list(dict.fromkeys(alias for alias in aliases if len(alias) >= 2))
''',
        "distinctive product aliases",
    )
    text = replace_once(
        text,
        '''        description = _select_required_sentence(
            evidence_values,
            required_aliases=aliases,
            excluded_pattern=CAPITAL_MARKET_RE,
            limit=420,
        )
''',
        '''        description = _select_required_sentence(
            evidence_values,
            required_aliases=aliases,
            required_terms=TECH_TERMS,
            excluded_pattern=CAPITAL_MARKET_RE,
            limit=420,
        )
''',
        "technical product description requirement",
    )
    text = replace_once(
        text,
        '''            if old_description and any(
                alias.casefold() in old_description.casefold() for alias in aliases
            ):
''',
        '''            if old_description and any(
                _alias_in_text(alias, old_description) for alias in aliases
            ):
''',
        "old description product matching",
    )
    text = replace_once(
        text,
        '''            if _contains_any(sentence, TECH_TERMS)
            and any(alias.casefold() in sentence.casefold() for alias in aliases)
            and "尚未识别到可独立核对的技术说明" not in sentence
''',
        '''            if _contains_any(sentence, TECH_TERMS)
            and any(_alias_in_text(alias, sentence) for alias in aliases)
            and "尚未识别到可独立核对的技术说明" not in sentence
''',
        "technical highlight product matching",
    )
    text = replace_once(
        text,
        '''        source_url = ""
        for article in articles:
            text = _article_text(article).casefold()
            if any(alias.casefold() in text for alias in aliases) and _source_url(article):
                source_url = _source_url(article)
                break
        if not source_url:
            source_url = normalize_url(old.get("sourceUrl", ""))
''',
        '''        source_url = ""
        for article in articles:
            article_text = _article_text(article)
            if (
                description
                and description.casefold() in article_text.casefold()
                and _source_url(article)
            ):
                source_url = _source_url(article)
                break
        if not source_url:
            old_description = sanitize_narrative(old.get("description", ""), limit=420)
            if old_description == description:
                source_url = normalize_url(old.get("sourceUrl", ""))
''',
        "description-bound source attribution",
    )
    REFINER.write_text(text, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    if "test_product_evidence_requires_exact_alias_and_technical_context" not in test:
        marker = "\n\nif __name__ == \"__main__\":\n"
        method = '''
    def test_product_evidence_requires_exact_alias_and_technical_context(self) -> None:
        self.assertFalse(refiner._alias_in_text("ARC", "collaborative research agreement"))
        self.assertTrue(refiner._alias_in_text("ARC", "ARC fusion power system"))
        self.assertEqual(
            refiner._select_required_sentence(
                ["Meet Axiom Space Project Astronaut Emiliano Ventura."],
                required_aliases=("Axiom Station",),
                required_terms=refiner.TECH_TERMS,
            ),
            "",
        )
        self.assertIn(
            "Wafer-Scale Engine",
            refiner._select_required_sentence(
                ["AMD and Cerebras combine the Wafer-Scale Engine for AI inference."],
                required_aliases=("Wafer Scale Engine", "WSE"),
                required_terms=refiner.TECH_TERMS,
            ).replace("-", "-"),
        )
'''
        if marker not in test:
            raise SystemExit("precision test insertion marker not found")
        test = test.replace(marker, method + marker, 1)
    TEST.write_text(test, encoding="utf-8")


if __name__ == "__main__":
    main()
