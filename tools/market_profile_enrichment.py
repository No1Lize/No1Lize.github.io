#!/usr/bin/env python3
"""Robust quote and company-copy enrichment for three-market profiles."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable

try:
    from . import crawl_market_profiles as market
except ImportError:
    import crawl_market_profiles as market

FetchText = Callable[[str], str]

QUOTE_FIELDS = (
    "f43,f44,f45,f46,f47,f48,f57,f58,f60,f84,f85,f100,f102,"
    "f116,f117,f162,f167,f168,f170"
)

PROVINCES = (
    "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古",
    "广西", "西藏", "宁夏", "新疆", "香港", "澳门", "台湾",
)

NOISY_DESCRIPTION_MARKERS = (
    "公司成立至今共获得多项荣誉",
    "公司先后获得多项荣誉",
    "公司曾获多项荣誉",
    "所获荣誉",
    "荣誉称号",
    "获奖情况",
)


def quote_secids(identity: market.CompanyIdentity, exchange: str = "") -> list[str]:
    if identity.market == "A股":
        prefix = "1" if market.a_share_exchange(identity.ticker) == "sh" else "0"
        return [f"{prefix}.{identity.ticker}"]
    if identity.market == "港股":
        return [f"116.{identity.ticker}"]

    normalized = exchange.casefold()
    if "nasdaq" in normalized:
        ids = [105, 106, 107]
    elif "纽约" in exchange or "nyse" in normalized:
        ids = [106, 105, 107]
    elif "amex" in normalized or "美国证券交易所" in exchange:
        ids = [107, 105, 106]
    else:
        ids = [105, 106, 107]
    return [f"{market_id}.{identity.ticker}" for market_id in ids]


def quote_url(secid: str) -> str:
    return (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={secid}&ut=fa5fd1943c7b386f172d6893dbfba10b&fields={QUOTE_FIELDS}"
    )


def valid_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def scaled_number(value: Any, scale: float = 100.0) -> float | None:
    number = valid_number(value)
    return number / scale if number is not None else None


def format_cap(value: float, market_name: str) -> str:
    prefix = "¥" if market_name == "A股" else "HK$" if market_name == "港股" else "US$"
    if value >= 1_000_000_000_000:
        return f"{prefix}{value / 1_000_000_000_000:.2f}万亿"
    if value >= 100_000_000:
        return f"{prefix}{value / 100_000_000:.2f}亿"
    if value >= 10_000:
        return f"{prefix}{value / 10_000:.2f}万"
    return f"{prefix}{value:,.0f}"


def format_shares(value: float) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿股"
    if value >= 10_000:
        return f"{value / 10_000:.2f}万股"
    return f"{value:,.0f}股"


def format_amount(value: float, market_name: str) -> str:
    return format_cap(value, market_name)


def parse_quote_payload(body: str, market_name: str) -> dict[str, Any]:
    payload = json.loads(body)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data:
        return {}

    metrics: list[dict[str, str]] = []

    def add(metric_id: str, label: str, value: str | None) -> None:
        if value:
            metrics.append({"id": metric_id, "label": label, "value": value})

    market_cap = valid_number(data.get("f116"))
    float_cap = valid_number(data.get("f117"))
    total_shares = valid_number(data.get("f84"))
    float_shares = valid_number(data.get("f85"))
    pe = scaled_number(data.get("f162"))
    pb = scaled_number(data.get("f167"))
    turnover = scaled_number(data.get("f168"))
    amount = valid_number(data.get("f48"))

    add("marketCap", "总市值", format_cap(market_cap, market_name) if market_cap else None)
    add("floatMarketCap", "流通市值", format_cap(float_cap, market_name) if float_cap else None)
    add("totalShares", "总股本", format_shares(total_shares) if total_shares else None)
    add("floatShares", "流通股", format_shares(float_shares) if float_shares else None)
    add("pe", "市盈率", f"{pe:.2f}" if pe is not None else None)
    add("pb", "市净率", f"{pb:.2f}" if pb is not None else None)
    add("turnover", "换手率", f"{turnover:.2f}%" if turnover is not None else None)
    add("amount", "成交额", format_amount(amount, market_name) if amount else None)

    region_candidates = [data.get("f102"), data.get("f100")]
    region = next(
        (
            str(value).strip()
            for value in region_candidates
            if isinstance(value, str)
            and value.strip()
            and value.strip() not in {"-", "--"}
            and len(value.strip()) <= 24
        ),
        "",
    )
    return {"metrics": metrics, "region": region}


def metric_has_number(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(re.search(r"\d", text)) and text not in {"0", "0.00", "0%"}


def merge_metrics(current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for metric in [*current, *incoming]:
        if not isinstance(metric, dict):
            continue
        metric_id = str(metric.get("id") or "").strip()
        if not metric_id:
            continue
        if metric_id not in order:
            order.append(metric_id)
        previous = merged.get(metric_id)
        if previous is None or (
            metric_has_number(metric.get("value"))
            and not metric_has_number(previous.get("value"))
        ) or metric in incoming:
            merged[metric_id] = metric
    preferred = [
        "marketCap", "floatMarketCap", "pe", "pb", "turnover", "amount",
        "totalShares", "floatShares", "eps", "revenue", "netIncome",
        "cashFlowPerShare", "bookValuePerShare", "roe", "roa",
    ]
    rank = {metric_id: index for index, metric_id in enumerate(preferred)}
    return sorted(merged.values(), key=lambda item: rank.get(str(item.get("id")), 999))


def parse_share_count(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(万亿|亿|万)?\s*股?", text)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"万亿": 1_000_000_000_000, "亿": 100_000_000, "万": 10_000}.get(match.group(2) or "", 1)
    result = number * multiplier
    return result if result > 0 else None


def infer_market_cap(profile: dict[str, Any], identity: market.CompanyIdentity) -> dict[str, str] | None:
    metrics = profile.get("metrics") if isinstance(profile.get("metrics"), list) else []
    if any(metric.get("id") == "marketCap" and metric_has_number(metric.get("value")) for metric in metrics if isinstance(metric, dict)):
        return None
    shares_metric = next((metric for metric in metrics if isinstance(metric, dict) and metric.get("id") == "totalShares"), None)
    shares = parse_share_count(shares_metric.get("value") if shares_metric else None)
    points = profile.get("priceHistory") if isinstance(profile.get("priceHistory"), list) else []
    latest = points[-1] if points else None
    close = valid_number(latest.get("close") if isinstance(latest, dict) else None)
    if shares is None or close is None:
        return None
    return {"id": "marketCap", "label": "总市值", "value": format_cap(shares * close, identity.market)}


def normalize_company_text(value: Any, max_chars: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ，。；;|-")
    if not text:
        return ""
    for marker in NOISY_DESCRIPTION_MARKERS:
        index = text.find(marker)
        if index >= 70:
            text = text[:index].rstrip(" ，。；;")
            break
    text = re.sub(r"(?:201\d|202\d)年\d{1,2}月[^。；]{20,}", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ，。；;")
    if len(text) <= max_chars:
        return text + ("。" if text and text[-1] not in "。！？" else "")
    clipped = text[:max_chars]
    sentence_end = max(clipped.rfind("。"), clipped.rfind("！"), clipped.rfind("？"))
    if sentence_end >= max(80, int(max_chars * 0.55)):
        return clipped[: sentence_end + 1]
    comma_end = max(clipped.rfind("，"), clipped.rfind("；"))
    if comma_end >= max(80, int(max_chars * 0.65)):
        clipped = clipped[:comma_end]
    return clipped.rstrip(" ，。；;") + "。"


def infer_region(profile: dict[str, Any], identity: market.CompanyIdentity) -> str:
    company = profile.get("company") if isinstance(profile.get("company"), dict) else {}
    explicit = str(company.get("region") or "").strip()
    if explicit and explicit not in {"-", "--"}:
        return explicit
    address = str(company.get("address") or "")
    for province in PROVINCES:
        if province in address:
            suffix = "市" if province in {"北京", "上海", "天津", "重庆"} else ""
            return f"{province}{suffix}"
    if identity.market == "港股":
        return "中国香港"
    if identity.market == "美股":
        return "美国"
    return "中国"


def normalize_company_profile(profile: dict[str, Any], identity: market.CompanyIdentity) -> dict[str, Any]:
    company = profile.setdefault("company", {})
    description = normalize_company_text(company.get("description"), 360)
    main_business = normalize_company_text(company.get("mainBusiness"), 220)
    if len(description) < 70 and main_business and main_business not in description:
        description = normalize_company_text(f"{description} {main_business}", 360)
    if description:
        company["description"] = description
    if main_business:
        company["mainBusiness"] = main_business
    company["region"] = infer_region(profile, identity)
    profile["company"] = company
    profile["metrics"] = [
        metric for metric in profile.get("metrics", [])
        if isinstance(metric, dict) and metric_has_number(metric.get("value"))
    ]
    inferred = infer_market_cap(profile, identity)
    if inferred:
        profile["metrics"] = merge_metrics(profile["metrics"], [inferred])
    return profile


def enrich_profile(
    identity: market.CompanyIdentity,
    profile: dict[str, Any],
    fetch_text: FetchText,
) -> dict[str, Any]:
    profile = normalize_company_profile(profile, identity)
    company = profile.get("company") if isinstance(profile.get("company"), dict) else {}
    exchange = str(company.get("exchange") or "")
    quote_error = ""
    for secid in quote_secids(identity, exchange):
        url = quote_url(secid)
        try:
            quote = parse_quote_payload(fetch_text(url), identity.market)
        except Exception as exc:  # noqa: BLE001 - fallback to current profile.
            quote_error = f"{type(exc).__name__}: {exc}"
            continue
        metrics = quote.get("metrics") if isinstance(quote.get("metrics"), list) else []
        if metrics:
            profile["metrics"] = merge_metrics(profile.get("metrics", []), metrics)
            profile.setdefault("sources", {})["quote"] = url
        quote_region = str(quote.get("region") or "").strip()
        if quote_region and not company.get("region"):
            company["region"] = quote_region
        if metrics:
            break
    profile["company"] = company
    profile = normalize_company_profile(profile, identity)
    if quote_error and not any(metric.get("id") == "marketCap" for metric in profile.get("metrics", [])):
        warnings = profile.setdefault("warnings", [])
        warnings.append(f"总市值公开报价补全失败：{quote_error}")
        profile["warnings"] = warnings[-8:]
    return profile
