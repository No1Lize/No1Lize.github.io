#!/usr/bin/env python3
"""Bounded concurrent runner for ``crawl_market_profiles``.

Each company remains an isolated crawl unit. Slow or blocked sites cannot stall
all three markets, while output ordering remains deterministic and prior valid
snapshots continue to be preserved by the underlying crawler. Tonghuashun's
public overview, company, finance and operations pages are merged before semantic
field extraction so the adapter is not tied to one market's page layout.
"""

from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any, Iterable
from urllib.parse import quote_plus, urlsplit

try:
    from . import crawl_market_profiles as market
except ImportError:
    import crawl_market_profiles as market

MAX_WORKERS = 5
MIN_TREND_POINTS = 20
TONGHUASHUN_SECTIONS = ("company", "finance", "operate")
_BASE_LABELED_VALUE = market.labeled_value


def robust_labeled_value(text: str, labels: Iterable[str], limit: int = 300) -> str:
    """Read both ``label: value`` prose and adjacent table-cell layouts."""

    strict = _BASE_LABELED_VALUE(text, labels, limit)
    if strict:
        return strict
    for label in labels:
        patterns = (
            rf"(?:^|\n)\s*{re.escape(label)}\s*\n\s*([^\n|]{{1,{limit}}})",
            rf"(?:^|\n)\s*{re.escape(label)}\s+([^\n|]{{1,{limit}}})",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = market.clean_value(match.group(1), limit)
            if value and value not in {"--", "-"}:
                return value
    return ""


# ``parse_tonghuashun_html`` resolves this global at runtime, so all production
# market refreshes use the table-aware extractor without forking the base parser.
market.labeled_value = robust_labeled_value


def is_tonghuashun_company_root(url: str) -> bool:
    parts = urlsplit(url)
    if (parts.hostname or "").casefold() != "stockpage.10jqka.com.cn":
        return False
    segments = [segment for segment in parts.path.split("/") if segment]
    return len(segments) == 1


def multi_page_fetch(url: str) -> str:
    """Merge bounded public company sections; use one attempt per endpoint."""

    if not is_tonghuashun_company_root(url):
        return market.fetch_text(url, attempts=1)

    root = url.rstrip("/")
    pages = [url, *(f"{root}/{section}/" for section in TONGHUASHUN_SECTIONS)]
    bodies: list[str] = []
    errors: list[str] = []
    for page_url in pages:
        try:
            bodies.append(market.fetch_text(page_url, attempts=1))
        except Exception as exc:  # noqa: BLE001 - partial sections remain useful.
            errors.append(f"{page_url}: {type(exc).__name__}: {exc}")
    if not bodies:
        raise RuntimeError("; ".join(errors[:2]) or "all Tonghuashun sections failed")
    return "\n<!-- merged public company section -->\n".join(bodies)


def stooq_url(identity: market.CompanyIdentity) -> str:
    symbol = quote_plus(f"{identity.ticker.lower()}.us")
    return f"https://stooq.com/q/d/l/?s={symbol}&i=d"


def parse_stooq_csv(body: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    reader = csv.DictReader(StringIO(body.strip()))
    for row in reader:
        try:
            point = {
                "date": str(row.get("Date") or ""),
                "open": float(row["Open"]),
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
            }
            volume = row.get("Volume")
            if volume not in {None, "", "No data"}:
                point["volume"] = float(volume)
            points.append(point)
        except (KeyError, TypeError, ValueError):
            continue
    return market.dedupe_price_points(points)


def clean_profile(profile: dict[str, Any]) -> dict[str, Any]:
    metrics = profile.get("metrics")
    if isinstance(metrics, list):
        for metric in metrics:
            if isinstance(metric, dict) and isinstance(metric.get("value"), str):
                metric["value"] = re.sub(r"%{2,}", "%", metric["value"])

    company = profile.get("company") if isinstance(profile.get("company"), dict) else {}
    listed_at = str(company.get("listedAt") or "")
    lower_bound = listed_at if re.fullmatch(r"\d{4}-\d{2}-\d{2}", listed_at) else "1900-01-01"
    upper_bound = date.today().isoformat()
    cleaned_points: list[dict[str, Any]] = []
    for point in profile.get("priceHistory", []):
        if not isinstance(point, dict):
            continue
        point_date = str(point.get("date") or "")
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", point_date):
            continue
        if lower_bound <= point_date <= upper_bound:
            cleaned_points.append(point)
    profile["priceHistory"] = market.dedupe_price_points(cleaned_points)
    return profile


def crawl_item(
    item: dict[str, Any],
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile, status = market.crawl_company(item, previous, multi_page_fetch)
    profile = clean_profile(profile)
    identity: market.CompanyIdentity = item["identity"]

    if identity.market == "美股" and len(profile.get("priceHistory", [])) < MIN_TREND_POINTS:
        fallback_url = stooq_url(identity)
        try:
            points = parse_stooq_csv(market.fetch_text(fallback_url, attempts=1))
            if len(points) > len(profile.get("priceHistory", [])):
                profile["priceHistory"] = points
                profile.setdefault("sources", {})["price"] = fallback_url
        except Exception as exc:  # noqa: BLE001 - the primary snapshot remains valid.
            warnings = profile.setdefault("warnings", [])
            warnings.append(f"美股历史行情回退失败：{type(exc).__name__}: {exc}")
            profile["warnings"] = warnings[-8:]

    status["status"] = profile.get("status", status.get("status", "partial"))
    status["pricePoints"] = len(profile.get("priceHistory", []))
    return profile, status


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
                crawl_item,
                item,
                previous_profiles.get(item["identity"].slug),
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
