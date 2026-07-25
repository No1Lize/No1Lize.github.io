#!/usr/bin/env python3
"""Second-stage discovery for JS-heavy and non-RSS user websites.

The primary generic crawler handles ordinary HTML links, feeds and public-search
RSS. This module adds bounded fallbacks that remain valid across source types:
embedded structured URLs, sitemap indexes, native site search pages and search
result redirect unwrapping. Platform-specific extraction is kept as a small
plugin inside the same general strategy pipeline rather than becoming a separate
crawler.
"""

from __future__ import annotations

import base64
import html
import re
import xml.etree.ElementTree as ET
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlsplit

COMMON_SITEMAPS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/news-sitemap.xml",
    "/sitemap_news.xml",
)
URL_FIELDS = (
    "url",
    "@id",
    "mainEntityOfPage",
    "contentUrl",
    "embedUrl",
    "canonicalUrl",
)
SEARCH_REDIRECT_KEYS = ("url", "target", "q", "u", "uddg")
MAX_SECOND_STAGE_CANDIDATES = 24
MAX_SITEMAP_FETCHES = 5


def _unique(values: Iterable[str], limit: int = 80) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = html.unescape(str(raw or "")).replace("\\/", "/").strip()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
        if len(result) >= limit:
            break
    return result


def _same_source_family(url: str, source_url: str, generic: Any) -> bool:
    if generic.source_kind(url) == generic.source_kind(source_url) != "website":
        return True
    return generic.registrable_domain(
        urlsplit(url).hostname or ""
    ) == generic.registrable_domain(urlsplit(source_url).hostname or "")


def _decode_bing_u(value: str) -> str:
    """Decode Bing's optional ``u=a1<base64url>`` destination parameter."""

    candidate = unquote(value)
    if candidate.startswith(("http://", "https://")):
        return candidate
    if candidate.startswith("a1"):
        encoded = candidate[2:]
        encoded += "=" * (-len(encoded) % 4)
        try:
            decoded = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="strict")
            if decoded.startswith(("http://", "https://")):
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
    return ""


def unwrap_search_result(url: str) -> str:
    """Return a destination URL from common search-engine redirect wrappers."""

    cleaned = html.unescape(url).replace("\\/", "/")
    parts = urlsplit(cleaned)
    host = (parts.hostname or "").casefold()
    if not any(token in host for token in ("bing.com", "google.com", "duckduckgo.com")):
        return cleaned
    params = parse_qs(parts.query)
    for key in SEARCH_REDIRECT_KEYS:
        for raw in params.get(key, []):
            decoded = _decode_bing_u(raw)
            if decoded:
                return decoded
    return cleaned


def embedded_candidates(source_url: str, body: str, generic: Any) -> list[str]:
    """Extract article/video URLs embedded in JSON-LD and hydrated app state."""

    normalized_body = html.unescape(body or "").replace("\\/", "/")
    values: list[str] = []
    for field in URL_FIELDS:
        values.extend(
            re.findall(
                rf'["\']{re.escape(field)}["\']\s*:\s*["\']([^"\']+)',
                normalized_body,
                flags=re.IGNORECASE,
            )
        )
    values.extend(
        re.findall(
            r"https?://[^\s<>\"']+",
            normalized_body,
            flags=re.IGNORECASE,
        )
    )
    values.extend(
        re.findall(
            r'["\']((?:/|\.\./)(?:news|article|story|post|blog|press|release|finance|tech|business|video|watch|shorts|live)[^"\']+)',
            normalized_body,
            flags=re.IGNORECASE,
        )
    )

    # YouTube and similar hydrated apps expose stable content identifiers even
    # when no usable anchor elements are server-rendered.
    if generic.source_kind(source_url) == "youtube":
        for video_id in re.findall(
            r'["\']videoId["\']\s*:\s*["\']([A-Za-z0-9_-]{11})',
            normalized_body,
        ):
            values.append(f"https://www.youtube.com/watch?v={video_id}")

    result: list[str] = []
    for raw in _unique(values, 200):
        candidate = unwrap_search_result(urljoin(source_url, raw)).split("#", 1)[0]
        if not candidate.startswith(("http://", "https://")):
            continue
        if not _same_source_family(candidate, source_url, generic):
            continue
        path = urlsplit(candidate).path.casefold()
        kind = generic.source_kind(source_url)
        if kind == "youtube" and not any(
            token in path for token in ("/watch", "/shorts/", "/live/")
        ):
            continue
        if kind == "bilibili" and "/video/" not in path:
            continue
        if candidate.rstrip("/") == source_url.rstrip("/"):
            continue
        result.append(candidate)
    return _unique(result, MAX_SECOND_STAGE_CANDIDATES)


def _xml_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _sitemap_rows(body: str) -> tuple[list[tuple[str, str]], list[str]]:
    root = ET.fromstring(body)
    urls: list[tuple[str, str]] = []
    indexes: list[str] = []
    for node in root.iter():
        if _xml_local(node.tag) not in {"url", "sitemap"}:
            continue
        loc = ""
        lastmod = ""
        for child in node:
            local = _xml_local(child.tag)
            if local == "loc":
                loc = " ".join(child.itertext()).strip()
            elif local == "lastmod":
                lastmod = " ".join(child.itertext()).strip()
        if not loc:
            continue
        if _xml_local(node.tag) == "sitemap":
            indexes.append(loc)
        else:
            urls.append((loc, lastmod))
    return urls, indexes


def _url_score(url: str, lastmod: str, keywords: Sequence[str], generic: Any) -> int:
    path = urlsplit(url).path.casefold()
    score = 0
    if any(token in path for token in generic.ARTICLE_PATHS):
        score += 8
    if re.search(r"/20\d{2}(?:/|-)\d{1,2}", path):
        score += 4
    if re.search(r"\d{6,}", path):
        score += 2
    score += 4 * sum(1 for term in keywords[:24] if term.casefold() in path)
    if lastmod:
        score += 2
    return score


def sitemap_candidates(
    source_url: str,
    keywords: Sequence[str],
    user_agent: str,
    crawler: Any,
    generic: Any,
) -> tuple[list[str], int, list[str]]:
    """Discover bounded same-site candidates from common and indexed sitemaps."""

    parts = urlsplit(source_url)
    root_url = f"{parts.scheme}://{parts.netloc}"
    queue = [urljoin(root_url, path) for path in COMMON_SITEMAPS]
    fetched = 0
    errors: list[str] = []
    rows: list[tuple[str, str]] = []
    seen_sitemaps: set[str] = set()

    while queue and fetched < MAX_SITEMAP_FETCHES:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        try:
            body = crawler.fetch_text(sitemap_url, user_agent, attempts=1)
            fetched += 1
            found_rows, child_indexes = _sitemap_rows(body)
            rows.extend(found_rows)
            for child in child_indexes:
                if (
                    _same_source_family(child, source_url, generic)
                    and child not in seen_sitemaps
                ):
                    queue.append(child)
        except Exception as exc:
            errors.append(f"sitemap {type(exc).__name__}: {exc}")

    scored: list[tuple[int, str, str]] = []
    for raw_url, lastmod in rows:
        candidate = html.unescape(raw_url).strip()
        if not _same_source_family(candidate, source_url, generic):
            continue
        score = _url_score(candidate, lastmod, keywords, generic)
        if score >= 4:
            scored.append((score, lastmod, candidate))
    scored.sort(reverse=True)
    return (
        _unique((url for _, _, url in scored), MAX_SECOND_STAGE_CANDIDATES),
        fetched,
        errors,
    )


def _search_query(keywords: Sequence[str], language: str, generic: Any) -> str:
    terms = _unique(
        [*keywords[:12], *generic.EVENT_TERMS.get(language, generic.EVENT_TERMS["multi"])],
        20,
    )
    return " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)


def native_search_candidates(
    source_url: str,
    keywords: Sequence[str],
    language: str,
    user_agent: str,
    crawler: Any,
    generic: Any,
) -> tuple[list[str], int, list[str]]:
    """Inspect a public site/search page, then extract embedded destination URLs."""

    kind = generic.source_kind(source_url)
    query = _search_query(keywords, language, generic)
    if kind == "youtube":
        search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
    elif kind == "bilibili":
        search_url = "https://search.bilibili.com/all?keyword=" + quote_plus(query)
    else:
        domain = generic.registrable_domain(urlsplit(source_url).hostname or "")
        search_url = "https://www.bing.com/search?q=" + quote_plus(
            f"site:{domain} ({query})"
        )

    try:
        body = crawler.fetch_text(search_url, user_agent, attempts=1)
    except Exception as exc:
        return [], 0, [f"search-page {type(exc).__name__}: {exc}"]

    candidates = embedded_candidates(source_url, body, generic)
    parser = generic.PageParser()
    parser.feed(body)
    for href, _label in parser.links:
        destination = unwrap_search_result(urljoin(search_url, href))
        if _same_source_family(destination, source_url, generic):
            candidates.append(destination)
    return _unique(candidates, MAX_SECOND_STAGE_CANDIDATES), 1, []


def crawl_with_second_stage(
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
    generic: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the primary adapter and bounded fallback strategies when yield is low."""

    base_items, base_status = generic.crawl_generic_source(spec, user_agent, crawler)
    max_items = max(1, int(spec.get("maxItems", 10)))
    source_url = str(spec.get("sourceUrl") or spec.get("url") or "").strip()
    language = str(spec.get("sourceLanguage") or "")
    errors: list[str] = []
    scanned = int(base_status.get("scanned", 0) or 0)
    items = list(base_items)
    strategies = ["primary"]

    if len(items) >= min(3, max_items):
        enriched = dict(base_status)
        enriched["adapter"] = "generic-web-v2"
        enriched["strategies"] = strategies
        return items[:max_items], enriched

    source_body = ""
    try:
        source_body = crawler.fetch_text(source_url, user_agent, attempts=1)
        scanned += 1
    except Exception as exc:
        errors.append(f"source {type(exc).__name__}: {exc}")
    language = generic.detect_language(source_url, source_body, language)
    keywords = generic.localize_keywords(spec.get("keywords", []), language)
    runtime_spec = {
        **spec,
        "sourceUrl": source_url,
        "keywords": keywords,
        "platform": generic.platform_name(spec),
    }

    candidates: list[str] = []
    if source_body:
        structured = embedded_candidates(source_url, source_body, generic)
        if structured:
            strategies.append("structured-data")
            candidates.extend(structured)

    sitemap_urls, sitemap_scanned, sitemap_errors = sitemap_candidates(
        source_url,
        keywords,
        user_agent,
        crawler,
        generic,
    )
    scanned += sitemap_scanned
    errors.extend(sitemap_errors)
    if sitemap_urls:
        strategies.append("sitemap")
        candidates.extend(sitemap_urls)

    search_urls, search_scanned, search_errors = native_search_candidates(
        source_url,
        keywords,
        language,
        user_agent,
        crawler,
        generic,
    )
    scanned += search_scanned
    errors.extend(search_errors)
    if search_urls:
        strategies.append("search-page")
        candidates.extend(search_urls)

    existing_urls = {
        crawler.normalize_url(
            str(
                (item.get("source") or {}).get("url", "")
                if isinstance(item.get("source"), dict)
                else ""
            )
        )
        for item in items
    }
    for candidate in _unique(candidates, MAX_SECOND_STAGE_CANDIDATES):
        if len(items) >= max_items:
            break
        normalized = crawler.normalize_url(candidate)
        if not normalized or normalized in existing_urls:
            continue
        try:
            body = crawler.fetch_text(candidate, user_agent, attempts=1)
            scanned += 1
            article = generic.parse_article(
                runtime_spec,
                candidate,
                body,
                crawler,
                keywords,
            )
            if article:
                items.append(article)
                existing_urls.add(normalized)
        except Exception as exc:
            errors.append(f"candidate {type(exc).__name__}: {exc}")

    items = generic._dedupe(items, crawler)[:max_items]
    combined_failures = int(base_status.get("failed", 0) or 0) + len(errors)
    status = (
        "ok"
        if items and combined_failures == 0
        else "partial"
        if items
        else "error"
        if combined_failures
        else "empty"
    )
    result = crawler._status(
        spec["id"],
        generic.platform_name(spec),
        status,
        scanned,
        len(items),
        failed=combined_failures,
        platform=generic.platform_name(spec),
        error="; ".join(errors[:3]) if errors and not items else None,
    )
    result["adapter"] = "generic-web-v2"
    result["detectedLanguage"] = language
    result["strategies"] = strategies
    return items, result
