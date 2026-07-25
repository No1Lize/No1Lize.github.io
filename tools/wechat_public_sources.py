#!/usr/bin/env python3
"""Sector-specific discovery and parsing for public WeChat articles.

The adapter discovers only publicly indexed ``mp.weixin.qq.com`` pages, fetches
those public pages directly, and stores a short factual summary rather than the
full copyrighted article body. It also records the public-account name, author,
and configured company/person mentions for downstream attribution.
"""

from __future__ import annotations

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any, Iterable, Sequence
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

WECHAT_HOST = "mp.weixin.qq.com"
MAX_QUERY_TERMS = 16
MAX_ITEMS_PER_TRACK = 6
WECHAT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
)
EVENT_TERMS = (
    "发布",
    "推出",
    "融资",
    "投资",
    "上市",
    "IPO",
    "研究",
    "突破",
    "合作",
    "签署",
    "报告",
    "论文",
    "访谈",
    "演讲",
    "观点",
    "表示",
    "指出",
    "任命",
    "离职",
    "量产",
    "投产",
)
GENERIC_DISCOVERY_TERMS = {
    "ai",
    "agi",
    "人工智能",
    "技术",
    "科技",
    "产业",
    "行业",
    "公司",
    "企业",
    "研究",
    "产品",
    "项目",
    "平台",
}
BLOCK_PAGE_MARKERS = (
    "环境异常",
    "访问过于频繁",
    "请在微信客户端打开链接",
    "该内容已被发布者删除",
    "此内容因违规无法查看",
    "当前环境存在异常",
)


def _clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()[:limit]


def _key(value: Any) -> str:
    return _clean(value, 200).normalize("NFKC") if False else _clean(value, 200).casefold()


def _unique(values: Iterable[Any], limit: int = 120) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 120)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _person_name(value: Any) -> str:
    text = _clean(value, 100).replace("＠", "@")
    text = re.sub(r"\s*@[A-Za-z0-9_]{1,15}\s*$", "", text)
    return text.strip(" ·•|｜-—–()（）[]【】")


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return text[:60] or "track"


def _quoted_terms(values: Sequence[str], limit: int = MAX_QUERY_TERMS) -> str:
    return " OR ".join(
        f'"{value.replace(chr(34), "")}"' for value in values[:limit] if value
    )


def generated_wechat_sources(
    tracks: Sequence[dict[str, Any]], tracking: Any
) -> list[dict[str, Any]]:
    """Create one independent WeChat discovery query for every enabled track."""

    sources: list[dict[str, Any]] = []
    event_query = _quoted_terms(list(EVENT_TERMS), 12)
    for track in tracks:
        companies = _unique(track.get("sampleCompanies", []), 20)
        people = _unique(
            _person_name(value) for value in track.get("people", []) if _person_name(value)
        , 20)
        keywords = _unique(track.get("keywords", []), 40)
        discovery_terms = _unique(
            [*companies[:6], *people[:5], *keywords[:10], track.get("name")],
            MAX_QUERY_TERMS,
        )
        if not discovery_terms:
            continue
        query = (
            "site:mp.weixin.qq.com/s "
            f"({_quoted_terms(discovery_terms)}) ({event_query})"
        )
        source_id = f"user-track-wechat-{_slug(track.get('slug') or track.get('name'))}"
        sources.append(
            {
                "id": source_id,
                "name": f"微信公众号 · {track['name']}",
                "url": f"https://www.bing.com/search?format=rss&q={quote_plus(query)}",
                "adapter": "wechat_search",
                "platform": "微信",
                "sourceLevel": "原始材料",
                "region": "中国",
                "sector": track["name"],
                "maxItems": MAX_ITEMS_PER_TRACK,
                "keywords": keywords,
                "trackedCompanies": companies,
                "trackedPeople": people,
                "strictTitleKeywords": False,
                "enabled": True,
            }
        )
    return sources


class WeChatPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.account_parts: list[str] = []
        self.author_parts: list[str] = []
        self.content_parts: list[str] = []
        self._capture: str | None = None
        self._capture_depth = 0
        self._content_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        tag = tag.casefold()
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").casefold()
            content = values.get("content", "").strip()
            if key and content:
                self.meta[key] = content
            return

        element_id = values.get("id", "")
        if element_id == "activity-name":
            self._capture = "title"
            self._capture_depth = 1
        elif element_id == "js_name":
            self._capture = "account"
            self._capture_depth = 1
        elif element_id == "js_author_name":
            self._capture = "author"
            self._capture_depth = 1
        elif self._capture:
            self._capture_depth += 1

        if element_id == "js_content":
            self._content_depth = 1
        elif self._content_depth:
            self._content_depth += 1
        if self._content_depth and tag in {"p", "section", "div", "br", "li"}:
            self.content_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth:
            self._capture_depth -= 1
            if self._capture_depth == 0:
                self._capture = None
        if self._content_depth:
            self._content_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture == "title":
            self.title_parts.append(data)
        elif self._capture == "account":
            self.account_parts.append(data)
        elif self._capture == "author":
            self.author_parts.append(data)
        if self._content_depth:
            self.content_parts.append(data)

    @property
    def title(self) -> str:
        return _clean(" ".join(self.title_parts), 260)

    @property
    def account(self) -> str:
        return _clean(" ".join(self.account_parts), 100)

    @property
    def author(self) -> str:
        return _clean(" ".join(self.author_parts), 100)

    @property
    def content(self) -> str:
        return _clean(" ".join(self.content_parts), 8000)


def _decode_js_string(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\\/", "/").replace("\\x26", "&")
    value = value.replace("\\x3c", "<").replace("\\x3e", ">")
    value = value.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")

    def replace_unicode(match: re.Match[str]) -> str:
        try:
            return chr(int(match.group(1), 16))
        except ValueError:
            return match.group(0)

    return _clean(re.sub(r"\\u([0-9a-fA-F]{4})", replace_unicode, value), 500)


def _js_value(body: str, names: Sequence[str]) -> str:
    for name in names:
        patterns = (
            rf"(?:var\s+)?{re.escape(name)}\s*=\s*['\"](.*?)['\"]\s*;",
            rf"['\"]{re.escape(name)}['\"]\s*:\s*['\"](.*?)['\"]",
        )
        for pattern in patterns:
            match = re.search(pattern, body, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return _decode_js_string(match.group(1))
    return ""


def _published_at(parser: WeChatPageParser, body: str, crawler: Any) -> str | None:
    candidates = (
        parser.meta.get("article:published_time"),
        parser.meta.get("date"),
        parser.meta.get("datepublished"),
        _js_value(body, ("publish_time", "publishTime")),
    )
    for candidate in candidates:
        normalized = crawler.normalize_date(candidate)
        if normalized:
            return normalized
    for name in ("oriCreateTime", "createTime", "ct"):
        match = re.search(
            rf"(?:var\s+)?{name}\s*=\s*['\"]?(\d{{10,13}})['\"]?",
            body,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        timestamp = int(match.group(1))
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        try:
            return datetime.fromtimestamp(timestamp, UTC).date().isoformat()
        except (OverflowError, OSError, ValueError):
            continue
    return None


def _contains_phrase(text: str, phrase: str, crawler: Any) -> bool:
    phrase = _clean(phrase, 120)
    if not phrase:
        return False
    return crawler._keyword_in_text(phrase, text.casefold())


def _matched(values: Sequence[str], text: str, crawler: Any) -> list[str]:
    return _unique(value for value in values if _contains_phrase(text, value, crawler), 40)


def _event_context(text: str) -> bool:
    folded = text.casefold()
    return any(term.casefold() in folded for term in EVENT_TERMS)


def _specific_keywords(values: Sequence[str]) -> list[str]:
    return [
        value
        for value in _unique(values, 80)
        if value.casefold() not in GENERIC_DISCOVERY_TERMS
        and not (re.fullmatch(r"[A-Za-z]{1,2}", value) or len(value) < 2)
    ]


def _is_relevant(
    title: str,
    summary: str,
    content: str,
    spec: dict[str, Any],
    crawler: Any,
) -> tuple[list[str], list[str], list[str]]:
    text = f"{title} {summary} {content}"
    companies = _matched(spec.get("trackedCompanies", []), text, crawler)
    people = _matched(spec.get("trackedPeople", []), text, crawler)
    keywords = _matched(_specific_keywords(spec.get("keywords", [])), text, crawler)
    if companies or people:
        return companies, people, keywords
    if len(keywords) >= 2 or (keywords and _event_context(text)):
        return companies, people, keywords
    return [], [], []


def _company_attribution(
    title: str,
    content: str,
    account: str,
    matched_companies: Sequence[str],
    crawler: Any,
) -> tuple[str, str | None]:
    title_matches = [
        company
        for company in matched_companies
        if _contains_phrase(title, company, crawler)
    ]
    if len(title_matches) == 1:
        return title_matches[0], None
    account_matches = [
        company
        for company in matched_companies
        if account and (
            _contains_phrase(account, company, crawler)
            or _contains_phrase(company, account, crawler)
        )
    ]
    if len(account_matches) == 1:
        return account_matches[0], None
    if len(matched_companies) == 1 and _event_context(f"{title} {content}"):
        return matched_companies[0], None
    inferred, slug, _region = crawler.infer_company(title, "")
    return inferred, slug


def fetch_public_wechat_page(url: str, timeout: int = 18, attempts: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": WECHAT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                "Referer": "https://mp.weixin.qq.com/",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except Exception as exc:  # noqa: BLE001 - surfaced in source status.
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.7 * (attempt + 1))
    assert last_error is not None
    raise last_error


def parse_wechat_article(
    spec: dict[str, Any],
    url: str,
    body: str,
    crawler: Any,
    *,
    fallback_title: str = "",
    fallback_summary: str = "",
    fallback_date: str | None = None,
) -> dict[str, Any] | None:
    if not body or any(marker in body for marker in BLOCK_PAGE_MARKERS):
        return None
    parser = WeChatPageParser()
    parser.feed(body)
    title = crawler.clean_title(
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.title
        or _js_value(body, ("msg_title", "title"))
        or fallback_title
    )
    account = (
        parser.account
        or _js_value(body, ("nickname", "profile_nickname", "account_name"))
        or spec.get("name", "")
    )
    author = parser.author or _js_value(body, ("author", "author_name"))
    published_at = _published_at(parser, body, crawler) or crawler.normalize_date(
        fallback_date
    )
    content = parser.content
    summary = _clean(
        parser.meta.get("description")
        or parser.meta.get("og:description")
        or parser.meta.get("twitter:description")
        or content[:650]
        or fallback_summary,
        500,
    )
    if not title or len(title) < 6 or not published_at or not summary:
        return None

    matched_companies, matched_people, matched_keywords = _is_relevant(
        title, summary, content, spec, crawler
    )
    if not (matched_companies or matched_people or matched_keywords):
        return None
    company, company_slug = _company_attribution(
        title, content, account, matched_companies, crawler
    )
    article = crawler._external_article(
        spec,
        title=title,
        summary=summary,
        url=crawler.normalize_url(url),
        published_at=published_at,
        source_name=account or spec.get("name", "微信公众号"),
        source_level="原始材料",
        platform="微信",
        company=company,
        company_slug=company_slug,
        authors=[author] if author else None,
    )
    article["sector"] = spec.get("sector") or article.get("sector")
    article["wechatAccount"] = account
    article["mentionedCompanies"] = matched_companies
    article["mentionedPeople"] = matched_people
    article["matchedTrackingTerms"] = matched_keywords[:20]
    return article


def _feed_rows(body: str, crawler: Any) -> list[dict[str, str]]:
    root = ET.fromstring(body)
    rows: list[dict[str, str]] = []
    for node in root.iter():
        if crawler._xml_local(node.tag) not in {"item", "entry"}:
            continue
        rows.append(
            {
                "title": crawler.clean_title(crawler._xml_text(node, ("title",))),
                "summary": crawler.strip_html(
                    crawler._xml_text(node, ("description", "summary", "content"))
                ),
                "url": crawler._xml_link(node),
                "date": crawler._xml_text(
                    node, ("pubdate", "published", "updated", "date")
                ),
            }
        )
    return rows


def crawl_wechat_source(
    spec: dict[str, Any], user_agent: str, crawler: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    feed_body = crawler.fetch_text(spec["url"], user_agent)
    rows = _feed_rows(feed_body, crawler)
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    failures = 0
    scanned = 0
    for row in rows:
        url = crawler.normalize_url(row.get("url", ""))
        host = (urlsplit(url).hostname or "").casefold()
        if host != WECHAT_HOST or url in seen:
            continue
        scanned += 1
        try:
            article = parse_wechat_article(
                spec,
                url,
                fetch_public_wechat_page(url),
                crawler,
                fallback_title=row.get("title", ""),
                fallback_summary=row.get("summary", ""),
                fallback_date=row.get("date"),
            )
        except Exception as exc:  # noqa: BLE001 - reported per public source.
            failures += 1
            print(
                f"WeChat article warning: {url} ({type(exc).__name__}: {exc})",
                file=getattr(crawler, "sys", __import__("sys")).stderr,
            )
            continue
        if article:
            accepted.append(article)
            seen.add(url)
        if len(accepted) >= int(spec.get("maxItems", MAX_ITEMS_PER_TRACK)):
            break
        time.sleep(0.12)

    status = (
        "ok"
        if accepted and failures == 0
        else "partial"
        if accepted
        else "error"
        if failures
        else "empty"
    )
    return accepted, crawler._status(
        spec["id"],
        spec["name"],
        status,
        scanned,
        len(accepted),
        failed=failures,
        platform="微信",
        error=(
            "Public WeChat pages could not be read; previous snapshot retained"
            if failures and not accepted
            else None
        ),
    )


def install(tracking: Any) -> None:
    """Install track-specific WeChat discovery into ``crawl_with_tracking``."""

    original_build = tracking.build_merged_config
    if not getattr(original_build, "_wechat_discovery", False):

        def build_merged_config(
            base: dict[str, Any], tracking_config: dict[str, Any]
        ) -> tuple[dict[str, Any], dict[str, tuple[str, str, str, str]], set[str]]:
            config, sec_specs, active_ids = original_build(base, tracking_config)
            tracks = tracking._enabled_tracks(tracking_config)
            generated = generated_wechat_sources(tracks, tracking)
            discovery = [
                spec
                for spec in config.get("publicDiscovery", [])
                if isinstance(spec, dict)
                and spec.get("id") != "wechat-public-index"
                and spec.get("adapter") != "wechat_search"
            ]
            discovery.extend(generated)
            config["publicDiscovery"] = discovery
            active_ids.update(spec["id"] for spec in generated)
            return config, sec_specs, active_ids

        setattr(build_merged_config, "_wechat_discovery", True)
        tracking.build_merged_config = build_merged_config

    original_install = tracking._install_runtime_overrides
    if getattr(original_install, "_wechat_adapter", False):
        return

    def install_runtime(
        merged: dict[str, Any],
        sec_specs: dict[str, tuple[str, str, str, str]],
        active_ids: set[str],
    ) -> None:
        original_install(merged, sec_specs, active_ids)
        original_crawl_source = tracking.crawler._crawl_config_source
        if getattr(original_crawl_source, "_wechat_source_dispatch", False):
            return

        def crawl_source(
            spec: dict[str, Any], user_agent: str
        ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            if spec.get("adapter") == "wechat_search":
                return crawl_wechat_source(spec, user_agent, tracking.crawler)
            return original_crawl_source(spec, user_agent)

        setattr(crawl_source, "_wechat_source_dispatch", True)
        tracking.crawler._crawl_config_source = crawl_source

    setattr(install_runtime, "_wechat_adapter", True)
    tracking._install_runtime_overrides = install_runtime
