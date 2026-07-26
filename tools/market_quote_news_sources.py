#!/usr/bin/env python3
"""Public quote snapshots and headline feeds from Yahoo Finance and Sina.

Yahoo Finance (sg.finance.yahoo.com and its public, unauthenticated chart and
RSS endpoints) covers US and Hong Kong tickers; Sina Finance's public
``hq.sinajs.cn`` quote endpoint and company-news list pages cover A-share and
Hong Kong tickers. In line with the repository's compliance boundary, only
public endpoints are requested and only headline title, time, category source
and the original link are stored — never article bodies. A failed source keeps
the previous valid quote or news list instead of fabricating data.
"""

from __future__ import annotations

import html
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

try:
    from . import crawl_market_profiles as market
except ImportError:  # pragma: no cover - direct script execution
    import crawl_market_profiles as market

FetchText = Callable[[str, str], str]

SOURCE_YAHOO = "Yahoo财经"
SOURCE_SINA = "新浪财经"
SINA_REFERER = "https://finance.sina.com.cn/"
CHINA_TZ = timezone(timedelta(hours=8))
YAHOO_NEWS_HOST_SUFFIXES = ("yahoo.com",)
SINA_NEWS_HOST_SUFFIXES = ("sina.com.cn", "sina.cn")
MAX_NEWS_PER_SOURCE = 6
MAX_NEWS_ITEMS = 10
MAX_TITLE_CHARS = 160


def host_allowed(url: str, suffixes: tuple[str, ...]) -> bool:
    hostname = (urlsplit(url).hostname or "").casefold()
    return bool(hostname) and any(
        hostname == suffix or hostname.endswith(f".{suffix}") for suffix in suffixes
    )


def positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# ---------------------------------------------------------------------------
# Yahoo Finance (US + Hong Kong)
# ---------------------------------------------------------------------------


def yahoo_symbol(identity: market.CompanyIdentity) -> str:
    if identity.market == "美股":
        return identity.ticker
    if identity.market == "港股":
        digits = re.sub(r"\D", "", identity.ticker)
        if not digits:
            return ""
        return f"{int(digits):04d}.HK"
    return ""


def yahoo_quote_api_url(symbol: str) -> str:
    return (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote_plus(symbol)}?range=5d&interval=1d"
    )


def yahoo_page_url(symbol: str) -> str:
    return f"https://sg.finance.yahoo.com/quote/{quote_plus(symbol)}/"


def yahoo_news_url(symbol: str) -> str:
    return (
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s="
        f"{quote_plus(symbol)}&region=SG&lang=en-SG"
    )


def parse_yahoo_quote(body: str) -> dict[str, Any]:
    payload = json.loads(body)
    chart = payload.get("chart") if isinstance(payload, dict) else None
    results = chart.get("result") if isinstance(chart, dict) else None
    result = results[0] if isinstance(results, list) and results else None
    meta = result.get("meta") if isinstance(result, dict) else None
    if not isinstance(meta, dict):
        return {}

    price = positive_number(meta.get("regularMarketPrice"))
    if price is None:
        return {}
    previous = positive_number(meta.get("chartPreviousClose"))
    if previous is None:
        previous = positive_number(meta.get("previousClose"))

    quote: dict[str, Any] = {"price": price}
    if previous is not None:
        quote["previousClose"] = previous
        quote["change"] = round(price - previous, 4)
        quote["changePercent"] = round((price - previous) / previous * 100, 2)
    currency = str(meta.get("currency") or "").strip().upper()
    if currency:
        quote["currency"] = currency
    timestamp = meta.get("regularMarketTime")
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        quote["asOf"] = datetime.fromtimestamp(int(timestamp), timezone.utc).isoformat(
            timespec="seconds"
        )
    return quote


def parse_yahoo_news(body: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for block in re.findall(r"<item[\s>]([\s\S]*?)</item>", body, re.IGNORECASE):
        title_match = re.search(
            r"<title>\s*(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?\s*</title>",
            block,
            re.IGNORECASE,
        )
        link_match = re.search(
            r"<link>\s*(?:<!\[CDATA\[)?(https?://[^<\]\s]+)(?:\]\]>)?\s*</link>",
            block,
            re.IGNORECASE,
        )
        date_match = re.search(
            r"<pubDate>\s*([^<]+?)\s*</pubDate>", block, re.IGNORECASE
        )
        if not title_match or not link_match:
            continue
        title = market.clean_value(html.unescape(title_match.group(1)), MAX_TITLE_CHARS)
        url = html.unescape(link_match.group(1)).strip()
        if not title or not host_allowed(url, YAHOO_NEWS_HOST_SUFFIXES):
            continue
        published = ""
        if date_match:
            try:
                published = parsedate_to_datetime(date_match.group(1)).isoformat(
                    timespec="seconds"
                )
            except (TypeError, ValueError):
                published = ""
        if not published:
            continue
        items.append(
            {
                "title": title,
                "url": url,
                "publishedAt": published,
                "source": SOURCE_YAHOO,
            }
        )
        if len(items) >= MAX_NEWS_PER_SOURCE:
            break
    return items


# ---------------------------------------------------------------------------
# Sina Finance (A-share + Hong Kong)
# ---------------------------------------------------------------------------


def sina_quote_code(identity: market.CompanyIdentity) -> str:
    if identity.market == "A股":
        return f"{market.a_share_exchange(identity.ticker)}{identity.ticker}"
    if identity.market == "港股":
        return f"rt_hk{identity.ticker}"
    return ""


def sina_quote_url(code: str) -> str:
    return f"https://hq.sinajs.cn/list={code}"


def sina_page_url(identity: market.CompanyIdentity) -> str:
    if identity.market == "A股":
        code = f"{market.a_share_exchange(identity.ticker)}{identity.ticker}"
        return f"https://finance.sina.com.cn/realstock/company/{code}/nc.shtml"
    if identity.market == "港股":
        return f"https://stock.finance.sina.com.cn/hkstock/quotes/{identity.ticker}.html"
    return ""


def sina_news_url(identity: market.CompanyIdentity) -> str:
    if identity.market == "A股":
        code = f"{market.a_share_exchange(identity.ticker)}{identity.ticker}"
        return (
            "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/"
            f"symbol/{code}.phtml"
        )
    if identity.market == "港股":
        return (
            "https://stock.finance.sina.com.cn/hkstock/go.php/CompanyNews/"
            f"page/1/code/{identity.ticker}/.phtml"
        )
    return ""


def _sina_iso(day: str, clock: str) -> str:
    normalized_day = day.replace("/", "-")
    if not re.fullmatch(r"20\d{2}-\d{1,2}-\d{1,2}", normalized_day):
        return ""
    parts = normalized_day.split("-")
    normalized_day = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    normalized_clock = clock if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", clock or "") else "00:00"
    if len(normalized_clock) == 5:
        normalized_clock += ":00"
    return f"{normalized_day}T{normalized_clock}+08:00"


def parse_sina_quote(body: str, market_name: str) -> dict[str, Any]:
    match = re.search(r'hq_str_(\w+)="([^"]*)"', body)
    if not match:
        return {}
    fields = match.group(2).split(",")
    if match.group(1).startswith("rt_hk"):
        if len(fields) < 9:
            return {}
        price = positive_number(fields[6])
        previous = positive_number(fields[3])
        if price is None:
            return {}
        quote: dict[str, Any] = {"price": price, "currency": "HKD"}
        if previous is not None:
            quote["previousClose"] = previous
        change = finite_number(fields[7])
        change_percent = finite_number(fields[8])
        if change is None and previous is not None:
            change = price - previous
        if change_percent is None and previous is not None:
            change_percent = (price - previous) / previous * 100
        if change is not None:
            quote["change"] = round(change, 4)
        if change_percent is not None:
            quote["changePercent"] = round(change_percent, 2)
        if len(fields) > 18:
            as_of = _sina_iso(fields[17], fields[18])
            if as_of:
                quote["asOf"] = as_of
        return quote

    if len(fields) < 6:
        return {}
    price = positive_number(fields[3])
    previous = positive_number(fields[2])
    if price is None:
        return {}
    quote = {"price": price, "currency": "CNY"}
    if previous is not None:
        quote["previousClose"] = previous
        quote["change"] = round(price - previous, 4)
        quote["changePercent"] = round((price - previous) / previous * 100, 2)
    if len(fields) > 31:
        as_of = _sina_iso(fields[30], fields[31])
        if as_of:
            quote["asOf"] = as_of
    return quote


_SINA_DATED_LINK = re.compile(
    r"(20\d{2}-\d{2}-\d{2})(?:\s|&nbsp;|　)*(\d{2}:\d{2})?(?:\s|&nbsp;|　)*"
    r"<a[^>]+href=[\"'](https?://[^\"']+)[\"'][^>]*>([^<]{4,200})</a>",
    re.IGNORECASE,
)
_SINA_LINK_THEN_DATE = re.compile(
    r"<a[^>]+href=[\"'](https?://[^\"']+)[\"'][^>]*>([^<]{4,200})</a>"
    r"(?:\s|&nbsp;|　|</?(?!a\b)\w[^>]*>)*"
    r"[（(]?\s*(?:(20\d{2})[-/年])?(\d{1,2})[-/月](\d{1,2})日?\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)


def parse_sina_news(body: str, today: date | None = None) -> list[dict[str, Any]]:
    today = today or datetime.now(CHINA_TZ).date()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(title: str, url: str, published: str) -> None:
        title = market.clean_value(html.unescape(title), MAX_TITLE_CHARS)
        url = html.unescape(url).strip()
        if not title or not published or not host_allowed(url, SINA_NEWS_HOST_SUFFIXES):
            return
        if url in seen:
            return
        seen.add(url)
        items.append(
            {
                "title": title,
                "url": url,
                "publishedAt": published,
                "source": SOURCE_SINA,
            }
        )

    for day, clock, url, title in _SINA_DATED_LINK.findall(body):
        add(title, url, _sina_iso(day, clock or "00:00"))

    for url, title, year, month, day, clock in _SINA_LINK_THEN_DATE.findall(body):
        try:
            resolved_year = int(year) if year else today.year
            candidate = date(resolved_year, int(month), int(day))
        except ValueError:
            continue
        if not year and candidate > today + timedelta(days=3):
            candidate = date(today.year - 1, int(month), int(day))
        add(title, url, _sina_iso(candidate.isoformat(), clock))

    return items[: MAX_NEWS_PER_SOURCE * 2]


# ---------------------------------------------------------------------------
# Transport, merging and profile enrichment
# ---------------------------------------------------------------------------


def fetch_with_referer(url: str, referer: str = "") -> str:
    headers = {
        "User-Agent": market.USER_AGENT,
        "Accept": "text/html,application/xml,application/json,text/plain,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    request = Request(url, headers=headers)
    with urlopen(request, timeout=15) as response:
        return market.decode_response(
            response.read(), response.headers.get("Content-Type", "")
        )


def _sort_key(item: dict[str, Any]) -> str:
    raw = str(item.get("publishedAt") or "")
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc).isoformat()
    except ValueError:
        return "0000"


def merge_news(*groups: list[dict[str, Any]], limit: int = MAX_NEWS_ITEMS) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for group in groups:
        for item in group:
            url = str(item.get("url") or "")
            title_key = re.sub(r"\s+", "", str(item.get("title") or "")).casefold()
            if not url or url in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(url)
            seen_titles.add(title_key)
            merged.append(item)
    merged.sort(key=_sort_key, reverse=True)
    return merged[:limit]


def _quote_plans(
    identity: market.CompanyIdentity,
) -> list[tuple[str, str, str, str, Callable[[str], dict[str, Any]]]]:
    """(source name, api url, referer, page url, parser) per market."""

    plans: list[tuple[str, str, str, str, Callable[[str], dict[str, Any]]]] = []
    sina_code = sina_quote_code(identity)
    if sina_code:
        plans.append(
            (
                SOURCE_SINA,
                sina_quote_url(sina_code),
                SINA_REFERER,
                sina_page_url(identity),
                lambda body: parse_sina_quote(body, identity.market),
            )
        )
    symbol = yahoo_symbol(identity)
    if symbol:
        plans.append(
            (
                SOURCE_YAHOO,
                yahoo_quote_api_url(symbol),
                "",
                yahoo_page_url(symbol),
                parse_yahoo_quote,
            )
        )
    return plans


def enrich_quote_and_news(
    identity: market.CompanyIdentity,
    profile: dict[str, Any],
    previous: dict[str, Any] | None = None,
    fetcher: FetchText = fetch_with_referer,
) -> dict[str, Any]:
    previous = previous if isinstance(previous, dict) else {}
    notes: list[str] = []

    quote: dict[str, Any] = {}
    for source_name, api_url, referer, page_url, parser in _quote_plans(identity):
        try:
            parsed = parser(fetcher(api_url, referer))
        except Exception as exc:  # noqa: BLE001 - each public source degrades alone.
            notes.append(f"{source_name}行情：{type(exc).__name__}: {exc}")
            continue
        if parsed.get("price"):
            quote = dict(parsed)
            quote["source"] = {"name": source_name, "url": page_url}
            break
        notes.append(f"{source_name}行情：公开报价暂无有效最新价")

    news_groups: list[list[dict[str, Any]]] = []
    symbol = yahoo_symbol(identity)
    if symbol:
        try:
            news_groups.append(parse_yahoo_news(fetcher(yahoo_news_url(symbol), "")))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{SOURCE_YAHOO}新闻：{type(exc).__name__}: {exc}")
    sina_list_url = sina_news_url(identity)
    if sina_list_url:
        try:
            news_groups.append(parse_sina_news(fetcher(sina_list_url, SINA_REFERER)))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{SOURCE_SINA}新闻：{type(exc).__name__}: {exc}")
    news = merge_news(*news_groups)

    previous_quote = previous.get("quote") if isinstance(previous.get("quote"), dict) else None
    if quote:
        profile["quote"] = quote
    elif previous_quote:
        profile["quote"] = previous_quote
        notes.append("本轮公开行情快照抓取失败，保留上一轮报价")

    previous_news = previous.get("news") if isinstance(previous.get("news"), list) else None
    if news:
        profile["news"] = news
    elif previous_news:
        profile["news"] = previous_news
        notes.append("本轮公开新闻为空，保留上一轮新闻标题")

    sources = profile.setdefault("sources", {})
    if symbol:
        sources["yahooFinance"] = yahoo_page_url(symbol)
    if sina_page_url(identity):
        sources["sinaFinance"] = sina_page_url(identity)

    if notes:
        warnings = profile.setdefault("warnings", [])
        warnings.extend(notes)
        profile["warnings"] = warnings[-8:]
    return profile
