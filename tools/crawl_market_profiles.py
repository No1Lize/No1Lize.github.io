#!/usr/bin/env python3
"""Build static A-share, Hong Kong and US company market profiles.

Public Tonghuashun company pages provide the company profile, key metrics and
financial-series structure used by the UI. Price history is read from embedded
page data when available and otherwise falls back to Tencent's public daily
K-line endpoint. The crawler is deliberately bounded, preserves prior good
snapshots on ambiguous failures and never treats delayed quotes as real-time.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
OUTPUT_PATH = ROOT / "public" / "data" / "market_profiles.json"
USER_AGENT = "VCIQResearchBot/1.0 (+https://vciq.github.io/)"
MARKETS = {"A股", "港股", "美股"}
MAX_COMPANIES = 80
MAX_PRICE_POINTS = 120


@dataclass(frozen=True)
class CompanyIdentity:
    market: str
    ticker: str
    slug: str
    ths_code: str
    quote_code: str


class TextCollector(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "li",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "br",
        "dl",
        "dt",
        "dd",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript"}:
            self._ignored += 1
        elif lowered in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1
        elif lowered in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)

    def text(self) -> str:
        joined = " ".join(self.parts)
        joined = re.sub(r"[ \t\f\v]+", " ", joined)
        joined = re.sub(r" *\n *", "\n", joined)
        joined = re.sub(r"\n{2,}", "\n", joined)
        return joined.strip()


def normalize_ticker(market: str, value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "")
    if market == "A股":
        raw = re.sub(r"^(SH|SZ|BJ)", "", raw)
        raw = re.sub(r"\.(SH|SZ|BJ)$", "", raw)
        digits = re.sub(r"\D", "", raw)
        return digits if re.fullmatch(r"\d{6}", digits) else ""
    if market == "港股":
        raw = re.sub(r"^HK", "", raw)
        raw = re.sub(r"\.HK$", "", raw)
        digits = re.sub(r"\D", "", raw)
        return digits.zfill(5) if 1 <= len(digits) <= 5 else ""
    return raw if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", raw) else ""


def a_share_exchange(ticker: str) -> str:
    if ticker.startswith(("4", "8", "92")):
        return "bj"
    if ticker.startswith(("5", "6", "9")):
        return "sh"
    return "sz"


def company_identity(
    market: str,
    ticker_value: Any,
    catalog_slug: str = "",
) -> CompanyIdentity | None:
    ticker = normalize_ticker(market, ticker_value)
    if not ticker or market not in MARKETS:
        return None
    if market == "A股":
        return CompanyIdentity(
            market,
            ticker,
            catalog_slug or f"a-{ticker}",
            ticker,
            f"{a_share_exchange(ticker)}{ticker}",
        )
    if market == "港股":
        short = str(int(ticker)).zfill(4)
        return CompanyIdentity(
            market,
            ticker,
            catalog_slug or f"hk-{ticker}",
            f"HK{short}",
            f"hk{ticker}",
        )
    slug_ticker = re.sub(r"[^a-z0-9]+", "-", ticker.casefold()).strip("-")
    return CompanyIdentity(
        market,
        ticker,
        catalog_slug or f"us-{slug_ticker}",
        ticker,
        f"us{ticker}",
    )


def stockpage_url(identity: CompanyIdentity) -> str:
    return f"https://stockpage.10jqka.com.cn/{quote(identity.ths_code)}/"


def kline_url(identity: CompanyIdentity, limit: int = MAX_PRICE_POINTS) -> str:
    param = f"{identity.quote_code},day,,,{max(10, min(limit, MAX_PRICE_POINTS))},qfq"
    return "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=" + quote(param)


def decode_response(data: bytes, content_type: str = "") -> str:
    charset_match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    encodings = [charset_match.group(1)] if charset_match else []
    encodings.extend(["utf-8", "gb18030", "big5"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def fetch_text(url: str, attempts: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh-TW;q=0.9,en;q=0.8",
                "Referer": "https://stockpage.10jqka.com.cn/",
            },
        )
        try:
            with urlopen(request, timeout=22) as response:
                return decode_response(
                    response.read(), response.headers.get("Content-Type", "")
                )
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def clean_value(value: str, limit: int = 500) -> str:
    result = html.unescape(str(value or ""))
    result = re.sub(r"\s+", " ", result).strip(" |：:,-")
    return result[:limit]


def labeled_value(text: str, labels: Iterable[str], limit: int = 300) -> str:
    for label in labels:
        pattern = rf"(?:^|\n|\|)\s*{re.escape(label)}\s*[：:]\s*([^\n|]{{1,{limit}}})"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = clean_value(match.group(1), limit)
            if value and value not in {"--", "-"}:
                return value
    return ""


def title_company_name(raw_html: str, identity: CompanyIdentity) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.I | re.S)
    if not title_match:
        return ""
    title = clean_value(re.sub(r"<[^>]+>", " ", title_match.group(1)), 100)
    title = re.sub(rf"\(?{re.escape(identity.ticker)}\)?.*$", "", title).strip()
    title = re.sub(r"(?:首页概览|个股|行情|同花顺).*$", "", title).strip(" _-")
    return title


def parse_financial_series(raw_html: str) -> list[dict[str, Any]]:
    body = html.unescape(raw_html).replace("\\/", "/")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"(\[\[\[[\s\S]{5,1800}?\]\],\s*\[\[[\s\S]{5,1000}?\]\],\s*\"[^\"]{0,30}\"\])"
        r"\s*(归母净利润|净利润|营业收入)",
        re.IGNORECASE,
    )
    for fragment, label in pattern.findall(body):
        try:
            parsed = json.loads(fragment)
            values, periods, unit = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        value_map = {str(row[0]): row[1] for row in values if isinstance(row, list) and len(row) >= 2}
        period_map = {str(row[0]): row[1] for row in periods if isinstance(row, list) and len(row) >= 2}
        points: list[dict[str, Any]] = []
        for key in period_map:
            try:
                points.append({"period": clean_value(str(period_map[key]), 40), "value": float(value_map[key])})
            except (KeyError, TypeError, ValueError):
                continue
        normalized_label = "净利润" if label in {"归母净利润", "净利润"} else "营业收入"
        series_id = "netIncome" if normalized_label == "净利润" else "revenue"
        if points and series_id not in seen:
            results.append(
                {
                    "id": series_id,
                    "label": normalized_label,
                    "unit": clean_value(str(unit), 30),
                    "points": points[-8:],
                }
            )
            seen.add(series_id)
    return results


def parse_embedded_price_history(raw_html: str) -> list[dict[str, Any]]:
    """Accept common embedded OHLC object/array shapes without binding to a DOM."""

    body = html.unescape(raw_html).replace("\\/", "/")
    points: list[dict[str, Any]] = []
    object_pattern = re.compile(
        r'\{[^{}]{0,220}?["\'](?:date|day|time)["\']\s*:\s*["\'](20\d{2}[-/]?\d{2}[-/]?\d{2})["\']'
        r'[^{}]{0,220}?["\'](?:open|o)["\']\s*:\s*["\']?(-?\d+(?:\.\d+)?)'
        r'[^{}]{0,220}?["\'](?:close|c|price)["\']\s*:\s*["\']?(-?\d+(?:\.\d+)?)'
        r'[^{}]{0,220}?["\'](?:high|h)["\']\s*:\s*["\']?(-?\d+(?:\.\d+)?)'
        r'[^{}]{0,220}?["\'](?:low|l)["\']\s*:\s*["\']?(-?\d+(?:\.\d+)?)',
        re.I,
    )
    for date, open_, close, high, low in object_pattern.findall(body):
        normalized_date = date.replace("/", "-")
        if len(normalized_date) == 8:
            normalized_date = f"{normalized_date[:4]}-{normalized_date[4:6]}-{normalized_date[6:]}"
        points.append(
            {
                "date": normalized_date,
                "open": float(open_),
                "close": float(close),
                "high": float(high),
                "low": float(low),
            }
        )
    return dedupe_price_points(points)


def parse_tonghuashun_html(
    raw_html: str,
    identity: CompanyIdentity,
    configured_name: str,
) -> dict[str, Any]:
    parser = TextCollector()
    parser.feed(raw_html)
    text = parser.text()

    company_name = labeled_value(text, ["公司名称", "公司简称"], 100)
    company_name = company_name or title_company_name(raw_html, identity) or configured_name
    profile = {
        "name": company_name,
        "englishName": labeled_value(text, ["英文名称"], 120),
        "industry": labeled_value(text, ["所属行业", "行业分类"], 160),
        "exchange": labeled_value(text, ["交易所", "上市场所"], 100),
        "listedAt": labeled_value(text, ["上市日期", "上市时间"], 40),
        "website": labeled_value(text, ["公司网址"], 160),
        "employees": labeled_value(text, ["员工人数"], 40),
        "chairman": labeled_value(text, ["董事长", "公司总裁"], 80),
        "address": labeled_value(text, ["办公地址", "注册地址"], 220),
        "description": labeled_value(text, ["公司简介", "公司介绍"], 600),
        "mainBusiness": labeled_value(text, ["主营业务", "经营范围"], 500),
    }
    profile = {key: value for key, value in profile.items() if value}

    metric_labels = [
        ("marketCap", "总市值"),
        ("pe", "市盈率"),
        ("pb", "市净率"),
        ("totalShares", "总股本"),
        ("floatShares", "流通股"),
        ("eps", "每股收益"),
        ("netIncome", "净利润"),
        ("revenue", "营业收入"),
        ("cashFlowPerShare", "每股现金流"),
        ("bookValuePerShare", "每股净资产"),
        ("roe", "净资产收益率"),
        ("roa", "总资产收益率"),
    ]
    metrics: list[dict[str, str]] = []
    for metric_id, label in metric_labels:
        value = labeled_value(text, [label, f"{label}(动)", f"{label}(TTM)"], 80)
        if value:
            metrics.append({"id": metric_id, "label": label, "value": value})

    return {
        "company": profile,
        "metrics": metrics,
        "financialSeries": parse_financial_series(raw_html),
        "priceHistory": parse_embedded_price_history(raw_html),
        "accepted": bool(profile.get("name") and (len(profile) > 1 or metrics)),
    }


def parse_tencent_kline(payload_text: str, quote_code: str) -> list[dict[str, Any]]:
    payload = json.loads(payload_text)
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    node = data.get(quote_code, {}) if isinstance(data, dict) else {}
    rows = []
    if isinstance(node, dict):
        rows = node.get("qfqday") or node.get("day") or node.get("hfqday") or []
    points: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            points.append(
                {
                    "date": str(row[0]),
                    "open": float(row[1]),
                    "close": float(row[2]),
                    "high": float(row[3]),
                    "low": float(row[4]),
                    "volume": float(row[5]),
                }
            )
        except (TypeError, ValueError):
            continue
    return dedupe_price_points(points)


def dedupe_price_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for point in points:
        date = str(point.get("date") or "")
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date):
            by_date[date] = point
    return [by_date[key] for key in sorted(by_date)][-MAX_PRICE_POINTS:]


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def configured_companies(config: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in config.get("listedCompanies", []):
        if not isinstance(raw, dict) or raw.get("enabled") is False:
            continue
        market = str(raw.get("market") or "")
        identity = company_identity(
            market,
            raw.get("ticker"),
            str(raw.get("catalogSlug") or "").strip(),
        )
        name = clean_value(str(raw.get("name") or ""), 100)
        if not identity or not name:
            continue
        key = (identity.market, identity.ticker)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "identity": identity,
                "name": name,
                "sector": clean_value(str(raw.get("sector") or "未分类"), 80),
            }
        )
        if len(result) >= MAX_COMPANIES:
            break
    return result


def merge_previous(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    if not previous:
        return current
    merged = dict(current)
    if not current.get("priceHistory") and previous.get("priceHistory"):
        merged["priceHistory"] = previous["priceHistory"]
        warnings.append("本轮行情为空，保留上一轮有效走势")
    if not current.get("metrics") and previous.get("metrics"):
        merged["metrics"] = previous["metrics"]
        warnings.append("本轮核心指标为空，保留上一轮有效指标")
    if not current.get("financialSeries") and previous.get("financialSeries"):
        merged["financialSeries"] = previous["financialSeries"]
        warnings.append("本轮财务趋势为空，保留上一轮有效趋势")
    previous_company = previous.get("company") if isinstance(previous.get("company"), dict) else {}
    current_company = merged.get("company") if isinstance(merged.get("company"), dict) else {}
    merged["company"] = {**previous_company, **current_company}
    return merged


def crawl_company(
    item: dict[str, Any],
    previous: dict[str, Any] | None,
    fetcher: Callable[[str], str] = fetch_text,
) -> tuple[dict[str, Any], dict[str, Any]]:
    identity: CompanyIdentity = item["identity"]
    ths_url = stockpage_url(identity)
    price_url = kline_url(identity)
    warnings: list[str] = []
    errors: list[str] = []
    parsed = {
        "company": {"name": item["name"]},
        "metrics": [],
        "financialSeries": [],
        "priceHistory": [],
        "accepted": False,
    }

    try:
        parsed = parse_tonghuashun_html(fetcher(ths_url), identity, item["name"])
    except Exception as exc:  # noqa: BLE001 - status must retain the exact adapter failure.
        errors.append(f"同花顺页面：{type(exc).__name__}: {exc}")

    if not parsed.get("priceHistory"):
        try:
            parsed["priceHistory"] = parse_tencent_kline(
                fetcher(price_url), identity.quote_code
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"行情走势：{type(exc).__name__}: {exc}")

    current = {
        "slug": identity.slug,
        "market": identity.market,
        "ticker": identity.ticker,
        "thsCode": identity.ths_code,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "ok",
        "company": parsed.get("company") or {"name": item["name"]},
        "priceHistory": parsed.get("priceHistory") or [],
        "metrics": parsed.get("metrics") or [],
        "financialSeries": parsed.get("financialSeries") or [],
        "sources": {"tonghuashun": ths_url, "price": price_url},
    }
    current = merge_previous(previous, current, warnings)
    profile_accepted = bool(parsed.get("accepted"))
    has_content = bool(
        current.get("priceHistory")
        or current.get("metrics")
        or current.get("financialSeries")
        or len(current.get("company", {})) > 1
    )
    if errors and has_content:
        current["status"] = "partial"
    elif errors:
        current["status"] = "error"
    elif not has_content:
        current["status"] = "pending"
    if warnings or errors:
        current["warnings"] = [*warnings, *errors][:8]

    status = {
        "slug": identity.slug,
        "status": current["status"],
        "profileAccepted": profile_accepted,
        "pricePoints": len(current.get("priceHistory", [])),
    }
    if errors:
        status["error"] = "; ".join(errors[:2])
    return current, status


def build_snapshot(
    config: dict[str, Any],
    previous_snapshot: dict[str, Any],
    fetcher: Callable[[str], str] = fetch_text,
) -> dict[str, Any]:
    previous_profiles = previous_snapshot.get("profiles", {})
    if not isinstance(previous_profiles, dict):
        previous_profiles = {}
    profiles: dict[str, Any] = {}
    statuses: list[dict[str, Any]] = []
    for item in configured_companies(config):
        identity: CompanyIdentity = item["identity"]
        profile, status = crawl_company(
            item,
            previous_profiles.get(identity.slug),
            fetcher,
        )
        profiles[identity.slug] = profile
        statuses.append(status)
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profiles": profiles,
        "sourceStatus": statuses,
    }


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    previous = load_json(OUTPUT_PATH, {"profiles": {}})
    snapshot = build_snapshot(config, previous)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ok = sum(1 for status in snapshot["sourceStatus"] if status["status"] == "ok")
    partial = sum(
        1 for status in snapshot["sourceStatus"] if status["status"] == "partial"
    )
    print(
        f"market profiles: {len(snapshot['profiles'])} companies, "
        f"{ok} ok, {partial} partial"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
