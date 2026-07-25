#!/usr/bin/env python3
"""Crawl the fixed company registry plus user-configured website sources."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:  # Imported by tests as tools.crawl_official_with_tracking.
    from . import crawl_official_companies as official
    from .crawl_with_tracking import TRACKING_PATH, load_tracking
except ImportError:  # Executed directly with ``python tools/...``.
    import crawl_official_companies as official
    from crawl_with_tracking import TRACKING_PATH, load_tracking


USER_OFFICIAL_PREFIX = "official-user-"
EASTMONEY_INDEX_URLS = (
    "https://fund.eastmoney.com/a/cjjyw.html",
    "https://fund.eastmoney.com/a/cjjgd.html",
    "https://finance.eastmoney.com/",
)
EASTMONEY_ARTICLE_PATTERN = r"/a/20\d{12,}\.html$"
EASTMONEY_INDEX_PATTERN = re.compile(
    r"/(?:a|news)/(?:cjjyw|cjjgd|cjjyj)(?:_\d+)?\.html$",
    flags=re.IGNORECASE,
)
EASTMONEY_BODY_IDS = {
    "contentbody",
    "articlebody",
    "articlecontent",
    "newscontent",
}
EASTMONEY_BODY_CLASSES = {
    "newscontent",
    "articlecontent",
    "article-body",
    "contentbody",
}
EASTMONEY_BOILERPLATE_MARKERS = (
    "东方财富app",
    "手机查看",
    "微信扫一扫",
    "分享到您的朋友圈",
    "文章来源",
    "责任编辑",
    "免责声明",
    "风险提示",
    "郑重声明",
)


class EastmoneyBodyParser(HTMLParser):
    """Extract paragraphs from Eastmoney's article-body containers."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self._capture_depth = 0
        self._paragraph_depth = 0
        self._paragraph_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        lowered = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        element_id = values.get("id", "").casefold()
        class_tokens = {
            token.casefold() for token in values.get("class", "").split() if token
        }
        is_container = (
            element_id in EASTMONEY_BODY_IDS
            or bool(class_tokens & EASTMONEY_BODY_CLASSES)
        )

        if self._capture_depth:
            self._capture_depth += 1
        elif is_container:
            self._capture_depth = 1

        if self._capture_depth and lowered in {"p", "h2", "h3"}:
            if not self._paragraph_depth:
                self._paragraph_parts = []
            self._paragraph_depth += 1
        elif self._capture_depth and lowered == "br" and self._paragraph_depth:
            self._paragraph_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._capture_depth and self._paragraph_depth:
            self._paragraph_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if (
            self._capture_depth
            and self._paragraph_depth
            and lowered in {"p", "h2", "h3"}
        ):
            self._paragraph_depth -= 1
            if not self._paragraph_depth:
                text = official.clean_text(" ".join(self._paragraph_parts))
                if text:
                    self.paragraphs.append(text)
                self._paragraph_parts = []
        if self._capture_depth:
            self._capture_depth -= 1


def _clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return text[:54] or "source"


def _root_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def _normalized_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _is_eastmoney_source(company: str, urls: list[str]) -> bool:
    return "东方财富" in company or any(
        _normalized_host(url).endswith("eastmoney.com") for url in urls
    )


def _is_eastmoney_article_url(url: str) -> bool:
    return _normalized_host(url).endswith("eastmoney.com") and bool(
        re.search(EASTMONEY_ARTICLE_PATTERN, urlsplit(url).path, flags=re.IGNORECASE)
    )


def _useful_eastmoney_paragraph(text: str) -> bool:
    folded = official.clean_text(text).casefold()
    return (
        len(folded) >= 18
        and not any(marker in folded for marker in EASTMONEY_BOILERPLATE_MARKERS)
    )


def _eastmoney_summary(body: str, limit: int = 500) -> str:
    parser = EastmoneyBodyParser()
    parser.feed(body)
    paragraphs = parser.paragraphs

    # Older Eastmoney templates occasionally omit the usual container id. In
    # that case, inspect paragraph tags but keep the same boilerplate filter.
    if not paragraphs:
        paragraphs = [
            official.strip_html(fragment)
            for fragment in re.findall(
                r"<p\b[^>]*>(.*?)</p>", body, flags=re.IGNORECASE | re.DOTALL
            )
        ]

    selected: list[str] = []
    seen: set[str] = set()
    for raw in paragraphs:
        text = official.clean_text(raw)
        key = text.casefold()
        if not _useful_eastmoney_paragraph(text) or key in seen:
            continue
        candidate = " ".join([*selected, text])
        if len(candidate) > limit:
            remaining = limit - len(" ".join(selected)) - (1 if selected else 0)
            if remaining >= 60:
                selected.append(text[:remaining].rstrip("，。；; ") + "…")
            break
        selected.append(text)
        seen.add(key)
        if len(" ".join(selected)) >= 320 or len(selected) >= 3:
            break
    return " ".join(selected)[:limit].rstrip()


def _is_probable_non_article(article: dict[str, Any]) -> bool:
    """Reject author profiles, channel indexes and other pages presented as articles."""

    title = _clean(article.get("title"), 240).casefold()
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    url = _clean(source.get("url"), 500)
    host = _normalized_host(url)
    path = urlsplit(url).path.casefold().rstrip("/")

    if host.endswith("eastmoney.com"):
        if EASTMONEY_INDEX_PATTERN.search(path):
            return True
        if title.startswith(("基金要闻", "基金观点", "基金研究")):
            return True

    title_markers = (
        "的文章_",
        "的文章 -",
        "的文章 |",
        "articles by ",
        "author profile",
        "作者主页",
        "个人主页",
        "全部文章",
        "文章列表",
    )
    if any(marker in title for marker in title_markers):
        return True

    profile_patterns = (
        r"/(?:author|authors|profile|profiles|columnist|contributors?)/[^/]+$",
        r"/(?:media|user|users|member|members)/(?:m|u|user)?\d+$",
        r"/(?:tag|tags|category|categories|channel|channels)/[^/]+$",
    )
    return any(re.search(pattern, path) for pattern in profile_patterns)


def _sanitize_user_article(article: dict[str, Any]) -> dict[str, Any]:
    """User-added sources are sources, not guaranteed catalog company entities."""

    cleaned = dict(article)
    cleaned.pop("companySlug", None)
    return cleaned


def build_user_specs(tracking: dict[str, Any]) -> list[official.CompanySpec]:
    """Convert enabled website sources into official-site crawler specifications.

    RSS sources stay in ``crawl_with_tracking.py`` because the official crawler is
    designed for newsrooms, company websites and website indexes. SEC sources are
    handled by the main crawler's EDGAR adapter.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in tracking.get("sources", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        if _clean(raw.get("sourceType"), 30) != "listing-search":
            continue
        url = _clean(raw.get("url"), 500)
        company = _clean(raw.get("company"), 80) or _clean(raw.get("name"), 80)
        if not company or not re.match(r"^https?://", url, flags=re.IGNORECASE):
            continue
        grouped[company.casefold()].append(raw)

    specs: list[official.CompanySpec] = []
    used_slugs: set[str] = set()
    for rows in grouped.values():
        first = rows[0]
        company = _clean(first.get("company"), 80) or _clean(first.get("name"), 80)
        slug_base = f"user-{_slug(company)}"
        slug = slug_base
        suffix = 2
        while slug in used_slugs:
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        used_slugs.add(slug)

        urls: list[str] = []
        aliases: list[str] = [company]
        keywords: list[str] = []
        ticker = ""
        for row in rows:
            url = official.normalize_url(_clean(row.get("url"), 500))
            if url and url not in urls:
                urls.append(url)
            ticker_value = _clean(row.get("ticker"), 30).upper()
            if ticker_value:
                ticker = ticker or ticker_value
                aliases.append(ticker_value)
            for keyword in row.get("keywords", []):
                cleaned = _clean(keyword, 80)
                if cleaned:
                    keywords.append(cleaned)

        is_eastmoney = _is_eastmoney_source(company, urls)
        if is_eastmoney:
            # The configured Eastmoney homepage is a portal. Add the fund/news
            # indexes that expose concrete article links and permit their related
            # finance subdomain. The article pattern below gives those detail URLs
            # priority while channel pages are discarded by the sanitizer.
            for seed_url in EASTMONEY_INDEX_URLS:
                normalized = official.normalize_url(seed_url)
                if normalized not in urls:
                    urls.append(normalized)

        homepage = _root_url(urls[0])
        region = _clean(first.get("region"), 20)
        if region not in {"中国", "美国", "全球"}:
            region = "全球"
        sector = _clean(first.get("sector"), 60) or "AI / AGI"
        sitemap_urls = tuple(
            dict.fromkeys(
                f"{_root_url(url).rstrip('/')}/sitemap.xml" for url in urls
            )
        )
        entity_aliases = tuple(dict.fromkeys([*aliases, *keywords]))
        article_url_patterns = [
            r"/(?:news|newsroom|press|blog|updates?)/",
            r"/(?:investors?|investor-relations|ir)/",
            r"/(?:announcements?|filings?|financials?)/",
            r"/20\d{2}/",
        ]
        if is_eastmoney:
            article_url_patterns.insert(0, EASTMONEY_ARTICLE_PATTERN)

        specs.append(
            official.CompanySpec(
                slug=slug,
                name=company,
                region=region,
                sector=sector,
                homepage=homepage,
                news_urls=tuple(urls),
                sitemap_urls=sitemap_urls,
                aliases=tuple(dict.fromkeys(alias for alias in aliases if alias != company)),
                entity_aliases=entity_aliases,
                article_url_patterns=tuple(article_url_patterns),
                require_entity_match=False,
                max_items=6,
                max_candidate_links=24,
                max_age_days=730,
                request_timeout=10,
            )
        )
    return specs[:40]


def install_overrides(
    base_specs: list[official.CompanySpec], user_specs: list[official.CompanySpec]
) -> None:
    original_load_payload = official.load_existing_payload
    original_article_from_page = official._article_from_page
    active_ids = {spec.source_id for spec in user_specs}

    def load_registry(
        path: Path = official.REGISTRY_PATH,
        catalog_path: Path = official.CATALOG_PATH,
    ) -> list[official.CompanySpec]:
        del path, catalog_path
        return [*base_specs, *user_specs]

    def article_from_page(
        spec: official.CompanySpec, candidate_url: str, body: str
    ) -> dict[str, Any] | None:
        article = original_article_from_page(spec, candidate_url, body)
        if not article or not spec.source_id.startswith(USER_OFFICIAL_PREFIX):
            return article
        if _is_probable_non_article(article):
            return None
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        article_url = _clean(source.get("url"), 500) or candidate_url
        if _is_eastmoney_article_url(article_url):
            summary = _eastmoney_summary(body)
            if summary:
                article["summary"] = summary
        return _sanitize_user_article(article)

    def load_payload(path: Path = official.OUTPUT_PATH) -> dict[str, Any]:
        payload = original_load_payload(path)
        retained_articles: list[dict[str, Any]] = []
        for raw in payload.get("articles", []):
            article = dict(raw)
            source_id = str(article.get("sourceId", ""))
            source = article.get("source") if isinstance(article.get("source"), dict) else {}
            source_url = _clean(source.get("url"), 500)

            # Eastmoney listing-search used to run through both the generic Bing
            # adapter and this direct crawler. Keep the direct article crawl and
            # remove the generic portal/index duplicate batch from the snapshot.
            if (
                source_id.startswith("user-source-")
                and _normalized_host(source_url).endswith("eastmoney.com")
            ):
                continue

            if source_id.startswith(USER_OFFICIAL_PREFIX):
                if source_id not in active_ids or _is_probable_non_article(article):
                    continue
                article = _sanitize_user_article(article)
            retained_articles.append(article)
        payload["articles"] = retained_articles

        payload["sourceStatus"] = [
            status
            for status in payload.get("sourceStatus", [])
            if not str(status.get("id", "")).startswith(USER_OFFICIAL_PREFIX)
            or str(status.get("id", "")) in active_ids
        ]
        return payload

    official.load_registry = load_registry
    official.load_existing_payload = load_payload
    official._article_from_page = article_from_page


def main() -> int:
    base_specs = official.load_registry()
    tracking = load_tracking(TRACKING_PATH)
    user_specs = build_user_specs(tracking)
    install_overrides(base_specs, user_specs)
    print(
        json.dumps(
            {
                "fixedOfficialCompanies": len(base_specs),
                "userWebsiteSources": len(user_specs),
            },
            ensure_ascii=False,
        )
    )
    return official.main()


if __name__ == "__main__":
    raise SystemExit(main())
