#!/usr/bin/env python3
"""Discover official company homepages without delegating source choice to an LLM.

The discovery order is intentionally conservative:

1. outbound links that are explicitly connected to the candidate in an existing
   traceable source article;
2. a small set of exact brand-domain probes derived from an ASCII company name.

A discovered URL is only returned after the caller's official-page verifier confirms
both the company identity and the expected sector. Multiple surviving hosts are
considered ambiguous and fail closed.
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

USER_AGENT = "VCIQ-Official-Source-Discovery/1.0 (+https://github.com/VCIQ/VCIQ.github.io)"
REQUEST_TIMEOUT = 12
MAX_SOURCE_BYTES = 2_000_000
MAX_SOURCE_URLS = 5
MAX_OUTBOUND_LINKS = 80

BLOCKED_HOST_SUFFIXES = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "weibo.com",
    "weixin.qq.com",
    "zhihu.com",
    "google.com",
    "bing.com",
    "baidu.com",
)

DOMAIN_TLDS = ("com", "ai", "io", "tech")
GENERIC_DOMAIN_TOKENS = {
    "ai",
    "the",
    "company",
    "technologies",
    "technology",
    "systems",
    "labs",
    "lab",
    "inc",
    "corp",
    "corporation",
    "limited",
    "ltd",
}


def clean(value: Any, limit: int = 2_000) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def identity_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean(value, 240).casefold())


def safe_http_url(value: Any) -> str:
    url = clean(value, 2_000)
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return url


def unique(values: list[Any], limit: int = 30) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw, 2_000)
        key = value.casefold()
        if not value or key in seen:
            continue
        result.append(value)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._href = ""
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        values = {key.casefold(): value or "" for key, value in attrs}
        href = safe_http_url(urljoin(self.base_url, values.get("href", "")))
        if not href:
            return
        self._href = href
        self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            value = clean(data, 300)
            if value:
                self._anchor_parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or not self._href:
            return
        self.links.append(
            {
                "url": self._href,
                "anchor": clean(" ".join(self._anchor_parts), 500),
            }
        )
        self._href = ""
        self._anchor_parts = []


def fetch_source_links(url: str, *, timeout: int = REQUEST_TIMEOUT) -> list[dict[str, str]]:
    source_url = safe_http_url(url)
    if not source_url:
        return []
    request = Request(
        source_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            return []
        final_url = safe_http_url(response.geturl()) or source_url
        content_type = response.headers.get("Content-Type", "")
    charset = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    encodings = [charset.group(1)] if charset else []
    encodings.extend(["utf-8", "gb18030", "big5", "latin-1"])
    body = ""
    for encoding in encodings:
        try:
            body = raw.decode(encoding)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    if not body:
        body = raw.decode("utf-8", errors="replace")
    parser = LinkParser(final_url)
    parser.feed(body)
    return parser.links[:MAX_OUTBOUND_LINKS]


def _host_blocked(host: str) -> bool:
    normalized = host.casefold().removeprefix("www.")
    return any(
        normalized == suffix or normalized.endswith("." + suffix)
        for suffix in BLOCKED_HOST_SUFFIXES
    )


def _brand_tokens(name: str) -> list[str]:
    ascii_name = (
        unicodedata.normalize("NFKD", clean(name, 160))
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )
    tokens = [token for token in re.findall(r"[a-z0-9]+", ascii_name) if token]
    while tokens and tokens[-1] in GENERIC_DOMAIN_TOKENS:
        tokens.pop()
    return tokens


def brand_domain_candidates(name: str) -> list[str]:
    """Generate a bounded exact-brand domain probe set.

    This is not an identity assertion. Every returned URL must still survive the
    caller's page identity and sector checks before it can become an official source.
    """

    tokens = _brand_tokens(name)
    if not tokens:
        return []
    compact = "".join(tokens)
    hyphenated = "-".join(tokens)
    if len(compact) < 4 or len(compact) > 48:
        return []
    labels = unique([compact, hyphenated], 2)
    return [f"https://{label}.{tld}/" for label in labels for tld in DOMAIN_TLDS]


def _candidate_link_score(candidate_name: str, anchor: str, url: str) -> int:
    wanted = identity_key(candidate_name)
    anchor_key = identity_key(anchor)
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    host_label = host.split(".")[0] if host else ""
    host_key = identity_key(host_label)
    score = 0
    if wanted and wanted == anchor_key:
        score += 6
    elif wanted and len(wanted) >= 4 and wanted in anchor_key:
        score += 4
    if wanted and wanted == host_key:
        score += 6
    elif wanted and len(wanted) >= 5 and wanted in host_key:
        score += 3
    return score


def source_link_candidates(
    candidate: Mapping[str, Any],
    *,
    source_link_fetcher: Callable[[str], list[dict[str, str]]] = fetch_source_links,
) -> list[str]:
    name = clean(candidate.get("name"), 160)
    raw_sources = candidate.get("sourceUrls", [])
    source_urls = raw_sources if isinstance(raw_sources, list) else []
    ranked: list[tuple[int, str]] = []
    for source_url in source_urls[:MAX_SOURCE_URLS]:
        source = safe_http_url(source_url)
        if not source:
            continue
        source_host = (urlsplit(source).hostname or "").casefold()
        try:
            links = source_link_fetcher(source)
        except Exception:
            continue
        for row in links:
            if not isinstance(row, dict):
                continue
            link = safe_http_url(row.get("url"))
            if not link:
                continue
            host = (urlsplit(link).hostname or "").casefold()
            if not host or host == source_host or host.endswith("." + source_host):
                continue
            if _host_blocked(host):
                continue
            score = _candidate_link_score(name, clean(row.get("anchor"), 500), link)
            if score >= 4:
                ranked.append((score, link))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return unique([url for _, url in ranked], 12)


def discover_verified_official_site(
    candidate: Mapping[str, Any],
    *,
    page_fetcher: Callable[[str], Mapping[str, Any]],
    identity_checker: Callable[[Mapping[str, Any], list[str]], bool],
    sector_checker: Callable[[Mapping[str, Any], str], bool],
    source_link_fetcher: Callable[[str], list[dict[str, str]]] = fetch_source_links,
) -> tuple[dict[str, Any] | None, str]:
    """Find exactly one official host that survives deterministic verification."""

    name = clean(candidate.get("name"), 240)
    raw_aliases = candidate.get("aliases", [])
    aliases = raw_aliases if isinstance(raw_aliases, list) else []
    names = unique([name, *aliases], 30)
    sector = clean(candidate.get("sector"), 120)

    sources = source_link_candidates(candidate, source_link_fetcher=source_link_fetcher)
    probe_urls = brand_domain_candidates(name)
    stages = [
        ("source-article-link", sources),
        ("brand-domain-probe", probe_urls),
    ]
    for source_kind, urls in stages:
        verified: dict[str, Mapping[str, Any]] = {}
        for url in urls:
            try:
                page = page_fetcher(url)
            except Exception:
                continue
            if not identity_checker(page, names):
                continue
            if not sector_checker(page, sector):
                continue
            final_url = safe_http_url(page.get("url")) or safe_http_url(url)
            host = (urlsplit(final_url).hostname or "").casefold().removeprefix("www.")
            if not host or _host_blocked(host):
                continue
            verified[host] = page
        if len(verified) > 1:
            return None, f"{source_kind} produced multiple verified official hosts"
        if len(verified) == 1:
            page = next(iter(verified.values()))
            final_url = safe_http_url(page.get("url"))
            candidate_region = clean(candidate.get("region"), 80)
            english_name = name if name and name.isascii() else ""
            return (
                {
                    "source": source_kind,
                    "sourceId": final_url,
                    "canonicalName": name,
                    "englishName": english_name,
                    "homepage": final_url,
                    "region": candidate_region,
                    "founded": "",
                    "headquarters": "",
                    "aliases": unique(list(aliases), 20),
                    "description": clean(page.get("description"), 500),
                    "newsUrls": unique(list(page.get("newsUrls", [])) if isinstance(page.get("newsUrls"), list) else [], 8),
                },
                "",
            )
    return None, "no verified official site from source links or exact brand-domain probes"
