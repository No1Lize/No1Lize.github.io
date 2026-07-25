#!/usr/bin/env python3
"""Bounded concurrent runner for ``crawl_market_profiles``.

Each company remains an isolated crawl unit. Slow or blocked sites cannot stall
all three markets, while output ordering remains deterministic and prior valid
snapshots continue to be preserved by the underlying crawler.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

try:
    from . import crawl_market_profiles as market
except ImportError:
    import crawl_market_profiles as market

MAX_WORKERS = 5


def single_attempt_fetch(url: str) -> str:
    return market.fetch_text(url, attempts=1)


def build_snapshot_concurrent(
    config: dict[str, Any],
    previous_snapshot: dict[str, Any],
) -> dict[str, Any]:
    items = market.configured_companies(config)
    previous_profiles = previous_snapshot.get("profiles", {})
    if not isinstance(previous_profiles, dict):
        previous_profiles = {}

    indexed_results: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(items)))) as pool:
        futures = {
            pool.submit(
                market.crawl_company,
                item,
                previous_profiles.get(item["identity"].slug),
                single_attempt_fetch,
            ): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            index = futures[future]
            item = items[index]
            try:
                indexed_results[index] = future.result()
            except Exception as exc:  # noqa: BLE001 - retain an isolated status row.
                identity = item["identity"]
                previous = previous_profiles.get(identity.slug)
                profile = previous or {
                    "slug": identity.slug,
                    "market": identity.market,
                    "ticker": identity.ticker,
                    "thsCode": identity.ths_code,
                    "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "status": "error",
                    "company": {"name": item["name"]},
                    "priceHistory": [],
                    "metrics": [],
                    "financialSeries": [],
                    "sources": {
                        "tonghuashun": market.stockpage_url(identity),
                        "price": market.kline_url(identity),
                    },
                    "warnings": [f"并发任务失败：{type(exc).__name__}: {exc}"],
                }
                if previous:
                    profile = {
                        **previous,
                        "status": "partial",
                        "warnings": [
                            *previous.get("warnings", []),
                            f"本轮并发任务失败：{type(exc).__name__}: {exc}",
                        ][-8:],
                    }
                indexed_results[index] = (
                    profile,
                    {
                        "slug": identity.slug,
                        "status": profile.get("status", "error"),
                        "profileAccepted": False,
                        "pricePoints": len(profile.get("priceHistory", [])),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )

    profiles: dict[str, Any] = {}
    statuses: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        profile, status = indexed_results[index]
        profiles[item["identity"].slug] = profile
        statuses.append(status)

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profiles": profiles,
        "sourceStatus": statuses,
    }


def main() -> int:
    config = market.load_json(market.CONFIG_PATH, {})
    previous = market.load_json(market.OUTPUT_PATH, {"profiles": {}})
    snapshot = build_snapshot_concurrent(config, previous)
    market.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    market.OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for status in snapshot["sourceStatus"]:
        key = status.get("status", "unknown")
        counts[key] = counts.get(key, 0) + 1
    print(f"market profiles: {len(snapshot['profiles'])}; statuses={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
