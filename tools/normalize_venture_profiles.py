#!/usr/bin/env python3
"""Apply cross-entity consistency rules to generated venture profiles.

The crawler intentionally keeps extraction heuristics permissive enough to work
across heterogeneous official sites. This final deterministic pass removes
company-name fragments, title fragments, event labels and generic product
suffixes from every startup and investment-institution profile before publish.
It also keeps structured research cards and capital conclusions aligned with the
cleaned underlying evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH, evaluate_quality
    from .venture_profile_extraction import (
        clean_text,
        evidence_score,
        parse_catalog,
        sanitize_product_items,
        sanitize_team_members,
    )
except ImportError:
    from crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH, evaluate_quality
    from venture_profile_extraction import (
        clean_text,
        evidence_score,
        parse_catalog,
        sanitize_product_items,
        sanitize_team_members,
    )

ROLE_FRAGMENT_NAMES = {
    "高级副", "执行副", "联席", "首席", "副总裁", "总裁", "董事", "董事长",
    "合伙人", "负责人", "管理层", "高级管理层",
}
ORGANIZATION_SUFFIXES = (
    "业务部", "事业部", "部门", "办公室", "委员会", "研究院", "实验室", "中心", "团队",
)
GENERIC_PRODUCT_NAMES = {
    "机器人", "模型", "平台", "系统", "芯片", "引擎", "终端", "助手", "智能体", "api",
}
PRODUCT_EVENT_TERMS = (
    "大赛", "赛事", "大会", "峰会", "论坛", "展会", "活动", "招聘", "新闻", "发布会",
)
PRODUCT_SPLIT_PATTERN = re.compile(r"[、，,;/]|\s+与\s+|\s+and\s+", re.IGNORECASE)
PRODUCT_SUFFIX_PATTERN = re.compile(
    r"(?:等)?(?:机器人|产品|解决方案)?系列$|(?:等产品|等解决方案)$", re.IGNORECASE
)
FINANCING_ACTION_PATTERN = re.compile(
    r"(?:\braised\b|\bfunding round\b|\bfinancing\b|\binvestment round\b|"
    r"\bseries\s+[a-z0-9]+\b|\bvaluation\b|\blead(?:s|ing)?\s+(?:an?\s+)?investment\b|"
    r"融资|募资|领投|跟投|战略投资|估值|完成.{0,12}(?:轮|融资))",
    re.IGNORECASE,
)
CAPITAL_MARKET_ACTION_PATTERN = re.compile(
    r"(?:\bipo\b|\blisted\b|\blisting\b|\bnasdaq\b|\bnyse\b|\bhkex\b|"
    r"\bpublic market\b|\bacquired\b|\bacquisition\b|\bmerger\b|"
    r"上市|挂牌|交易所|进入公开市场|并购|收购|退出)",
    re.IGNORECASE,
)


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean_text(value, 220).casefold())


def _unique(values: Iterable[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean_text(value, 220)
        key = _compact(item)
        if not item or not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def normalize_product_items(values: Sequence[Any]) -> list[str]:
    """Normalize product labels retained from any previous crawler version."""
    normalized: list[str] = []
    for raw in sanitize_product_items(values):
        for part in PRODUCT_SPLIT_PATTERN.split(clean_text(raw, 600)):
            item = clean_text(part, 180).strip(" >›→-|｜。.!！")
            item = PRODUCT_SUFFIX_PATTERN.sub("", item).strip(" >›→-|｜。.!！")
            compact = _compact(item)
            if not compact or compact in GENERIC_PRODUCT_NAMES:
                continue
            if any(term in item for term in PRODUCT_EVENT_TERMS):
                continue
            normalized.append(item)
    return _unique(normalized, 10)


def normalize_team_members(
    members: Sequence[dict[str, Any]], aliases: Sequence[str]
) -> list[dict[str, str]]:
    """Remove brand fragments, organization labels and title fragments."""
    alias_keys = [_compact(alias) for alias in aliases if _compact(alias)]
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for member in sanitize_team_members(members, aliases):
        name = clean_text(member.get("name"), 120).strip(" ,，:：;；-|｜")
        lowered = name.casefold()
        compact = _compact(name)
        if not compact or lowered in ROLE_FRAGMENT_NAMES:
            continue
        if any(name.endswith(suffix) for suffix in ORGANIZATION_SUFFIXES):
            continue
        if any(
            compact == alias
            or (len(compact) >= 2 and len(compact) < len(alias) and compact in alias)
            for alias in alias_keys
        ):
            continue
        if compact in seen:
            continue
        result.append({
            "name": name,
            "role": clean_text(member.get("role"), 160),
            "summary": clean_text(member.get("summary"), 360),
            "sourceUrl": clean_text(member.get("sourceUrl"), 2000),
        })
        seen.add(compact)
        if len(result) >= 16:
            break
    return result


def _event_has_evidence(event: dict[str, Any], capital_market: bool) -> bool:
    text = clean_text(
        f"{event.get('title', '')} {event.get('summary', '')}", 1200
    )
    if capital_market:
        return bool(CAPITAL_MARKET_ACTION_PATTERN.search(text))
    return bool(
        FINANCING_ACTION_PATTERN.search(text)
        or clean_text(event.get("amount"), 80)
        or clean_text(event.get("round"), 80)
        or any(clean_text(item, 100) for item in event.get("investors", []))
    )


def normalize_capital_events(
    values: Sequence[Any], *, capital_market: bool
) -> list[dict[str, Any]]:
    """Keep only records with an explicit financing, listing or exit action."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict) or not _event_has_evidence(raw, capital_market):
            continue
        title = clean_text(raw.get("title"), 220)
        summary = clean_text(raw.get("summary"), 520)
        source_url = clean_text(raw.get("sourceUrl"), 2000)
        key = f"{clean_text(raw.get('date'), 20)}|{title}|{source_url}".casefold()
        if not title or key in seen:
            continue
        result.append({
            "date": clean_text(raw.get("date"), 20),
            "type": clean_text(raw.get("type"), 60)
            or ("资本市场" if capital_market else "融资"),
            "title": title,
            "summary": summary or title,
            "amount": clean_text(raw.get("amount"), 80),
            "round": clean_text(raw.get("round"), 80),
            "investors": _unique(
                (clean_text(item, 100) for item in raw.get("investors", [])), 12
            ),
            "sourceUrl": source_url,
        })
        seen.add(key)
        if len(result) >= 20:
            break
    return result


def normalize_technology_products(
    values: Sequence[Any], products: Sequence[str]
) -> list[dict[str, Any]]:
    """Keep structured product cards aligned with the final product list."""
    by_name = {
        _compact(item.get("name")): item
        for item in values
        if isinstance(item, dict) and _compact(item.get("name"))
    }
    result: list[dict[str, Any]] = []
    for product in products:
        raw = by_name.get(_compact(product), {})
        description = clean_text(raw.get("description"), 520) or (
            f"公开资料将{product}列为该公司的核心产品或技术平台，具体技术参数以原始来源为准。"
        )
        result.append({
            "name": product,
            "category": clean_text(raw.get("category"), 80) or "技术产品",
            "description": description,
            "technicalHighlights": _unique(
                (clean_text(item, 260) for item in raw.get("technicalHighlights", [])), 6
            ),
            "sourceUrl": clean_text(raw.get("sourceUrl"), 2000),
        })
    return result


def _capital_summary(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latest = events[0] if events else {}
    summary = (
        f"共识别到{len(events)}条可追溯融资或资本投入记录。"
        f"最新记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
        f"{clean_text(latest.get('title'), 180)}。"
        if events
        else "当前公开来源未提供可核对的融资轮次、金额和投资方记录。"
    )
    return {
        "eventCount": len(events),
        "disclosedAmounts": _unique(
            (clean_text(item.get("amount"), 80) for item in events), 12
        ),
        "rounds": _unique((clean_text(item.get("round"), 80) for item in events), 12),
        "majorInvestors": _unique(
            (clean_text(name, 100) for item in events for name in item.get("investors", [])), 20
        ),
        "latestDate": clean_text(latest.get("date"), 20),
        "latestRound": clean_text(latest.get("round"), 80),
        "summary": summary,
    }


def _exit_performance(company_status: str, events: Sequence[dict[str, Any]]) -> dict[str, str]:
    latest = events[0] if events else {}
    text = " ".join(
        clean_text(f"{item.get('type', '')} {item.get('title', '')}", 300)
        for item in events
    )
    if re.search(r"并购|收购|acquired|acquisition|merger", text, re.IGNORECASE):
        status = "已发生并购或退出事件"
    elif company_status == "已上市" or re.search(
        r"上市|ipo|listed|listing|公开市场", text, re.IGNORECASE
    ):
        status = "已上市"
    else:
        status = "暂无公开退出信息"
    if latest:
        summary = (
            f"最新可核对资本市场记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    elif company_status == "已上市":
        summary = "目录标记该公司已上市，尚待交易所、监管文件或公司公告补齐上市地点、代码与上市后表现。"
    else:
        summary = "当前未发现上市、并购退出或明确退出安排的可核对公开证据。"
    return {
        "status": status,
        "latestDate": clean_text(latest.get("date"), 20),
        "latestEvent": clean_text(latest.get("title"), 220),
        "summary": summary,
        "sourceUrl": clean_text(latest.get("sourceUrl"), 2000),
    }


def consistency_errors(
    payload: dict[str, Any],
    company_aliases: dict[str, Sequence[str]],
    institution_aliases: dict[str, Sequence[str]],
) -> list[str]:
    errors: list[str] = []
    for slug, profile in payload.get("companies", {}).items():
        products = profile.get("products", [])
        if products != normalize_product_items(products):
            errors.append(f"company:{slug}:products")
        if int(profile.get("researchModelVersion", 0) or 0) >= 2 and profile.get(
            "technologyProducts", []
        ) != normalize_technology_products(profile.get("technologyProducts", []), products):
            errors.append(f"company:{slug}:technology-products")
        aliases = company_aliases.get(slug, (profile.get("name", ""),))
        if profile.get("team", []) != normalize_team_members(profile.get("team", []), aliases):
            errors.append(f"company:{slug}:team")
        if profile.get("financing", []) != normalize_capital_events(
            profile.get("financing", []), capital_market=False
        ):
            errors.append(f"company:{slug}:financing")
        if profile.get("capitalMarkets", []) != normalize_capital_events(
            profile.get("capitalMarkets", []), capital_market=True
        ):
            errors.append(f"company:{slug}:capital-markets")
    for slug, profile in payload.get("institutions", {}).items():
        aliases = institution_aliases.get(slug, (profile.get("name", ""),))
        if profile.get("team", []) != normalize_team_members(profile.get("team", []), aliases):
            errors.append(f"institution:{slug}:team")
    return errors


def normalize_payload(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    companies, institutions = parse_catalog(catalog_text)
    company_aliases = {item.slug: item.aliases for item in companies}
    company_status = {item.slug: item.status for item in companies}
    institution_aliases = {item.slug: item.aliases for item in institutions}
    stats = {
        "companyTeams": 0,
        "companyProducts": 0,
        "companyFinancing": 0,
        "companyCapitalMarkets": 0,
        "institutionTeams": 0,
    }

    for slug, profile in payload.get("companies", {}).items():
        aliases = company_aliases.get(slug, (profile.get("name", ""),))
        old_team = list(profile.get("team", []))
        old_products = list(profile.get("products", []))
        old_financing = list(profile.get("financing", []))
        old_capital_markets = list(profile.get("capitalMarkets", []))
        profile["team"] = normalize_team_members(old_team, aliases)
        profile["products"] = normalize_product_items(old_products)
        profile["financing"] = normalize_capital_events(old_financing, capital_market=False)
        profile["capitalMarkets"] = normalize_capital_events(
            old_capital_markets, capital_market=True
        )
        if int(profile.get("researchModelVersion", 0) or 0) >= 2:
            profile["technologyProducts"] = normalize_technology_products(
                profile.get("technologyProducts", []), profile["products"]
            )
            profile["capitalSummary"] = _capital_summary(profile["financing"])
            profile["exitPerformance"] = _exit_performance(
                company_status.get(slug, ""), profile["capitalMarkets"]
            )
        stats["companyTeams"] += max(0, len(old_team) - len(profile["team"]))
        stats["companyProducts"] += max(0, len(old_products) - len(profile["products"]))
        stats["companyFinancing"] += max(0, len(old_financing) - len(profile["financing"]))
        stats["companyCapitalMarkets"] += max(
            0, len(old_capital_markets) - len(profile["capitalMarkets"])
        )
        profile["evidenceScore"] = evidence_score(profile, "company")

    for slug, profile in payload.get("institutions", {}).items():
        aliases = institution_aliases.get(slug, (profile.get("name", ""),))
        old_team = list(profile.get("team", []))
        profile["team"] = normalize_team_members(old_team, aliases)
        stats["institutionTeams"] += max(0, len(old_team) - len(profile["team"]))
        profile["evidenceScore"] = evidence_score(profile, "institution")

    core_quality = evaluate_quality(
        payload.get("companies", {}),
        payload.get("institutions", {}),
        len(companies),
        len(institutions),
        payload.get("sourceStatus", []),
    )
    existing_quality = (
        dict(payload.get("qualityGate", {}))
        if isinstance(payload.get("qualityGate"), dict)
        else {}
    )
    quality = dict(existing_quality)
    for key, value in core_quality.items():
        if key not in {"checks", "passed"}:
            quality[key] = value
    checks = (
        dict(existing_quality.get("checks", {}))
        if isinstance(existing_quality.get("checks"), dict)
        else {}
    )
    if isinstance(core_quality.get("checks"), dict):
        checks.update(core_quality["checks"])

    errors = consistency_errors(payload, company_aliases, institution_aliases)
    checks["profileConsistency"] = {
        "actual": len(errors), "required": 0, "passed": not errors
    }
    if int(payload.get("researchModelVersion", 0) or 0) >= 2:
        enriched_companies = sum(
            isinstance(profile.get("projectBackground"), dict)
            and isinstance(profile.get("technologyProducts"), list)
            and isinstance(profile.get("capitalSummary"), dict)
            and isinstance(profile.get("exitPerformance"), dict)
            for profile in payload.get("companies", {}).values()
        )
        enriched_institutions = sum(
            isinstance(profile.get("recentYearSummary"), dict)
            and isinstance(profile.get("classicCases"), list)
            for profile in payload.get("institutions", {}).values()
        )
        checks["companyResearchEnrichment"] = {
            "actual": enriched_companies,
            "required": len(payload.get("companies", {})),
            "passed": enriched_companies == len(payload.get("companies", {})),
        }
        checks["institutionResearchEnrichment"] = {
            "actual": enriched_institutions,
            "required": len(payload.get("institutions", {})),
            "passed": enriched_institutions == len(payload.get("institutions", {})),
        }
    quality["checks"] = checks
    quality["consistencyErrors"] = errors[:50]
    quality["passed"] = all(
        bool(check.get("passed")) for check in checks.values() if isinstance(check, dict)
    )
    payload["qualityGate"] = quality
    return payload, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    original = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    catalog_text = args.catalog.read_text(encoding="utf-8")
    normalized, stats = normalize_payload(payload, catalog_text)
    normalized_text = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    already_normalized = original == normalized_text
    quality = normalized.get("qualityGate", {})

    if args.check:
        passed = bool(quality.get("passed", False)) and already_normalized
        print(json.dumps({
            "passed": passed,
            "alreadyNormalized": already_normalized,
            "stats": stats,
            "qualityGate": quality,
        }, ensure_ascii=False))
        return 0 if passed else 1

    args.input.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "stats": stats,
        "passed": quality.get("passed", False),
        "changed": not already_normalized,
    }, ensure_ascii=False))
    return 0 if quality.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
