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
    runner.crawl_item = crawl_item
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
