#!/usr/bin/env python3
"""Bounded concurrent runner for ``crawl_market_profiles``.

Each company remains an isolated crawl unit. Slow or blocked sites cannot stall
all three markets, while output ordering remains deterministic and prior valid
snapshots continue to be preserved by the underlying crawler. Tonghuashun's
public overview, company, finance, operations and A-share youth pages are merged
before semantic field extraction so the adapter is not tied to one market layout.
"""

from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

try:
    from . import crawl_market_profiles as market
except ImportError:
    import crawl_market_profiles as market

MAX_WORKERS = 5
MIN_TREND_POINTS = 20
TONGHUASHUN_SECTIONS = ("index", "company", "finance", "operate")
_BASE_LABELED_VALUE = market.labeled_value


def robust_labeled_value(text: str, labels: Iterable[str], limit: int = 300) -> str:
    """Read both ``label: value`` prose and adjacent table-cell layouts."""

    strict = _BASE_LABELED_VALUE(text, labels, limit)
    if strict:
        return strict
    for label in labels:
        patterns = (
            rf"(?:^|\n|\|)\s*{re.escape(label)}\s*\n\s*([^\n|]{{1,{limit}}})",
            rf"(?:^|\n|\|)\s*{re.escape(label)}\s+([^\n|]{{1,{limit}}})",
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


def tonghuashun_pages(url: str) -> list[str]:
    root = url.rstrip("/")
    code = root.rsplit("/", 1)[-1]
    pages = [url, *(f"{root}/{section}/" for section in TONGHUASHUN_SECTIONS)]
    if re.fullmatch(r"\d{6}", code):
        pages.append(f"https://stockpage.10jqka.com.cn/youth/{code}/")
    return list(dict.fromkeys(pages))


def multi_page_fetch(url: str) -> str:
    """Merge bounded public company sections; use one attempt per endpoint."""

    if not is_tonghuashun_company_root(url):
        return market.fetch_text(url, attempts=1)

    bodies: list[str] = []
    errors: list[str] = []
    for page_url in tonghuashun_pages(url):
        try:
            bodies.append(market.fetch_text(page_url, attempts=1))
        except Exception as exc:  # noqa: BLE001 - partial sections remain useful.
            errors.append(f"{page_url}: {type(exc).__name__}: {exc}")
    if not bodies:
        raise RuntimeError("; ".join(errors[:2]) or "all Tonghuashun sections failed")
    return "\n<!-- merged public company section -->\n".join(bodies)


def neutral_fetch_text(url: str, timeout: int = 18) -> str:
    """Fetch public JSON/CSV endpoints without leaking an unrelated Referer."""

    request = Request(
        url,
        headers={
            "User-Agent": market.USER_AGENT,
            "Accept": "application/json,text/csv,text/plain,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.7",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return market.decode_response(
                response.read(), response.headers.get("Content-Type", "")
            )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"fetch failed for {url}: {exc}") from exc


def yahoo_chart_urls(identity: market.CompanyIdentity) -> list[str]:
    symbol = quote_plus(identity.ticker)
    query = "range=6mo&interval=1d&events=history&includeAdjustedClose=true"
    return [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?{query}",
    ]


def parse_yahoo_chart(body: str) -> list[dict[str, Any]]:
    payload = json.loads(body)
    chart = payload.get("chart") if isinstance(payload, dict) else None
    results = chart.get("result") if isinstance(chart, dict) else None
    result = results[0] if isinstance(results, list) and results else None
    if not isinstance(result, dict):
        return []
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    quotes = indicators.get("quote") if isinstance(indicators, dict) else None
    quote = quotes[0] if isinstance(quotes, list) and quotes else None
    if not isinstance(timestamps, list) or not isinstance(quote, dict):
        return []

    opens = quote.get("open") if isinstance(quote.get("open"), list) else []
    closes = quote.get("close") if isinstance(quote.get("close"), list) else []
    highs = quote.get("high") if isinstance(quote.get("high"), list) else []
    lows = quote.get("low") if isinstance(quote.get("low"), list) else []
    volumes = quote.get("volume") if isinstance(quote.get("volume"), list) else []
    points: list[dict[str, Any]] = []
    for index, raw_timestamp in enumerate(timestamps):
        try:
            values = (
                float(opens[index]),
                float(closes[index]),
                float(highs[index]),
                float(lows[index]),
            )
            point: dict[str, Any] = {
                "date": datetime.fromtimestamp(
                    int(raw_timestamp), timezone.utc
                ).date().isoformat(),
                "open": values[0],
                "close": values[1],
                "high": values[2],
                "low": values[3],
            }
            if index < len(volumes) and volumes[index] is not None:
                point["volume"] = float(volumes[index])
            points.append(point)
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
    return market.dedupe_price_points(points)


def eastmoney_market_ids(exchange: str) -> list[int]:
    normalized = exchange.casefold()
    if "nasdaq" in normalized:
        return [105, 106, 107]
    if "纽约" in exchange or "nyse" in normalized:
        return [106, 105, 107]
    if "amex" in normalized or "美国证券交易所" in exchange:
        return [107, 105, 106]
    return [105, 106, 107]


def eastmoney_url(identity: market.CompanyIdentity, market_id: int) -> str:
    fields1 = "f1,f2,f3,f4,f5,f6"
    fields2 = "f51,f52,f53,f54,f55,f56"
    return (
        "https://63.push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={market_id}.{identity.ticker}"
        f"&ut=fa5fd1943c7b386f172d6893dbfba10b"
        f"&fields1={fields1}&fields2={fields2}"
        "&klt=101&fqt=1&beg=0&end=20500101&lmt=120"
    )


def parse_eastmoney_kline(body: str) -> list[dict[str, Any]]:
    payload = json.loads(body)
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("klines", []) if isinstance(data, dict) else []
    points: list[dict[str, Any]] = []
    for raw in rows:
        columns = str(raw).split(",")
        if len(columns) < 6:
            continue
        try:
            points.append(
                {
                    "date": columns[0],
                    "open": float(columns[1]),
                    "close": float(columns[2]),
                    "high": float(columns[3]),
                    "low": float(columns[4]),
                    "volume": float(columns[5]),
                }
            )
        except (TypeError, ValueError):
            continue
    return market.dedupe_price_points(points)


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


def backfill_us_trend(
    identity: market.CompanyIdentity,
    profile: dict[str, Any],
) -> dict[str, Any]:
    current = profile.get("priceHistory", [])
    if identity.market != "美股" or len(current) >= MIN_TREND_POINTS:
        return profile

    for fallback_url in yahoo_chart_urls(identity):
        try:
            points = parse_yahoo_chart(neutral_fetch_text(fallback_url))
        except Exception:
            continue
        if len(points) > len(current):
            profile["priceHistory"] = points
            profile.setdefault("sources", {})["price"] = fallback_url
            current = points
        if len(current) >= MIN_TREND_POINTS:
            return clean_profile(profile)

    company = profile.get("company") if isinstance(profile.get("company"), dict) else {}
    exchange = str(company.get("exchange") or "")
    for market_id in eastmoney_market_ids(exchange):
        fallback_url = eastmoney_url(identity, market_id)
        try:
            points = parse_eastmoney_kline(neutral_fetch_text(fallback_url))
        except Exception:
            continue
        if len(points) > len(current):
            profile["priceHistory"] = points
            profile.setdefault("sources", {})["price"] = fallback_url
            current = points
        if len(current) >= MIN_TREND_POINTS:
            return clean_profile(profile)

    fallback_url = stooq_url(identity)
    try:
        points = parse_stooq_csv(neutral_fetch_text(fallback_url))
        if len(points) > len(current):
            profile["priceHistory"] = points
            profile.setdefault("sources", {})["price"] = fallback_url
            current = points
    except Exception:
        pass

    if len(current) < MIN_TREND_POINTS:
        warnings = profile.setdefault("warnings", [])
        warnings.append(
            "美股历史日线不足：已尝试 Yahoo Chart、东方财富市场映射与 Stooq，"
            f"当前 {len(current)} 个交易日"
        )
        profile["warnings"] = warnings[-8:]
    return clean_profile(profile)


def crawl_item(
    item: dict[str, Any],
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile, status = market.crawl_company(item, previous, multi_page_fetch)
    profile = backfill_us_trend(item["identity"], clean_profile(profile))
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
