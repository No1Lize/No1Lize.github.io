#!/usr/bin/env python3
"""Production entrypoint for enriched three-market company profiles."""

from __future__ import annotations

try:
    from . import market_profile_enrichment as enrichment
    from . import refresh_market_profiles as runner
except ImportError:
    import market_profile_enrichment as enrichment
    import refresh_market_profiles as runner

_original_crawl_item = runner.crawl_item
_original_parse_tonghuashun = runner.market.parse_tonghuashun_html


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
    if region:
        parsed.setdefault("company", {})["region"] = region
    return parsed


def crawl_item(item, previous):
    profile, status = _original_crawl_item(item, previous)
    profile = enrichment.enrich_profile(
        item["identity"],
        profile,
        runner.neutral_fetch_text,
    )
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
