#!/usr/bin/env python3
"""Recompute venture derived fields after terminal semantic filtering."""

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
        raise SystemExit(f"{label}: expected one block, found {count}")
    print(f"{label}: applied")
    return text.replace(old, new, 1)


def patch_semantics() -> None:
    text = TARGET.read_text(encoding="utf-8")

    helper = '''def _contains_product_noise(value: Any) -> bool:
    text = clean_text(value, 1600)
    if not text:
        return False
    for raw in re.split(r"[、，,;/。]", text):
        item = clean_text(raw, 300).strip(" .。:：")
        if not item:
            continue
        if (
            PRODUCT_EDITORIAL_RE.search(item)
            or PRODUCT_URL_RE.search(item)
            or PRODUCT_FILE_RE.search(item)
            or PRODUCT_SENTENCE_RE.search(item)
            or PRODUCT_DATE_LABEL_RE.fullmatch(item)
            or PRODUCT_NAV_PREFIX_RE.search(item)
            or PRODUCT_FRAGMENT_RE.search(item)
            or PRODUCT_GENERIC_RE.fullmatch(item)
            or item.casefold().strip(" .") in PRODUCT_EXACT_NOISE
        ):
            return True
    return False


def _exit_performance(
    events: Sequence[dict[str, Any]], *, listed: bool = False
) -> dict[str, str]:
    latest = sorted(
        events,
        key=lambda row: clean_text(row.get("date"), 20),
        reverse=True,
    )[0] if events else {}
    if latest:
        title = clean_text(latest.get("title"), 180)
        date = clean_text(latest.get("date"), 20)
        event_type = clean_text(latest.get("type"), 80)
        is_listing = listed or any(
            term in f"{event_type} {title}".casefold()
            for term in ("ipo", "listed", "listing", "上市", "挂牌")
        )
        return {
            "status": "已上市" if is_listing else "已发生并购或退出事件",
            "latestDate": date,
            "latestEvent": title,
            "summary": (
                f"最新可核对资本市场记录为{date or '日期未披露'}的"
                f"{title or '资本市场事件'}。"
            ),
            "sourceUrl": clean_text(latest.get("sourceUrl"), 1000),
        }
    if listed:
        return {
            "status": "已上市",
            "latestDate": "",
            "latestEvent": "",
            "summary": "目录状态显示该公司已上市；当前快照未保留可核对的上市事件明细。",
            "sourceUrl": "",
        }
    return {
        "status": "暂无公开退出信息",
        "latestDate": "",
        "latestEvent": "",
        "summary": "当前未发现上市、并购退出或明确退出安排的可核对公开证据。",
        "sourceUrl": "",
    }


'''
    marker = "def _enforce_snapshot_once(\n"
    if "def _contains_product_noise(" not in text:
        if marker not in text:
            raise SystemExit("derived helper insertion marker not found")
        text = text.replace(marker, helper + marker, 1)
        print("derived helpers: applied")

    old_products = '''        original_products = profile.get("products", [])
        products = [
            clean_text(item, 180)
            for item in original_products
            if _valid_product(item, aliases)
        ] if isinstance(original_products, list) else []
        products = list(dict.fromkeys(products))[:16]
        diagnostics["removedProducts"] += max(
            0,
            (len(original_products) if isinstance(original_products, list) else 0)
            - len(products),
        )
        profile["products"] = products
'''
    new_products = '''        original_products = profile.get("products", [])
        original_product_items = [
            clean_text(item, 180)
            for item in original_products
            if clean_text(item, 180)
        ] if isinstance(original_products, list) else []
        products = [
            item
            for item in original_product_items
            if _valid_product(item, aliases)
        ]
        products = list(dict.fromkeys(products))[:16]
        removed_products = [
            item for item in original_product_items if item not in products
        ]
        diagnostics["removedProducts"] += max(
            0,
            len(original_product_items) - len(products),
        )
        profile["products"] = products
'''
    text = replace_once(text, old_products, new_products, "removed product tracking")

    old_technology = '''        raw_technology = clean_text(profile.get("technology", ""), 1400)
        technology = _relevant_clauses(
            raw_technology, aliases, products, limit=900
        )
        if products and (
            not technology
            or PRODUCT_EDITORIAL_RE.search(raw_technology)
            or PRODUCT_URL_RE.search(raw_technology)
            or PRODUCT_FILE_RE.search(raw_technology)
            or PRODUCT_SENTENCE_RE.search(raw_technology)
        ):
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
        profile["technology"] = technology
        research_technology = _relevant_clauses(
            profile.get("researchTechnology", ""), aliases, products, limit=900
        )
        profile["researchTechnology"] = research_technology or technology
'''
    new_technology = '''        raw_technology = clean_text(profile.get("technology", ""), 1400)
        technology = _relevant_clauses(
            raw_technology, aliases, products, limit=900
        )
        removed_in_technology = any(
            _contains_any(raw_technology, (item,))
            for item in removed_products
        )
        rebuild_technology = bool(
            products
            and (
                removed_in_technology
                or _contains_product_noise(raw_technology)
                or not technology
            )
        )
        if rebuild_technology:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
        profile["technology"] = technology
        raw_research_technology = clean_text(
            profile.get("researchTechnology", ""), 1400
        )
        research_technology = _relevant_clauses(
            raw_research_technology, aliases, products, limit=900
        )
        removed_in_research = any(
            _contains_any(raw_research_technology, (item,))
            for item in removed_products
        )
        profile["researchTechnology"] = (
            technology
            if removed_in_research or _contains_product_noise(raw_research_technology)
            else (research_technology or technology)
        )
'''
    text = replace_once(text, old_technology, new_technology, "targeted technology rebuild")

    old_capital = '''        profile["capitalSummary"] = _capital_summary(profile["financing"])
        profile["evidenceScore"] = evidence_score(profile, "company")
'''
    new_capital = '''        profile["capitalSummary"] = _capital_summary(profile["financing"])
        profile["exitPerformance"] = _exit_performance(
            profile["capitalMarkets"],
            listed=bool(spec and spec.status == "已上市"),
        )
        profile["evidenceScore"] = evidence_score(profile, "company")
'''
    text = replace_once(text, old_capital, new_capital, "exit performance recomputation")

    TARGET.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = '''    def test_trims_investor_relations_page_chrome(self) -> None:
'''
    addition = '''    def test_recomputes_derived_fields_after_semantic_removal(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "核心技术与产品包括Claude Platform、工艺革新。",
                    "researchTechnology": "核心技术与产品包括Claude Platform、工艺革新。",
                    "products": ["Claude Platform", "工艺革新"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "capitalSummary": {"eventCount": 0},
                    "exitPerformance": {
                        "status": "已发生并购或退出事件",
                        "latestDate": "2026-07-11",
                        "latestEvent": "旧媒体标题",
                        "summary": "旧媒体标题。",
                        "sourceUrl": "https://example.com/stale",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = semantics.enforce_snapshot(payload, CATALOG)
        company = cleaned["companies"]["anthropic"]
        self.assertEqual(company["products"], ["Claude Platform"])
        self.assertEqual(
            company["technology"],
            "核心技术与产品包括Claude Platform。",
        )
        self.assertEqual(company["researchTechnology"], company["technology"])
        self.assertEqual(
            company["exitPerformance"],
            {
                "status": "暂无公开退出信息",
                "latestDate": "",
                "latestEvent": "",
                "summary": "当前未发现上市、并购退出或明确退出安排的可核对公开证据。",
                "sourceUrl": "",
            },
        )

'''
    if "def test_recomputes_derived_fields_after_semantic_removal" not in text:
        if marker not in text:
            raise SystemExit("derived consistency test marker not found")
        text = text.replace(marker, addition + marker, 1)
        print("derived consistency regression: applied")

    old = '''        self.assertEqual(cleaned["companies"]["anthropic"]["capitalMarkets"], [])
'''
    new = '''        self.assertEqual(cleaned["companies"]["anthropic"]["capitalMarkets"], [])
        self.assertEqual(
            cleaned["companies"]["anthropic"]["exitPerformance"]["status"],
            "暂无公开退出信息",
        )
        self.assertNotIn(
            "工艺革新",
            cleaned["companies"]["galactic-energy"].get("technology", ""),
        )
'''
    if new not in text:
        if old not in text:
            raise SystemExit("production derived assertion marker not found")
        text = text.replace(old, new, 1)
        print("production derived assertions: applied")

    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_semantics()
    patch_tests()


if __name__ == "__main__":
    main()
