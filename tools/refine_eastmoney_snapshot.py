#!/usr/bin/env python3
"""Keep only focused technology intelligence from Eastmoney detail pages.

The direct crawler correctly follows Eastmoney channel pages into concrete
``/a/<timestamp-id>.html`` stories. This final snapshot pass removes two classes
that are still unsuitable for the intelligence dashboard:

* daily/weekly roundup pages that mention many unrelated companies and can create
  false primary-company attribution;
* general social or political news with no tracked company or technology signal.

This module deliberately runs after entity migration and does not replace the
existing title, quote-link, or lead-paragraph attribution logic.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

try:
    from .crawl_articles import OUTPUT_PATH, ROOT, clean_text
    from .eastmoney_entities import build_listed_entity_index
except ImportError:
    from crawl_articles import OUTPUT_PATH, ROOT, clean_text
    from eastmoney_entities import build_listed_entity_index


TRACKING_PATH = ROOT / "config" / "user_tracking.json"
GENERIC_COMPANIES = {"", "科技产业", "东方财富", "未识别", "unknown"}
ROUNDUP_PATTERNS = (
    r"(?:东方财富|财经|市场|全球市场|A股|港股|美股).{0,8}(?:早报|早餐|晚报|日报|周报)",
    r"(?:早报|早餐|晚报|日报|周报).{0,8}(?:新闻联播|要闻|速览|一览)",
    r"(?:今日|本周|一周).{0,6}(?:要闻|大事|财经|市场).{0,6}(?:回顾|汇总|速览|一览)?",
    r"(?:盘前|盘中|盘后).{0,6}(?:必读|要闻|速览|播报)",
    r"(?:新闻|资讯|行情).{0,6}(?:汇总|合集|集锦|滚动)",
    r"新闻联播",
    r"财经日历",
)
TECH_PATTERNS = (
    r"(?<![a-z0-9])ai(?![a-z0-9])",
    r"(?<![a-z0-9])agi(?![a-z0-9])",
    r"artificial intelligence",
    r"large language model",
    r"foundation model",
    r"generative ai",
    r"machine learning",
    r"deep learning",
    r"semiconductor",
    r"(?<![a-z0-9])gpu(?![a-z0-9])",
    r"robot(?:ics|axi)?",
    r"autonomous driv",
    r"quantum comput",
    r"blockchain",
    r"web3",
    r"biotech",
    r"genomic",
    r"brain.?computer interface",
    r"人工智能",
    r"大模型",
    r"基础模型",
    r"生成式AI",
    r"生成式人工智能",
    r"智能体",
    r"算力",
    r"芯片",
    r"半导体",
    r"机器人",
    r"自动驾驶",
    r"无人驾驶",
    r"具身智能",
    r"新能源",
    r"动力电池",
    r"固态电池",
    r"储能",
    r"可控核聚变",
    r"量子计算",
    r"量子通信",
    r"商业航天",
    r"卫星互联网",
    r"运载火箭",
    r"生物科技",
    r"创新药",
    r"基因编辑",
    r"合成生物",
    r"脑机接口",
    r"区块链",
    r"新材料",
    r"智能制造",
    r"工业机器人",
    r"先进封装",
    r"光刻机",
    r"云计算",
    r"数据中心",
)


def _clean(value: Any, limit: int = 1000) -> str:
    return clean_text(str(value or ""))[:limit]


def _host(url: str) -> str:
    host = (urlsplit(_clean(url, 500)).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def is_eastmoney_article(article: dict[str, Any]) -> bool:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_id = _clean(article.get("sourceId"), 120)
    source_name = _clean(source.get("name"), 120)
    return (
        source_id.startswith("official-user-东方财富")
        or "东方财富" in source_name
        or _host(_clean(source.get("url"), 500)).endswith("eastmoney.com")
    )


def is_roundup_title(title: str) -> bool:
    normalized = _clean(title, 300)
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in ROUNDUP_PATTERNS)


def _technology_hits(text: str) -> set[str]:
    normalized = _clean(text, 1500).casefold()
    return {
        pattern
        for pattern in TECH_PATTERNS
        if re.search(pattern, normalized, flags=re.IGNORECASE)
    }


def _company_aliases(entities: Iterable[dict[str, str]]) -> set[str]:
    aliases: set[str] = set()
    for entity in entities:
        for key in ("name", "englishName"):
            value = _clean(entity.get(key), 100)
            if len(value) >= 2:
                aliases.add(value.casefold())
    return aliases


def _focused_company_match(article: dict[str, Any], aliases: set[str]) -> bool:
    title = _clean(article.get("title"), 300).casefold()
    summary = _clean(article.get("summary"), 1200).casefold()
    company = _clean(article.get("company"), 100)
    if company not in GENERIC_COMPANIES:
        folded_company = company.casefold()
        if folded_company in title or folded_company in summary[:600]:
            return True
    return any(alias in title for alias in aliases)


def is_relevant_eastmoney_article(
    article: dict[str, Any], aliases: set[str]
) -> tuple[bool, str]:
    title = _clean(article.get("title"), 300)
    summary = _clean(article.get("summary"), 1500)
    if is_roundup_title(title):
        return False, "roundup"
    if _focused_company_match(article, aliases):
        return True, "tracked-company"
    title_hits = _technology_hits(title)
    if title_hits:
        return True, "technology-title"
    summary_hits = _technology_hits(summary)
    if len(summary_hits) >= 2:
        return True, "technology-summary"
    return False, "unrelated"


def refine_snapshot(
    snapshot: dict[str, Any], tracking: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    entities = build_listed_entity_index(tracking)
    aliases = _company_aliases(entities)
    kept: list[dict[str, Any]] = []
    removed_roundups: list[str] = []
    removed_unrelated: list[str] = []
    eastmoney_seen = 0
    eastmoney_kept = 0

    for raw in snapshot.get("articles", []):
        if not isinstance(raw, dict):
            continue
        article = dict(raw)
        if not is_eastmoney_article(article):
            kept.append(article)
            continue
        eastmoney_seen += 1
        relevant, reason = is_relevant_eastmoney_article(article, aliases)
        if relevant:
            kept.append(article)
            eastmoney_kept += 1
        elif reason == "roundup":
            removed_roundups.append(_clean(article.get("title"), 300))
        else:
            removed_unrelated.append(_clean(article.get("title"), 300))

    result = dict(snapshot)
    result["articles"] = kept
    result["articleCount"] = len(kept)

    for status in result.get("sourceStatus", []):
        if not isinstance(status, dict):
            continue
        status_id = _clean(status.get("id"), 120)
        if status_id.startswith("official-user-东方财富"):
            status["accepted"] = eastmoney_kept
            if eastmoney_kept == 0 and status.get("status") in {"ok", "partial"}:
                status["status"] = "empty"

    report = {
        "eastmoneySeen": eastmoney_seen,
        "eastmoneyKept": eastmoney_kept,
        "removedRoundups": removed_roundups,
        "removedUnrelated": removed_unrelated,
    }
    return result, report


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return
    path.write_text(serialized, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    tracking = json.loads(args.tracking.read_text(encoding="utf-8"))
    refined, report = refine_snapshot(snapshot, tracking)
    write_snapshot(args.snapshot, refined)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
