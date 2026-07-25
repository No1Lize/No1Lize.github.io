#!/usr/bin/env python3
"""Validate that every enabled browser-managed source entered a known adapter.

A public crawler cannot guarantee content behind authentication, CAPTCHAs or
paywalls. It can guarantee that no configured source is silently ignored. This
validator checks routing and diagnostic coverage rather than pretending every
website must return articles on every run.
"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from . import crawl_articles as crawler
    from . import crawl_with_source_categories as categories
    from . import crawl_with_tracking as tracking
    from . import strict_tracking_config
except ImportError:
    import crawl_articles as crawler
    import crawl_with_source_categories as categories
    import crawl_with_tracking as tracking
    import strict_tracking_config


TRACKING_PATH = crawler.ROOT / "config" / "user_tracking.json"
SNAPSHOT_PATH = crawler.OUTPUT_PATH


def _enabled_raw_sources(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        raw
        for raw in config.get("sources", [])
        if isinstance(raw, dict) and raw.get("enabled", True) is not False
    ]


def _runtime_id(raw: dict[str, Any], index: int) -> str:
    name = tracking._clean(raw.get("name"), 80)
    return f"user-source-{tracking._slug(raw.get('id') or name or index)}"


def evaluate_coverage(
    tracking_config: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    sanitized = strict_tracking_config.sanitize_tracking_config(tracking_config)
    enabled_sources = _enabled_raw_sources(sanitized)
    tracks = tracking._enabled_tracks(sanitized)
    runtime_specs, sec_specs = categories._custom_sources(sanitized, tracks)
    runtime_by_id = {
        str(spec.get("id")): spec for spec in runtime_specs if spec.get("id")
    }
    status_by_id = {
        str(status.get("id")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict) and status.get("id")
    }

    expected_ids: list[str] = []
    missing_statuses: list[str] = []
    unroutable_sources: list[dict[str, str]] = []
    adapter_mismatches: list[dict[str, str]] = []
    attempted = 0
    productive = 0

    for index, raw in enumerate(enabled_sources):
        source_type = tracking._clean(raw.get("sourceType"), 30) or "listing-search"
        if source_type == "sec":
            ticker = tracking._clean(raw.get("ticker"), 30).upper()
            if not ticker and not tracking._clean(raw.get("listedCompanyId"), 100):
                unroutable_sources.append(
                    {
                        "id": str(raw.get("id") or index),
                        "reason": "SEC source requires a ticker or listedCompanyId",
                    }
                )
            continue
        source_id = _runtime_id(raw, index)
        url = tracking._clean(raw.get("url"), 500)
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            unroutable_sources.append(
                {
                    "id": str(raw.get("id") or index),
                    "reason": "public source requires an http(s) URL",
                }
            )
            continue
        if source_id not in runtime_by_id:
            unroutable_sources.append(
                {
                    "id": str(raw.get("id") or index),
                    "reason": "enabled source did not produce a runtime adapter spec",
                }
            )

    for spec in runtime_specs:
        source_id = str(spec.get("id") or "")
        if not source_id:
            continue
        expected_ids.append(source_id)
        status = status_by_id.get(source_id)
        if status is None:
            missing_statuses.append(source_id)
            continue
        attempted += 1
        if int(status.get("accepted", 0) or 0) > 0:
            productive += 1
        if (
            spec.get("adapter") == "generic_web"
            and not categories._direct_only_generic_source(spec)
            and status.get("adapter") != "adaptive-public-v1"
        ):
            adapter_mismatches.append(
                {
                    "id": source_id,
                    "expected": "adaptive-public-v1",
                    "actual": str(status.get("adapter") or "missing"),
                }
            )

    if sec_specs:
        expected_ids.append("sec")
        if "sec" not in status_by_id:
            missing_statuses.append("sec")
        else:
            attempted += 1
            if int(status_by_id["sec"].get("accepted", 0) or 0) > 0:
                productive += 1

    duplicates = sorted(
        source_id for source_id in set(expected_ids) if expected_ids.count(source_id) > 1
    )
    errors: list[str] = []
    if unroutable_sources:
        errors.append("enabled sources could not be converted into runtime adapters")
    if missing_statuses:
        errors.append("enabled sources missing sourceStatus records")
    if adapter_mismatches:
        errors.append("public websites bypassed the adaptive adapter")
    if duplicates:
        errors.append("configured sources resolve to duplicate runtime ids")

    return {
        "passed": not errors,
        "enabledConfiguredSources": len(enabled_sources),
        "expectedRuntimeStatuses": len(set(expected_ids)),
        "attemptedRuntimeStatuses": attempted,
        "productiveRuntimeStatuses": productive,
        "unroutableSources": unroutable_sources,
        "missingStatuses": sorted(set(missing_statuses)),
        "adapterMismatches": adapter_mismatches,
        "duplicateRuntimeIds": duplicates,
        "errors": errors,
    }


def main() -> int:
    tracking_config = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    report = evaluate_coverage(tracking_config, snapshot)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
