#!/usr/bin/env python3
"""Probe every browser-managed source without mutating the public snapshot.

This command uses the same runtime specs and adapters as the scheduled crawler,
but returns diagnostics only. Network errors, login walls and rate limits remain
explicit source-level errors; one failing site never prevents other sources from
being probed.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    from . import adaptive_public_sources as adaptive
    from . import crawl_articles as crawler
    from . import crawl_with_source_categories as categories
    from . import crawl_with_tracking as tracking
    from . import generic_web_sources as generic
    from . import robust_web_fallback as robust
    from . import strict_tracking_config
except ImportError:
    import adaptive_public_sources as adaptive
    import crawl_articles as crawler
    import crawl_with_source_categories as categories
    import crawl_with_tracking as tracking
    import generic_web_sources as generic
    import robust_web_fallback as robust
    import strict_tracking_config


TRACKING_PATH = crawler.ROOT / "config" / "user_tracking.json"


def _enabled_browser_source_count(config: dict[str, Any]) -> int:
    return sum(
        1
        for raw in config.get("sources", [])
        if isinstance(raw, dict)
        and raw.get("enabled", True) is not False
        and (tracking._clean(raw.get("sourceType"), 30) or "listing-search") != "sec"
    )


def probe_spec(
    spec: dict[str, Any],
    user_agent: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adapter = str(spec.get("adapter") or "")
    if adapter == "rss":
        return crawler._crawl_config_source(spec, user_agent)
    if adapter != "generic_web":
        return crawler._crawl_config_source(spec, user_agent)
    if categories._direct_only_generic_source(spec):
        return generic.crawl_generic_source(spec, user_agent, crawler)
    return adaptive.crawl_adaptive_source(
        spec,
        user_agent,
        crawler,
        generic,
        robust,
    )


def probe_sources(
    config: dict[str, Any],
    *,
    workers: int = 4,
    source_id: str = "",
    user_agent: str = "",
) -> dict[str, Any]:
    sanitized = strict_tracking_config.sanitize_tracking_config(config)
    tracks = tracking._enabled_tracks(sanitized)
    specs, sec_specs = categories._custom_sources(sanitized, tracks)
    if source_id:
        specs = [spec for spec in specs if str(spec.get("id")) == source_id]
    user_agent = user_agent or crawler.DEFAULT_USER_AGENT

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(8, workers))) as executor:
        future_by_id = {
            executor.submit(probe_spec, spec, user_agent): str(spec.get("id") or "")
            for spec in specs
        }
        for future in as_completed(future_by_id):
            runtime_id = future_by_id[future]
            try:
                articles, status = future.result()
            except Exception as exc:
                articles = []
                status = {
                    "id": runtime_id,
                    "name": runtime_id,
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                    "failed": 1,
                    "platform": "用户来源",
                    "error": f"{type(exc).__name__}: {exc}",
                    "adapter": "probe-exception",
                }
            results.append(
                {
                    "status": status,
                    "articles": [
                        {
                            "title": article.get("title"),
                            "publishedAt": article.get("publishedAt"),
                            "url": (
                                article.get("source", {}).get("url")
                                if isinstance(article.get("source"), dict)
                                else ""
                            ),
                        }
                        for article in articles[:10]
                    ],
                }
            )

    results.sort(key=lambda item: str(item.get("status", {}).get("id", "")))
    browser_count = _enabled_browser_source_count(sanitized)
    routed_count = len(specs)
    return {
        "passed": (
            bool(source_id)
            or (
                routed_count == browser_count
                and not any(
                    item.get("status", {}).get("adapter") == "probe-exception"
                    for item in results
                )
            )
        ),
        "enabledBrowserSources": browser_count,
        "routedRuntimeSources": routed_count,
        "configuredSecTickers": sorted(sec_specs),
        "productiveSources": sum(
            int(item.get("status", {}).get("accepted", 0) or 0) > 0
            or int(item.get("status", {}).get("discoveredAccepted", 0) or 0) > 0
            for item in results
        ),
        "diagnosedSources": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--source-id", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    config = json.loads(args.tracking.read_text(encoding="utf-8"))
    report = probe_sources(
        config,
        workers=args.workers,
        source_id=args.source_id,
        user_agent=os.environ.get("SEC_USER_AGENT", "").strip(),
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
