#!/usr/bin/env python3
"""Apply cross-entity consistency rules to generated venture profiles.

The crawler intentionally keeps extraction heuristics permissive enough to work
across heterogeneous official sites. This final deterministic pass removes
company-name fragments, title fragments, event labels and generic product
suffixes from every startup and investment-institution profile before publish.
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
    "高级副",
    "执行副",
    "联席",
    "首席",
    "副总裁",
    "总裁",
    "董事",
    "董事长",
    "合伙人",
    "负责人",
    "管理层",
    "高级管理层",
}

ORGANIZATION_SUFFIXES = (
    "业务部",
    "事业部",
    "部门",
    "办公室",
    "委员会",
    "研究院",
    "实验室",
    "中心",
    "团队",
)

GENERIC_PRODUCT_NAMES = {
    "机器人",
    "模型",
    "平台",
    "系统",
    "芯片",
    "引擎",
    "终端",
    "助手",
    "智能体",
    "api",
}

PRODUCT_EVENT_TERMS = (
    "大赛",
    "赛事",
    "大会",
    "峰会",
    "论坛",
    "展会",
    "活动",
    "招聘",
    "新闻",
    "发布会",
)

PRODUCT_SPLIT_PATTERN = re.compile(r"[、，,;/]|\s+与\s+|\s+and\s+", re.IGNORECASE)
PRODUCT_SUFFIX_PATTERN = re.compile(
    r"(?:等)?(?:机器人|产品|解决方案)?系列$|(?:等产品|等解决方案)$",
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
        result.append(
            {
                "name": name,
                "role": clean_text(member.get("role"), 160),
                "summary": clean_text(member.get("summary"), 320),
                "sourceUrl": clean_text(member.get("sourceUrl"), 2000),
            }
        )
        seen.add(compact)
        if len(result) >= 16:
            break
    return result


def consistency_errors(
    payload: dict[str, Any],
    company_aliases: dict[str, Sequence[str]],
    institution_aliases: dict[str, Sequence[str]],
) -> list[str]:
    errors: list[str] = []
    for slug, profile in payload.get("companies", {}).items():
        if profile.get("products", []) != normalize_product_items(profile.get("products", [])):
            errors.append(f"company:{slug}:products")
        aliases = company_aliases.get(slug, (profile.get("name", ""),))
        if profile.get("team", []) != normalize_team_members(profile.get("team", []), aliases):
            errors.append(f"company:{slug}:team")
    for slug, profile in payload.get("institutions", {}).items():
        aliases = institution_aliases.get(slug, (profile.get("name", ""),))
        if profile.get("team", []) != normalize_team_members(profile.get("team", []), aliases):
            errors.append(f"institution:{slug}:team")
    return errors


def normalize_payload(payload: dict[str, Any], catalog_text: str) -> tuple[dict[str, Any], dict[str, int]]:
    companies, institutions = parse_catalog(catalog_text)
    company_aliases = {item.slug: item.aliases for item in companies}
    institution_aliases = {item.slug: item.aliases for item in institutions}
    stats = {"companyTeams": 0, "companyProducts": 0, "institutionTeams": 0}

    for slug, profile in payload.get("companies", {}).items():
        aliases = company_aliases.get(slug, (profile.get("name", ""),))
        old_team = list(profile.get("team", []))
        old_products = list(profile.get("products", []))
        profile["team"] = normalize_team_members(old_team, aliases)
        profile["products"] = normalize_product_items(old_products)
        stats["companyTeams"] += max(0, len(old_team) - len(profile["team"]))
        stats["companyProducts"] += max(0, len(old_products) - len(profile["products"]))
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
        "actual": len(errors),
        "required": 0,
        "passed": not errors,
    }
    quality["checks"] = checks
    quality["consistencyErrors"] = errors[:50]
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict)
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
        print(
            json.dumps(
                {
                    "passed": passed,
                    "alreadyNormalized": already_normalized,
                    "stats": stats,
                    "qualityGate": quality,
                },
                ensure_ascii=False,
            )
        )
        return 0 if passed else 1

    args.input.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "stats": stats,
                "passed": quality.get("passed", False),
                "changed": not already_normalized,
            },
            ensure_ascii=False,
        )
    )
    return 0 if quality.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
