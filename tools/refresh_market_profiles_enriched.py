#!/usr/bin/env python3
"""Production entrypoint for enriched three-market company profiles."""

from __future__ import annotations

import re

try:
    from . import market_profile_enrichment as enrichment
    from . import refresh_market_profiles as runner
except ImportError:
    import market_profile_enrichment as enrichment
    import refresh_market_profiles as runner

_original_crawl_item = runner.crawl_item
_original_parse_tonghuashun = runner.market.parse_tonghuashun_html

_NAVIGATION_LABELS = (
    "所属地域",
    "所属地区",
    "经营分析",
    "财务分析",
    "公司资料",
    "公司概况",
    "主营业务",
    "营业收入构成",
    "总市值",
    "行情走势",
    "新闻公告",
)


def navigation_noise(value: object) -> bool:
    compact = re.sub(r"[\s，。；;:：|\-—_/]+", "", str(value or ""))
    if not compact:
        return True
    hits = sum(label in compact for label in _NAVIGATION_LABELS)
    if hits >= 2 and len(compact) < 80:
        return True
    if hits >= 1 and len(compact) < 18:
        return True
    return bool(re.fullmatch(r"(?:--?|暂无|待同步|亿|万|元|股)+", compact))


def parse_tonghuashun_html(raw_html, identity, configured_name):
    parsed = _original_parse_tonghuashun(raw_html, identity, configured_name)
    parser = runner.market.TextCollector()
    parser.feed(raw_html)
    text = parser.text()
    region = runner.robust_labeled_value(
        text,
        ["所属地域", "所属地区", "所在地区", "国家/地区", "注册地区"],
        40,
    )
    if region and not navigation_noise(region):
        parsed.setdefault("company", {})["region"] = region
    return parsed


def preserve_company_copy(profile, previous):
    company = profile.setdefault("company", {})
    previous_company = previous.get("company", {}) if isinstance(previous, dict) else {}
    for field in ("description", "mainBusiness", "industry"):
        value = company.get(field)
        if navigation_noise(value):
            previous_value = previous_company.get(field)
            if previous_value and not navigation_noise(previous_value):
                company[field] = previous_value
            else:
                company.pop(field, None)
    profile["company"] = company
    return profile


def crawl_item(item, previous):
    profile, status = _original_crawl_item(item, previous)
    profile = preserve_company_copy(profile, previous)
    profile = enrichment.enrich_profile(
        item["identity"],
        profile,
        runner.neutral_fetch_text,
    )
    profile = preserve_company_copy(profile, previous)
    status["status"] = profile.get("status", status.get("status", "partial"))
    status["pricePoints"] = len(profile.get("priceHistory", []))
    status["marketCapAccepted"] = any(
        metric.get("id") == "marketCap"
        for metric in profile.get("metrics", [])
        if isinstance(metric, dict)
    )
    return profile, status


def main() -> int:
    runner.market.parse_tonghuashun_html = parse_tonghuashun_html
    runner.crawl_item = crawl_item
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
