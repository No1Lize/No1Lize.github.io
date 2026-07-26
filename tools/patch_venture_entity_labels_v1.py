#!/usr/bin/env python3
"""Patch terminal venture semantics for product, prose and event attribution noise."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"{label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source block, found {count}")
    print(f"{label}: applied")
    return text.replace(old, new, 1)


def patch_semantics() -> None:
    text = TARGET.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''PRODUCT_EDITORIAL_RE = re.compile(
    r"\\b(?:press release|latest news|newsroom|things to know|crew undocks|"
    r"journey home|announces?|launches?|introduces?|partnership|collaboration)\\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|大会|峰会|访谈|观点|生态合作)",
    re.IGNORECASE,
)
PERSON_CJK_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
''',
        '''PRODUCT_EDITORIAL_RE = re.compile(
    r"\\b(?:press release|latest news|newsroom|things to know|crew undocks|"
    r"journey home|announces?|launches?|introduces?|partnership|collaboration|"
    r"raises?|raised|funding round|financing round|contributed|arrives?|signs?|"
    r"named|publishes?|delivers?|updates?|development|virtual tour|"
    r"demo(?:nstration)?)\\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|"
    r"大会|峰会|访谈|观点|生态合作|融资|募资|领投|跟投|交付速度|再提升)",
    re.IGNORECASE,
)
PRODUCT_URL_FILE_RE = re.compile(
    r"(?:^https?:$|https?://|www\\.|\\.(?:png|jpe?g|gif|webp|svg|pdf|html?)"
    r"(?:[?#].*)?$|^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
    re.IGNORECASE,
)
PRODUCT_DATE_LABEL_RE = re.compile(
    r"^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\\s+\\d{1,2}(?:,?\\s+20\\d{2})?$",
    re.IGNORECASE,
)
PRODUCT_NAV_PREFIX_RE = re.compile(
    r"^(?:view|explore|discover|read|learn|watch|see|find|download|get started)\\b",
    re.IGNORECASE,
)
PRODUCT_FRAGMENT_RE = re.compile(r"^\\d{2,}\\s+[A-Za-z]", re.IGNORECASE)
PRODUCT_GENERIC_RE = re.compile(
    r"^(?:b2b marketing|b2c marketing|marketing|工艺革新|技术创新|"
    r"产品|平台|服务|业务|更多|qnimgs|images?|assets?|static|uploads?)$",
    re.IGNORECASE,
)
NARRATIVE_EDITORIAL_RE = re.compile(
    r"(?:网友|直呼|狂塞|昨日|过去\\d+天|一口气|热议|小编|据悉|报道称|"
    r"本文|作者|赌.{0,8}级|别再|它讲的是)|"
    r"\\b(?:click here|we asked|viral|what you need to know)\\b",
    re.IGNORECASE,
)
PERSON_CJK_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
''',
        "expanded product and prose noise constants",
    )
    text = replace_once(
        text,
        '''        if len(clause) < 18 or PAGE_CHROME_RE.search(clause):
            continue
''',
        '''        if (
            len(clause) < 18
            or PAGE_CHROME_RE.search(clause)
            or NARRATIVE_EDITORIAL_RE.search(clause)
        ):
            continue
''',
        "editorial narrative clause filter",
    )
    text = replace_once(
        text,
        '''def _valid_product(value: Any, aliases: Sequence[str] = ()) -> bool:
    item = clean_text(value, 200).strip()
    compact = _compact(item)
    if (
        not item
        or YEAR_ONLY_RE.fullmatch(item)
        or NUMERIC_ONLY_RE.fullmatch(item)
        or PRODUCT_EDITORIAL_RE.search(item)
        or len(compact) < 2
    ):
        return False
    alias_compacts = {_compact(alias) for alias in aliases if _compact(alias)}
    return compact not in alias_compacts
''',
        '''def _valid_product(value: Any, aliases: Sequence[str] = ()) -> bool:
    item = clean_text(value, 200).strip()
    compact = _compact(item)
    if (
        not item
        or len(item) > 100
        or YEAR_ONLY_RE.fullmatch(item)
        or NUMERIC_ONLY_RE.fullmatch(item)
        or PRODUCT_EDITORIAL_RE.search(item)
        or PRODUCT_URL_FILE_RE.search(item)
        or PRODUCT_DATE_LABEL_RE.fullmatch(item)
        or PRODUCT_NAV_PREFIX_RE.search(item)
        or PRODUCT_FRAGMENT_RE.search(item)
        or PRODUCT_GENERIC_RE.fullmatch(item)
        or len(compact) < 2
    ):
        return False
    alias_compacts = {_compact(alias) for alias in aliases if _compact(alias)}
    return compact not in alias_compacts
''',
        "strict product label validator",
    )
    text = replace_once(
        text,
        '''    return source_is_official


def _sanitize_events(
''',
        '''    return bool(source_is_official and FIRST_PERSON_FINANCING_RE.search(evidence))


def _sanitize_events(
''',
        "strict official event subject attribution",
    )
    TARGET.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''import copy
import unittest
''',
        '''import copy
import json
import unittest
''',
        "json test import",
    )
    marker = '''    def test_trims_investor_relations_page_chrome(self) -> None:
'''
    addition = '''    def test_rejects_web_dates_files_events_and_clickbait_prose(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude Platform for enterprise AI.",
                    "researchTechnology": (
                        "过去45天Anthropic狂塞500个技能，网友直呼疯狂，一口气赌OS级深度。 "
                        "Anthropic develops Claude Platform for enterprise AI."
                    ),
                    "products": [
                        "Claude Platform",
                        "November 19",
                        "June 30",
                        "https:",
                        "www.example.com",
                        "A15D1080-6F8C-4C6A-833F-73803D8B7.png",
                        "View C360 Reference Architecture for Insurance",
                        "Explore Agent Library",
                        "F.02 Contributed to the Production of 30",
                        "000 Cars at BMW",
                        "Commonwealth Fusion Systems Raises $863 Million Series B2 Round",
                        "F.03 Battery Development",
                        "B2B Marketing",
                        "工艺革新",
                        "星河动力 CQ-50 发动机交付速度再提升",
                    ],
                    "team": [],
                    "financing": [
                        {
                            "date": "2021-03-19",
                            "title": "Newsroom",
                            "summary": (
                                "A founder raised $900M. Anthropic researchers later commented."
                            ),
                            "sourceUrl": "https://www.anthropic.com/newsroom",
                        }
                    ],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        company = cleaned["companies"]["anthropic"]
        self.assertEqual(company["products"], ["Claude Platform"])
        self.assertEqual(
            company["researchTechnology"],
            "Anthropic develops Claude Platform for enterprise AI.",
        )
        self.assertEqual(company["financing"], [])
        self.assertEqual(diagnostics["removedProducts"], 14)
        self.assertEqual(diagnostics["removedFinancing"], 1)

    def test_current_snapshot_removes_known_product_and_prose_noise(self) -> None:
        payload = json.loads(semantics.SNAPSHOT_PATH.read_text(encoding="utf-8"))
        catalog_text = semantics.CATALOG_PATH.read_text(encoding="utf-8")
        cleaned, _ = semantics.enforce_snapshot(payload, catalog_text)
        rendered = json.dumps(cleaned, ensure_ascii=False)
        forbidden = (
            "November 19",
            "June 30",
            "View C360 Reference Architecture for Insurance",
            "Commonwealth Fusion Systems Raises $863 Million Series B2 Round",
            "A15D1080-6F8C-4C6A-833F-73803D8B7",
            "星河动力 CQ-50 发动机交付速度再提升",
            "网友直呼疯狂",
        )
        self.assertTrue(all(item not in rendered for item in forbidden))
        self.assertEqual(cleaned["companies"]["form-energy"]["financing"], [])

'''
    if "def test_rejects_web_dates_files_events_and_clickbait_prose" not in text:
        if marker not in text:
            raise SystemExit("product noise test insertion marker not found")
        text = text.replace(marker, addition + marker, 1)
    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_semantics()
    patch_tests()


if __name__ == "__main__":
    main()
