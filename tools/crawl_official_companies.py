#!/usr/bin/env python3
"""Crawl official news for every company in the public company catalog.

The main crawler intentionally keeps source-specific adapters small. This module
adds a registry-driven layer for the complete 58-company catalog without
hard-coding each company in ``crawl_articles.py``. It prefers direct official
news, newsroom, blog and investor-relations pages, discovers RSS/Atom feeds and
article links on those pages, and uses a domain-restricted public search index
only to discover official URLs when a site exposes no usable index.

All accepted records are bound to the registry's exact ``companySlug``. This
prevents a company mentioned incidentally in an article summary from becoming
the article's primary company.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote_plus, urljoin, urlsplit

try:  # Imported by tests as tools.crawl_official_companies.
    from .crawl_articles import (
        DEFAULT_USER_AGENT,
        OUTPUT_PATH,
        ROOT,
        ArticleHTMLParser,
        _published_value,
        _source,
        article_id,
        clean_text,
        clean_title,
        evaluate_quality,
        fetch_text,
        infer_event_type,
        load_config,
        load_existing_payload,
        merge_source_status,
        normalize_date,
        normalize_url,
        replace_source_batches,
        strip_html,
        write_if_changed,
    )
except ImportError:  # Executed directly with ``python tools/...``.
    from crawl_articles import (
        DEFAULT_USER_AGENT,
        OUTPUT_PATH,
        ROOT,
        ArticleHTMLParser,
        _published_value,
        _source,
        article_id,
        clean_text,
        clean_title,
        evaluate_quality,
        fetch_text,
        infer_event_type,
        load_config,
        load_existing_payload,
        merge_source_status,
        normalize_date,
        normalize_url,
        replace_source_batches,
        strip_html,
        write_if_changed,
    )


REGISTRY_PATH = ROOT / "config" / "official_company_sources.json"
NEWS_PATH_HINTS = (
    "/news",
    "/newsroom",
    "/press",
    "/media",
    "/blog",
    "/updates",
    "/articles",
    "/insights",
    "/stories",
    "/resources",
    "/announcements",
    "/news-releases",
    "/press-releases",
)
NEWS_TEXT_HINTS = (
    "news",
    "newsroom",
    "press",
    "media",
    "blog",
    "update",
    "announcement",
    "release",
    "insight",
    "article",
    "新闻",
    "动态",
    "资讯",
    "公告",
    "媒体",
    "博客",
)
SKIP_PATH_HINTS = (
    "/about",
    "/company",
    "/careers",
    "/jobs",
    "/contact",
    "/privacy",
    "/terms",
    "/legal",
    "/products",
    "/solutions",
    "/events",
    "/tag/",
    "/category/",
    "/author/",
)
GENERIC_TITLES = {
    "news",
    "newsroom",
    "press",
    "press releases",
    "blog",
    "updates",
    "articles",
    "insights",
    "media",
    "新闻",
    "新闻中心",
    "公司动态",
    "资讯中心",
}


@dataclass(frozen=True)
class CompanySpec:
    slug: str
    name: str
    region: str
    sector: str
    homepage: str
    news_urls: tuple[str, ...]
    aliases: tuple[str, ...]
    max_items: int
    max_candidate_links: int
    max_age_days: int
    request_timeout: int

    @property
    def source_id(self) -> str:
        return f"official-{self.slug}"

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        hosts: list[str] = []
        for raw_url in (self.homepage, *self.news_urls):
            host = (urlsplit(raw_url).hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            if host and host not in hosts:
                hosts.append(host)
        return tuple(hosts)


class OfficialIndexParser(HTMLParser):
    """Collect anchors and feed links without retaining page text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self.feeds: list[str] = []
        self._href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        lowered = tag.lower()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._anchor_text = []
        elif lowered == "link" and values.get("href"):
            relation = values.get("rel", "").lower()
            media_type = values.get("type", "").lower()
            if "alternate" in relation and media_type in {
                "application/rss+xml",
                "application/atom+xml",
                "application/feed+json",
            }:
                self.feeds.append(values["href"])

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, clean_text(" ".join(self._anchor_text))))
            self._href = None
            self._anchor_text = []


class FeedLinkParser:
    """Extract destination URLs from RSS/Atom search output."""

    @staticmethod
    def links(body: str) -> list[str]:
        root = ET.fromstring(body)
        links: list[str] = []
        for node in root.iter():
            local = node.tag.rsplit("}", 1)[-1].lower()
            if local not in {"item", "entry"}:
                continue
            candidate = ""
            for child in node.iter():
                if child.tag.rsplit("}", 1)[-1].lower() != "link":
                    continue
                candidate = clean_text(child.attrib.get("href", "")) or clean_text(
                    child.text or ""
                )
                if candidate:
                    break
            if candidate and candidate not in links:
                links.append(candidate)
        return links


def load_registry(path: Path = REGISTRY_PATH) -> list[CompanySpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    defaults = payload.get("defaults", {})
    raw_companies = payload.get("companies", [])
    if not isinstance(raw_companies, list):
        raise ValueError("official company registry must contain a companies array")
    specs: list[CompanySpec] = []
    for raw in raw_companies:
        spec = CompanySpec(
            slug=clean_text(str(raw.get("slug", ""))),
            name=clean_text(str(raw.get("name", ""))),
            region=clean_text(str(raw.get("region", ""))),
            sector=clean_text(str(raw.get("sector", ""))),
            homepage=normalize_url(str(raw.get("homepage", ""))),
            news_urls=tuple(
                normalize_url(str(url)) for url in raw.get("newsUrls", []) if url
            ),
            aliases=tuple(
                clean_text(str(alias)) for alias in raw.get("aliases", []) if alias
            ),
            max_items=int(raw.get("maxItems", defaults.get("maxItems", 4))),
            max_candidate_links=int(
                raw.get(
                    "maxCandidateLinks", defaults.get("maxCandidateLinks", 10)
                )
            ),
            max_age_days=int(raw.get("maxAgeDays", defaults.get("maxAgeDays", 730))),
            request_timeout=int(
                raw.get("requestTimeout", defaults.get("requestTimeout", 10))
            ),
        )
        missing = [
            field
            for field, value in (
                ("slug", spec.slug),
                ("name", spec.name),
                ("region", spec.region),
                ("sector", spec.sector),
                ("homepage", spec.homepage),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"registry entry missing {','.join(missing)}: {raw}")
        if not spec.allowed_hosts:
            raise ValueError(f"registry entry has no valid official host: {spec.slug}")
        specs.append(spec)
    slugs = [spec.slug for spec in specs]
    if len(slugs) != len(set(slugs)):
        raise ValueError("official company registry contains duplicate slugs")
    if len(specs) < 58:
        raise ValueError(f"official company registry covers only {len(specs)} companies")
    return specs


def _host_allowed(url: str, allowed_hosts: Sequence[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def _path_date(url: str) -> str | None:
    path = urlsplit(url).path
    for pattern in (
        r"/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|$)",
        r"/(20\d{2})-(\d{1,2})-(\d{1,2})(?:/|$)",
    ):
        match = re.search(pattern, path)
        if not match:
            continue
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    return None


def _candidate_score(url: str, anchor_text: str) -> int:
    parts = urlsplit(url)
    path = parts.path.casefold()
    text = anchor_text.casefold()
    if not path or path == "/":
        return -100
    if any(hint in path for hint in SKIP_PATH_HINTS):
        return -100
    score = 0
    if any(hint in path for hint in NEWS_PATH_HINTS):
        score += 5
    if any(hint in text for hint in NEWS_TEXT_HINTS):
        score += 3
    if re.search(r"/20\d{2}(?:/|-)", path):
        score += 3
    if len([part for part in path.split("/") if part]) >= 2:
        score += 1
    if parts.query:
        score -= 1
    return score


def discover_candidate_urls(
    index_url: str,
    body: str,
    allowed_hosts: Sequence[str],
    limit: int,
) -> tuple[list[str], list[str]]:
    parser = OfficialIndexParser()
    parser.feed(body)
    scored: dict[str, int] = {}
    for href, text in parser.anchors:
        absolute = normalize_url(urljoin(index_url, href))
        if absolute == normalize_url(index_url) or not _host_allowed(
            absolute, allowed_hosts
        ):
            continue
        score = _candidate_score(absolute, text)
        if score >= 4:
            scored[absolute] = max(score, scored.get(absolute, -100))
    candidates = [
        url
        for url, _ in sorted(
            scored.items(), key=lambda item: (item[1], item[0]), reverse=True
        )[:limit]
    ]
    feeds = []
    for href in parser.feeds:
        absolute = normalize_url(urljoin(index_url, href))
        if _host_allowed(absolute, allowed_hosts) and absolute not in feeds:
            feeds.append(absolute)
    return candidates, feeds


def _article_from_page(
    spec: CompanySpec, url: str, body: str
) -> dict[str, Any] | None:
    parser = ArticleHTMLParser()
    parser.feed(body)
    canonical_url = normalize_url(parser.meta.get("og:url", "") or url)
    if not _host_allowed(canonical_url, spec.allowed_hosts):
        return None
    raw_title = next(
        (
            value
            for value in (
                parser.meta.get("og:title", ""),
                parser.text("h1"),
                parser.text("title"),
            )
            if clean_title(value)
        ),
        "",
    )
    title = clean_title(raw_title)
    for suffix in (spec.name, *spec.aliases):
        title = re.sub(
            rf"\s*(?:\||—|–|-)\s*{re.escape(suffix)}\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
    title = clean_text(title)
    if (
        len(title) < 8
        or title.casefold() in GENERIC_TITLES
        or title.casefold() == spec.name.casefold()
    ):
        return None
    published_at = normalize_date(_published_value(parser, body)) or _path_date(
        canonical_url
    )
    if not published_at:
        return None
    published_date = date.fromisoformat(published_at)
    if published_date < datetime.now(UTC).date() - timedelta(days=spec.max_age_days):
        return None
    summary = strip_html(
        parser.meta.get("description", "")
        or parser.meta.get("og:description", "")
        or parser.meta.get("twitter:description", "")
    )
    if not summary:
        summary = f"{spec.name} 发布“{title}”；完整事实、数据与附件见官方原文。"
    event_type, importance = infer_event_type(title, summary)
    return {
        "id": article_id(spec.source_id, canonical_url),
        "sourceId": spec.source_id,
        "title": title[:220],
        "summary": summary[:500].rstrip(),
        "type": event_type,
        "region": spec.region,
        "sector": spec.sector,
        "company": spec.name,
        "companySlug": spec.slug,
        "publishedAt": published_at,
        "importance": max(importance, 80),
        "source": _source(spec.name, canonical_url, "官方披露", "官方网站"),
    }


def _candidate_urls_from_feed(
    feed_url: str,
    body: str,
    allowed_hosts: Sequence[str],
    limit: int,
) -> list[str]:
    candidates: list[str] = []
    try:
        for url in FeedLinkParser.links(body):
            absolute = normalize_url(urljoin(feed_url, url))
            if _host_allowed(absolute, allowed_hosts) and absolute not in candidates:
                candidates.append(absolute)
            if len(candidates) >= limit:
                break
    except ET.ParseError:
        return []
    return candidates


def _search_official_urls(
    spec: CompanySpec, user_agent: str
) -> list[str]:
    discovered: list[str] = []
    for host in spec.allowed_hosts[:2]:
        query = (
            f'site:{host} "{spec.name}" '
            "(news OR newsroom OR blog OR update OR press OR 新闻 OR 动态 OR 公告)"
        )
        search_url = f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"
        try:
            body = fetch_text(
                search_url,
                user_agent,
                timeout=min(spec.request_timeout, 8),
                attempts=1,
            )
            for url in FeedLinkParser.links(body):
                normalized = normalize_url(url)
                if (
                    _host_allowed(normalized, spec.allowed_hosts)
                    and normalized not in discovered
                    and _candidate_score(normalized, "news") >= 4
                ):
                    discovered.append(normalized)
                if len(discovered) >= spec.max_candidate_links:
                    return discovered
        except Exception:
            continue
    return discovered


def crawl_company(
    spec: CompanySpec, user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    index_urls = list(spec.news_urls) or [spec.homepage]
    if spec.homepage not in index_urls:
        index_urls.append(spec.homepage)
    candidate_urls: list[str] = []
    feed_urls: list[str] = []
    failures = 0
    scanned_indexes = 0
    for index_url in index_urls:
        try:
            body = fetch_text(
                index_url,
                user_agent,
                timeout=spec.request_timeout,
                attempts=2,
            )
            scanned_indexes += 1
            candidates, feeds = discover_candidate_urls(
                index_url,
                body,
                spec.allowed_hosts,
                spec.max_candidate_links,
            )
            for candidate in candidates:
                if candidate not in candidate_urls:
                    candidate_urls.append(candidate)
            for feed in feeds:
                if feed not in feed_urls:
                    feed_urls.append(feed)
        except Exception:
            failures += 1

    for feed_url in feed_urls[:3]:
        try:
            body = fetch_text(
                feed_url,
                user_agent,
                timeout=spec.request_timeout,
                attempts=2,
            )
            for candidate in _candidate_urls_from_feed(
                feed_url,
                body,
                spec.allowed_hosts,
                spec.max_candidate_links,
            ):
                if candidate not in candidate_urls:
                    candidate_urls.append(candidate)
        except Exception:
            failures += 1

    if not candidate_urls:
        candidate_urls.extend(_search_official_urls(spec, user_agent))

    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for candidate in candidate_urls[: spec.max_candidate_links]:
        try:
            body = fetch_text(
                candidate,
                user_agent,
                timeout=spec.request_timeout,
                attempts=2,
            )
            article = _article_from_page(spec, candidate, body)
            if article and article["source"]["url"] not in seen_urls:
                articles.append(article)
                seen_urls.add(article["source"]["url"])
        except Exception:
            failures += 1

    articles.sort(
        key=lambda item: (
            item.get("publishedAt", ""),
            int(item.get("importance", 0)),
            item.get("id", ""),
        ),
        reverse=True,
    )
    articles = articles[: spec.max_items]
    status = "ok" if articles and failures == 0 else "partial" if articles else "empty"
    elapsed = time.monotonic() - started
    print(
        f"official={spec.slug} status={status} accepted={len(articles)} "
        f"candidates={len(candidate_urls)} indexes={scanned_indexes} "
        f"failures={failures} seconds={elapsed:.2f}",
        file=sys.stderr,
    )
    result: dict[str, Any] = {
        "id": spec.source_id,
        "name": f"{spec.name} 官方动态",
        "status": status,
        "scanned": len(candidate_urls) + scanned_indexes,
        "accepted": len(articles),
        "failed": failures,
        "platform": "官方网站",
    }
    if not articles and failures:
        result["error"] = "official indexes returned no dated article pages"
    return articles, result


def crawl_all_companies(
    specs: Sequence[CompanySpec], user_agent: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(specs))) as executor:
        future_map = {
            executor.submit(crawl_company, spec, user_agent): spec for spec in specs
        }
        for future in as_completed(future_map):
            spec = future_map[future]
            try:
                incoming, status = future.result()
                articles.extend(incoming)
                statuses.append(status)
            except Exception as exc:
                statuses.append(
                    {
                        "id": spec.source_id,
                        "name": f"{spec.name} 官方动态",
                        "status": "error",
                        "scanned": 0,
                        "accepted": 0,
                        "failed": 1,
                        "platform": "官方网站",
                        "error": f"{type(exc).__name__}: {exc}"[:240],
                    }
                )
                print(
                    f"official={spec.slug} fatal={type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
    return articles, sorted(statuses, key=lambda item: item["id"])


def main() -> int:
    specs = load_registry()
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    payload = load_existing_payload()
    incoming, statuses = crawl_all_companies(specs, user_agent)
    merged = replace_source_batches(payload.get("articles", []), incoming, statuses)
    source_status = merge_source_status(payload.get("sourceStatus", []), statuses)
    quality = evaluate_quality(merged, source_status, load_config().get("qualityGate", {}))
    result = {
        "registeredCompanies": len(specs),
        "companiesWithArticles": sum(status.get("accepted", 0) > 0 for status in statuses),
        "incoming": len(incoming),
        "total": len(merged),
        "qualityPassed": quality["passed"],
    }
    if not quality["passed"]:
        print("Official-company quality gate failed; previous snapshot retained.", file=sys.stderr)
        print(json.dumps({"result": result, "qualityGate": quality}, ensure_ascii=False))
        return 1
    write_if_changed(
        merged,
        payload,
        company_facts=payload.get("companyFacts", {}),
        source_status=source_status,
        quality_gate=quality,
    )
    print(json.dumps(result, ensure_ascii=False))
    existing_official = any(
        str(item.get("sourceId", "")).startswith("official-")
        for item in payload.get("articles", [])
    )
    if not incoming and not existing_official:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
