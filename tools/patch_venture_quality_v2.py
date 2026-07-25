#!/usr/bin/env python3
"""Apply the second deterministic venture-profile quality hardening patch.

This helper is intentionally one-shot. The accompanying workflow removes it
and itself after the patch, tests, and snapshot sanitation succeed.
"""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXTRACTION_PATH = ROOT / "tools" / "venture_profile_extraction.py"
TEST_PATH = ROOT / "tests" / "test_venture_profile_noise_filters.py"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_extraction() -> None:
    text = EXTRACTION_PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '    "研究院",\n}',
        '    "研究院",\n'
        '    "高级",\n'
        '    "副总",\n'
        '    "总裁",\n'
        '    "经理",\n'
        '    "总监",\n'
        '    "主管",\n'
        '    "首席",\n'
        '    "负责人",\n'
        '    "董事会",\n'
        '}',
        "person role fragments",
    )

    text = replace_once(
        text,
        '    "软件包",\n)\n\nCOMPANY_LINK_TERMS = {',
        '    "软件包",\n)\n\n'
        'PRODUCT_EVENT_TERMS = (\n'
        '    "conference",\n'
        '    "summit",\n'
        '    "competition",\n'
        '    "contest",\n'
        '    "event",\n'
        '    "award",\n'
        '    "webinar",\n'
        '    "大会",\n'
        '    "峰会",\n'
        '    "论坛",\n'
        '    "大赛",\n'
        '    "赛事",\n'
        '    "活动",\n'
        '    "发布会",\n'
        '    "展会",\n'
        '    "招聘",\n'
        '    "奖项",\n'
        '    "获奖",\n'
        '    "新闻",\n'
        '    "资讯",\n'
        ')\n\nCOMPANY_LINK_TERMS = {',
        "product event terms",
    )

    product_guard = (
        '    if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):\n'
        '        return False\n'
        '    if compact in {re.sub(r"\\W+", "", value).casefold() for value in GENERIC_PRODUCT_LABELS}:\n'
    )
    product_guard_replacement = (
        '    if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):\n'
        '        return False\n'
        '    if any(term in lowered for term in PRODUCT_EVENT_TERMS):\n'
        '        return False\n'
        '    if "|" in item or "｜" in item:\n'
        '        return False\n'
        '    if compact in {re.sub(r"\\W+", "", value).casefold() for value in GENERIC_PRODUCT_LABELS}:\n'
    )
    text = replace_once(text, product_guard, product_guard_replacement, "specific product guard")

    sanitize_guard = (
        '        if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):\n'
        '            continue\n'
        '        if compact in {\n'
    )
    sanitize_guard_replacement = (
        '        if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):\n'
        '            continue\n'
        '        if any(term in lowered for term in PRODUCT_EVENT_TERMS):\n'
        '            continue\n'
        '        if "|" in item or "｜" in item:\n'
        '            continue\n'
        '        if compact in {\n'
    )
    text = replace_once(text, sanitize_guard, sanitize_guard_replacement, "retained product guard")

    valid_person_end = (
        '    return bool(\n'
        '        re.fullmatch(\n'
        '            r"[A-Z][A-Za-z\'.-]+(?:\\s+[A-Z][A-Za-z\'.-]+){1,3}",\n'
        '            compact,\n'
        '        )\n'
        '    )\n\n\n'
        'def sanitize_team_members(\n'
    )
    valid_person_replacement = (
        '    return bool(\n'
        '        re.fullmatch(\n'
        '            r"[A-Z][A-Za-z\'.-]+(?:\\s+[A-Z][A-Za-z\'.-]+){1,3}",\n'
        '            compact,\n'
        '        )\n'
        '    )\n\n\n'
        'def _matches_entity_alias(name: str, aliases: Sequence[str]) -> bool:\n'
        '    name_key = re.sub(r"[^a-z0-9\\u3400-\\u9fff]+", "", clean_text(name, 120).casefold())\n'
        '    if len(name_key) < 2:\n'
        '        return False\n'
        '    for alias in aliases:\n'
        '        alias_key = re.sub(r"[^a-z0-9\\u3400-\\u9fff]+", "", clean_text(alias, 120).casefold())\n'
        '        if len(alias_key) < 2:\n'
        '            continue\n'
        '        if name_key in alias_key or alias_key in name_key:\n'
        '            return True\n'
        '    return False\n\n\n'
        'def sanitize_team_members(\n'
    )
    text = replace_once(text, valid_person_end, valid_person_replacement, "entity alias helper")

    alias_guard = '        if any(alias in name.casefold() for alias in alias_keys if len(alias) >= 2):\n'
    if text.count(alias_guard) != 2:
        raise RuntimeError(f"team alias guards: expected two anchors, found {text.count(alias_guard)}")
    text = text.replace(alias_guard, '        if _matches_entity_alias(name, alias_keys):\n')

    event_helper_anchor = (
        '    if any(item in lowered for item in ("strategic", "战略投资")):\n'
        '        return "战略融资"\n'
        '    return "融资"\n\n\n'
        'def extract_capital_events(\n'
    )
    event_helper_replacement = (
        '    if any(item in lowered for item in ("strategic", "战略投资")):\n'
        '        return "战略融资"\n'
        '    return "融资"\n\n\n'
        'def has_capital_event_evidence(sentence: str, capital_market: bool) -> bool:\n'
        '    lowered = clean_text(sentence, 2000).casefold()\n'
        '    if capital_market:\n'
        '        return any(keyword.casefold() in lowered for keyword in CAPITAL_MARKET_KEYWORDS)\n'
        '    strong_keywords = tuple(\n'
        '        keyword for keyword in FINANCING_KEYWORDS if keyword.casefold() != "investor"\n'
        '    )\n'
        '    return any(keyword.casefold() in lowered for keyword in strong_keywords)\n\n\n'
        'def extract_capital_events(\n'
    )
    text = replace_once(text, event_helper_anchor, event_helper_replacement, "capital evidence helper")

    text = replace_once(
        text,
        '            if score < 4:\n                continue\n',
        '            if score < 4 or not has_capital_event_evidence(sentence, capital_market):\n                continue\n',
        "capital event acceptance",
    )

    EXTRACTION_PATH.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '          <p>联席 总裁 营销服 总裁</p>\n',
        '          <p>联席 总裁 营销服 总裁 高级副 总裁 智元 合伙人</p>\n',
        "team fixture",
    )
    text = replace_once(
        text,
        '        self.assertNotIn("营销服", names)\n',
        '        self.assertNotIn("营销服", names)\n'
        '        self.assertNotIn("高级副", names)\n'
        '        self.assertNotIn("智元", names)\n',
        "team assertions",
    )
    text = replace_once(
        text,
        '          <h2>远征A3人形机器人</h2>\n',
        '          <h2>远征A3人形机器人</h2>\n'
        '          <h2>具身智能服务机器人大赛</h2>\n'
        '          <h2>Transforming U.S. Defense Capabilities | Anduril</h2>\n',
        "product fixture",
    )
    text = replace_once(
        text,
        '        self.assertNotIn("售后服务政策", products)\n\n',
        '        self.assertNotIn("售后服务政策", products)\n'
        '        self.assertNotIn("具身智能服务机器人大赛", products)\n'
        '        self.assertNotIn("Transforming U.S. Defense Capabilities | Anduril", products)\n\n',
        "product assertions",
    )

    new_test = '''    def test_capital_events_require_explicit_event_evidence(self) -> None:
        generic_body = """
        <html><head><title>Transforming U.S. Defense Capabilities | Anduril</title></head>
        <body><p>Anduril Industries builds advanced autonomous systems and defense technology.</p></body></html>
        """
        generic_page = extraction.parse_public_page(
            "https://www.anduril.com/", generic_body, "company"
        )
        self.assertEqual(
            extraction.extract_capital_events(
                [generic_page], ("Anduril Industries", "Anduril"), capital_market=False
            ),
            [],
        )
        self.assertEqual(
            extraction.extract_capital_events(
                [generic_page], ("Anduril Industries", "Anduril"), capital_market=True
            ),
            [],
        )

        funding_body = """
        <html><head><title>Anduril raises Series G</title></head>
        <body><p>Anduril raised $2.5 billion in a Series G funding round.</p></body></html>
        """
        funding_page = extraction.parse_public_page(
            "https://www.anduril.com/news/series-g", funding_body, "company"
        )
        events = extraction.extract_capital_events(
            [funding_page], ("Anduril Industries", "Anduril"), capital_market=False
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["round"], "Series G")
        self.assertEqual(events[0]["amount"], "$2.5 billion")

'''
    text = replace_once(
        text,
        '    def test_retained_history_is_resanitized_after_homepage_timeout(self) -> None:\n',
        new_test + '    def test_retained_history_is_resanitized_after_homepage_timeout(self) -> None:\n',
        "capital event test",
    )
    text = replace_once(
        text,
        '                {"name": "具身业务部", "role": "总裁", "summary": "", "sourceUrl": company.source_url},\n',
        '                {"name": "具身业务部", "role": "总裁", "summary": "", "sourceUrl": company.source_url},\n'
        '                {"name": "高级副", "role": "总裁", "summary": "", "sourceUrl": company.source_url},\n'
        '                {"name": "智元", "role": "合伙人", "summary": "", "sourceUrl": company.source_url},\n',
        "retained team fixture",
    )
    TEST_PATH.write_text(text, encoding="utf-8")


def event_text(event: dict[str, Any]) -> str:
    return " ".join(
        str(event.get(key, ""))
        for key in ("title", "summary", "round", "amount", "type")
    )


def sanitize_snapshot() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    importlib.invalidate_caches()
    from tools import crawl_venture_profiles as crawler
    from tools import venture_profile_extraction as extraction

    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    companies, institutions = extraction.parse_catalog(CATALOG_PATH.read_text(encoding="utf-8"))
    company_map = {item.slug: item for item in companies}
    institution_map = {item.slug: item for item in institutions}

    for slug, profile in payload.get("companies", {}).items():
        spec = company_map.get(slug)
        aliases = spec.aliases if spec else (str(profile.get("name", "")),)
        profile["team"] = extraction.sanitize_team_members(profile.get("team", []), aliases)
        profile["products"] = extraction.sanitize_product_items(profile.get("products", []))
        profile["financing"] = [
            event
            for event in profile.get("financing", [])
            if extraction.has_capital_event_evidence(event_text(event), False)
        ]
        profile["capitalMarkets"] = [
            event
            for event in profile.get("capitalMarkets", [])
            if extraction.has_capital_event_evidence(event_text(event), True)
        ]
        profile["evidenceScore"] = extraction.evidence_score(profile, "company")

    for slug, profile in payload.get("institutions", {}).items():
        spec = institution_map.get(slug)
        aliases = spec.aliases if spec else (str(profile.get("name", "")),)
        profile["team"] = extraction.sanitize_team_members(profile.get("team", []), aliases)
        profile["evidenceScore"] = extraction.evidence_score(profile, "institution")

    payload["generatedAt"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    payload["qualityGate"] = crawler.evaluate_quality(
        payload.get("companies", {}),
        payload.get("institutions", {}),
        len(companies),
        len(institutions),
        payload.get("sourceStatus", []),
    )
    SNAPSHOT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    patch_extraction()
    patch_tests()
    sanitize_snapshot()
    print("Applied venture quality hardening and sanitized the current snapshot.")


if __name__ == "__main__":
    main()
