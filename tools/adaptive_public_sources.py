#!/usr/bin/env python3
"""Unified multi-stage adapter kernel for user-added public sources.

Every public website enters the same pipeline. Site differences are represented
as small profiles that provide canonical URLs, additional public entry points,
request headers and decoding candidates. Profiles do not own separate crawler
implementations; candidate discovery, article parsing, filtering and quality
control remain in the shared generic/robust stages.

The adapter is intentionally best-effort for public pages. Login-only content,
CAPTCHAs, paywalls and sites that expose no public HTML/feed/search surface are
reported as unavailable rather than fabricated as successful crawls.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 No1LizePublicResearch/1.0"
)
VOLATILE_QUERY_KEYS = {
    "guccounter",
    "guce_referrer",
    "guce_referrer_sig",
    "soc_src",
    "soc_trk",
    "ncid",
    "fr",
    "from",
    "p",
}
CHARSET_PATTERN = re.compile(
    br"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceProfile:
    id: str
    host_suffixes: tuple[str, ...]
    default_language: str = ""
    encodings: tuple[str, ...] = ("utf-8",)
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.6"


PROFILES = (
    SourceProfile(
        id="eastmoney",
        host_suffixes=("eastmoney.com",),
        default_language="zh-Hans",
        encodings=("utf-8", "gb18030"),
        accept_language="zh-CN,zh;q=0.9,en;q=0.5",
    ),
    SourceProfile(
        id="yahoo-tw",
        host_suffixes=("tw.yahoo.com", "tw.news.yahoo.com", "tw.stock.yahoo.com"),
        default_language="zh-Hant",
        encodings=("utf-8", "big5", "cp950"),
        accept_language="zh-TW,zh-Hant;q=0.9,en-US;q=0.7,en;q=0.5",
    ),
    SourceProfile(
        id="yahoo-sg",
        host_suffixes=("sg.yahoo.com", "sg.news.yahoo.com", "sg.finance.yahoo.com"),
        default_language="en",
        encodings=("utf-8",),
        accept_language="en-SG,en;q=0.9,zh-TW;q=0.5",
    ),
)
DEFAULT_PROFILE = SourceProfile(id="default", host_suffixes=())


def _host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def profile_for(url: str) -> SourceProfile:
    host = _host(url)
    for profile in PROFILES:
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in profile.host_suffixes):
            return profile
    return DEFAULT_PROFILE


def canonical_source_url(url: str) -> str:
    """Remove consent/tracking noise while preserving the selected public host."""

    parts = urlsplit(html.unescape(str(url or "")).strip())
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        return str(url or "").strip()
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in VOLATILE_QUERY_KEYS
            and not key.casefold().startswith("utm_")
        )
    )
    path = parts.path or "/"
    if path in {"/default.html", "/index.html", "/index.htm"}:
        path = "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path.rstrip("/") or "/",
            query,
            "",
        )
    )


def source_seed_urls(url: str) -> list[str]:
    """Return bounded public entry points for the selected site profile."""

    canonical = canonical_source_url(url)
    profile = profile_for(canonical)
    seeds = [canonical]
    if profile.id == "yahoo-tw":
        seeds.extend(
            (
                "https://tw.yahoo.com/",
                "https://tw.news.yahoo.com/",
                "https://tw.stock.yahoo.com/",
            )
        )
    elif profile.id == "yahoo-sg":
        seeds.extend(
            (
                "https://sg.yahoo.com/",
                "https://sg.news.yahoo.com/",
                "https://sg.finance.yahoo.com/",
            )
        )
    elif profile.id == "eastmoney":
        seeds.extend(
            (
                "https://www.eastmoney.com/",
                "https://finance.eastmoney.com/",
                "https://stock.eastmoney.com/",
                "https://fund.eastmoney.com/",
            )
        )

    result: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        normalized = canonical_source_url(seed)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result[:6]


def _normalize_charset(value: str | None) -> str:
    charset = (value or "").strip().strip("\"'").casefold().replace("_", "-")
    return {
        "gb2312": "gb18030",
        "gb-2312": "gb18030",
        "gbk": "gb18030",
        "x-gbk": "gb18030",
        "cp936": "gb18030",
        "utf8": "utf-8",
        "big-5": "big5",
    }.get(charset, charset)


def decode_public_bytes(
    payload: bytes,
    url: str,
    header_charset: str | None = None,
) -> str:
    """Decode public HTML/XML using HTTP, in-document and profile evidence."""

    candidates: list[str] = []

    def add(value: str | None) -> None:
        normalized = _normalize_charset(value)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add(header_charset)
    match = CHARSET_PATTERN.search(payload[:32768])
    if match:
        add(match.group(1).decode("ascii", errors="ignore"))
    if payload.startswith(b"\xef\xbb\xbf"):
        add("utf-8-sig")
    for encoding in profile_for(url).encodings:
        add(encoding)
    add("utf-8")
    add("gb18030")
    add("big5")

    for charset in candidates:
        try:
            return payload.decode(charset, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode(candidates[0] if candidates else "utf-8", errors="replace")


def fetch_public_text(
    url: str,
    user_agent: str,
    timeout: int = 18,
    attempts: int = 3,
) -> str:
    """Fetch one public page with browser-compatible, profile-aware transport."""

    profile = profile_for(url)
    parts = urlsplit(url)
    referer = f"{parts.scheme}://{parts.netloc}/" if parts.scheme and parts.netloc else url
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        request = Request(
            url,
            headers={
                "User-Agent": BROWSER_USER_AGENT if profile.id != "default" else (user_agent or BROWSER_USER_AGENT),
                "Accept": "text/html,application/xhtml+xml,application/json,application/xml,text/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": profile.accept_language,
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
                "Referer": referer,
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return decode_public_bytes(
                    response.read(),
                    response.geturl() or url,
                    response.headers.get_content_charset(),
                )
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < max(1, attempts):
                time.sleep(0.5 * (2**attempt))
    assert last_error is not None
    raise last_error


class CrawlerProxy:
    """Delegate crawler helpers while replacing only public-web transport."""

    def __init__(self, crawler: Any) -> None:
        self._crawler = crawler

    def __getattr__(self, name: str) -> Any:
        return getattr(self._crawler, name)

    def fetch_text(
        self,
        url: str,
        user_agent: str,
        timeout: int = 18,
        attempts: int = 3,
    ) -> str:
        return fetch_public_text(url, user_agent, timeout=timeout, attempts=attempts)


def _dedupe_articles(items: Iterable[dict[str, Any]], crawler: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        url = crawler.normalize_url(str(source.get("url") or ""))
        if not url or url in seen:
            continue
        result.append(item)
        seen.add(url)
    return result


def crawl_adaptive_source(
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
    generic: Any,
    robust: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run all public sources through the same bounded multi-entry pipeline."""

    original_url = str(spec.get("sourceUrl") or spec.get("url") or "").strip()
    canonical = canonical_source_url(original_url)
    profile = profile_for(canonical)
    proxy = CrawlerProxy(crawler)
    max_items = max(1, int(spec.get("maxItems", 10)))
    all_items: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    strategies: list[str] = []
    seeds = source_seed_urls(canonical)

    for seed in seeds:
        if len(_dedupe_articles(all_items, crawler)) >= max_items:
            break
        seed_spec = {
            **spec,
            "url": seed,
            "sourceUrl": seed,
            "sourceLanguage": spec.get("sourceLanguage") or profile.default_language,
            "maxItems": max_items,
        }
        items, status = robust.crawl_with_second_stage(
            seed_spec,
            user_agent,
            proxy,
            generic,
        )
        all_items.extend(items)
        statuses.append(status)
        for strategy in status.get("strategies", []):
            if strategy not in strategies:
                strategies.append(strategy)

    items = _dedupe_articles(all_items, crawler)[:max_items]
    scanned = sum(int(status.get("scanned", 0) or 0) for status in statuses)
    failed = sum(int(status.get("failed", 0) or 0) for status in statuses)
    has_clean_attempt = any(status.get("status") in {"ok", "empty"} for status in statuses)
    status_name = (
        "ok"
        if items and failed == 0
        else "partial"
        if items
        else "error"
        if failed or not has_clean_attempt
        else "empty"
    )
    result = crawler._status(
        spec["id"],
        generic.platform_name({**spec, "sourceUrl": canonical}),
        status_name,
        scanned,
        len(items),
        failed=failed,
        platform=generic.platform_name({**spec, "sourceUrl": canonical}),
        error=(
            "; ".join(
                str(status.get("error"))
                for status in statuses
                if status.get("error")
            )[:600]
            or None
        ) if not items else None,
    )
    result.update(
        {
            "adapter": "adaptive-public-v1",
            "profile": profile.id,
            "canonicalSourceUrl": canonical,
            "attemptedSeeds": seeds,
            "strategies": strategies,
        }
    )
    return items, result
