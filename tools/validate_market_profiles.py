#!/usr/bin/env python3
"""Validate the committed three-market company profile snapshot."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

try:
    from . import crawl_market_profiles as market
except ImportError:
    import crawl_market_profiles as market

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
SNAPSHOT_PATH = ROOT / "public" / "data" / "market_profiles.json"
ALLOWED_STATUS = {"ok", "partial", "error", "pending"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    config = load(CONFIG_PATH)
    snapshot = load(SNAPSHOT_PATH)
    profiles = snapshot.get("profiles")
    if not isinstance(profiles, dict):
        return ["profiles must be an object"], warnings

    expected: dict[str, market.CompanyIdentity] = {}
    for raw in config.get("listedCompanies", []):
        if not isinstance(raw, dict) or raw.get("enabled") is False:
            continue
        identity = market.company_identity(
            str(raw.get("market") or ""),
            raw.get("ticker"),
            str(raw.get("catalogSlug") or "").strip(),
        )
        if identity:
            expected[identity.slug] = identity

    missing = sorted(set(expected) - set(profiles))
    if missing:
        errors.append("missing enabled profiles: " + ", ".join(missing))

    for slug, identity in expected.items():
        profile = profiles.get(slug)
        if not isinstance(profile, dict):
            continue
        if profile.get("market") != identity.market:
            errors.append(f"{slug}: market mismatch")
        if profile.get("ticker") != identity.ticker:
            errors.append(f"{slug}: ticker mismatch")
        if profile.get("status") not in ALLOWED_STATUS:
            errors.append(f"{slug}: invalid status {profile.get('status')!r}")

        company = profile.get("company")
        if not isinstance(company, dict) or not str(company.get("name") or "").strip():
            errors.append(f"{slug}: missing company name")
            company = {}
        region = str(company.get("region") or "").strip()
        if not region:
            errors.append(f"{slug}: missing normalized company region")
        description = str(company.get("description") or "").strip()
        if len(description) > 420:
            errors.append(f"{slug}: company description exceeds 420 characters")
        elif description and len(description) < 40:
            warnings.append(f"{slug}: company description is shorter than 40 characters")

        sources = profile.get("sources")
        if not isinstance(sources, dict):
            errors.append(f"{slug}: missing sources")
        else:
            ths = str(sources.get("tonghuashun") or "")
            if not ths.startswith("https://stockpage.10jqka.com.cn/"):
                errors.append(f"{slug}: invalid Tonghuashun source")

        metrics = profile.get("metrics", [])
        if not isinstance(metrics, list):
            errors.append(f"{slug}: metrics must be an array")
            metrics = []
        metric_ids: set[str] = set()
        market_cap_value = ""
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            metric_id = str(metric.get("id") or "")
            if metric_id in metric_ids:
                errors.append(f"{slug}: duplicate metric id {metric_id}")
            metric_ids.add(metric_id)
            value = str(metric.get("value") or "")
            if "%%" in value:
                errors.append(f"{slug}: duplicate percent marker")
            if metric_id == "marketCap":
                market_cap_value = value
        if market_cap_value and not re.search(r"\d", market_cap_value):
            errors.append(f"{slug}: market cap contains no numeric value")
        if not market_cap_value:
            warnings.append(f"{slug}: total market cap is unavailable")

        listed_at = str(company.get("listedAt") or "")
        dates: list[str] = []
        seen: set[str] = set()
        points = profile.get("priceHistory", [])
        if not isinstance(points, list):
            errors.append(f"{slug}: priceHistory must be an array")
            continue
        for index, point in enumerate(points):
            if not isinstance(point, dict):
                errors.append(f"{slug}: price point {index} is not an object")
                continue
            point_date = str(point.get("date") or "")
            if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", point_date):
                errors.append(f"{slug}: invalid price date {point_date!r}")
                continue
            if point_date in seen:
                errors.append(f"{slug}: duplicate price date {point_date}")
            seen.add(point_date)
            dates.append(point_date)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", listed_at) and point_date < listed_at:
                errors.append(f"{slug}: price date {point_date} precedes listing {listed_at}")
            try:
                open_ = float(point["open"])
                close = float(point["close"])
                high = float(point["high"])
                low = float(point["low"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{slug}: invalid OHLC at {point_date}")
                continue
            if not all(math.isfinite(value) and value >= 0 for value in (open_, close, high, low)):
                errors.append(f"{slug}: non-finite or negative OHLC at {point_date}")
            if high < max(open_, close, low) or low > min(open_, close, high):
                errors.append(f"{slug}: inconsistent OHLC at {point_date}")
        if dates != sorted(dates):
            errors.append(f"{slug}: price dates are not sorted")
        if len(points) < 2:
            warnings.append(f"{slug}: fewer than two verified price points")

    extra = sorted(set(profiles) - set(expected))
    if extra:
        warnings.append("snapshot contains disabled/removed profiles: " + ", ".join(extra))
    return errors, warnings


def main() -> int:
    errors, warnings = validate()
    for warning in warnings:
        print(f"MARKET_PROFILE_WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"MARKET_PROFILE_ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Market profile snapshot valid; {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
