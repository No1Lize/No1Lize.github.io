#!/usr/bin/env python3
"""Discover public WeChat Channels cards embedded in public WeChat articles.

Only public article HTML and original WeChat share links are used. The adapter does
not resolve private media URLs, signatures, captions, audio, or downloadable video.
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from tools.person_video_discovery import (
    ALL_VIDEO_MARKERS,
    _material_type,
    clean,
    normalize,
    request_text,
    unique,
)

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
MAX_ARTICLES = 8
MAX_RESULTS = 4
WECHAT_ARTICLE_HOST = "mp.weixin.qq.com"
WECHAT_CHANNEL_HOST = "channels.weixin.qq.com"
WECHAT_SHARE_HOST = "weixin.qq.com"


def load_articles() -> list[dict[str, Any]]:
    try:
        payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [row for row in payload.get("articles") or [] if isinstance(row, dict)]


def _alias_keys(candidate: dict[str, Any]) -> list[str]:
    return [
        normalize(value)
        for value in unique([
            candidate.get("name"),
            candidate.get("englishName"),
            *(candidate.get("aliases") or []),
        ])
        if len(normalize(value)) >= 3
    ]


def _article_matches_person(article: dict[str, Any], alias_keys: list[str]) -> bool:
    source = article.get("source") or {}
    haystack = normalize(" ".join([
        str(article.get("title") or ""),
        str(article.get("summary") or ""),
        " ".join(str(value) for value in article.get("authors") or []),
        str(source.get("name") or ""),
    ]))
    return bool(alias_keys and any(alias in haystack for alias in alias_keys))


def matching_public_wechat_articles(
    candidate: dict[str, Any],
    articles: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    alias_keys = _alias_keys(candidate)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for article in articles if articles is not None else load_articles():
        source = article.get("source") or {}
        url = str(source.get("url") or "").strip()
        try:
            host = (urlsplit(url).hostname or "").casefold()
        except ValueError:
            continue
        if host != WECHAT_ARTICLE_HOST or not _article_matches_person(article, alias_keys):
            continue
        if url in seen:
            continue
        result.append({
            "title": clean(article.get("title"), 260),
            "summary": clean(article.get("summary"), 900),
            "publishedAt": clean(article.get("publishedAt"), 40) or "持续更新",
            "url": url,
            "sourceName": clean(source.get("name"), 120) or "微信公众号",
        })
        seen.add(url)
    result.sort(key=lambda row: row["publishedAt"], reverse=True)
    return result[:MAX_ARTICLES]


def _decoded_html(value: str) -> str:
    return (
        html.unescape(value or "")
        .replace("\\/", "/")
        .replace("\\u0026", "&")
        .replace("\\x26", "&")
    )


def normalize_wechat_share_url(value: str) -> str:
    text = _decoded_html(str(value or "")).strip().strip("'\"")
    text = text.rstrip(".,;，。；)]}）】")
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    host = (parts.hostname or "").casefold()
    path = parts.path or ""
    if host == WECHAT_CHANNEL_HOST:
        if not any(marker in path.casefold() for marker in ("/web/pages/feed", "/mobile/video")):
            return ""
    elif host == WECHAT_SHARE_HOST:
        if not path.casefold().startswith("/sph/"):
            return ""
    else:
        return ""
    return urlunsplit((parts.scheme or "https", parts.netloc, path, parts.query, ""))


def _attributes(tag: str) -> dict[str, str]:
    return {
        name.casefold(): _decoded_html(value)
        for name, _, value in re.findall(
            r"([:\w-]+)\s*=\s*(['\"])(.*?)\2",
            tag,
            flags=re.IGNORECASE | re.DOTALL,
        )
    }


def _share_urls(value: str) -> list[str]:
    decoded = _decoded_html(value)
    candidates = re.findall(
        r"https?://(?:channels\.weixin\.qq\.com|weixin\.qq\.com)/[^\s'\"<>]+",
        decoded,
        flags=re.IGNORECASE,
    )
    return unique(normalize_wechat_share_url(candidate) for candidate in candidates)


def extract_embedded_wechat_videos(
    body: str,
    article: dict[str, Any],
) -> list[dict[str, str]]:
    decoded = _decoded_html(body)
    article_title = clean(article.get("title"), 260) or "微信视频号公开材料"
    article_summary = clean(article.get("summary"), 900)
    article_date = clean(article.get("publishedAt"), 40) or "持续更新"
    article_source = clean(article.get("sourceName"), 120) or "微信公众号"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    tags = re.findall(
        r"<mp-common-videosnap\b[^>]*>",
        decoded,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for tag in tags:
        attrs = _attributes(tag)
        urls = unique([
            normalize_wechat_share_url(attrs.get("data-url", "")),
            normalize_wechat_share_url(attrs.get("data-src", "")),
            normalize_wechat_share_url(attrs.get("data-link", "")),
            *_share_urls(tag),
        ])
        card_title = clean(
            attrs.get("data-desc")
            or attrs.get("data-title")
            or attrs.get("title")
            or article_title,
            260,
        )
        nickname = clean(attrs.get("data-nickname"), 100)
        context = clean(f"{card_title} {article_title} {article_summary}", 1600)
        if not any(marker in context.casefold() for marker in ALL_VIDEO_MARKERS):
            continue
        for url in urls:
            if not url or url in seen:
                continue
            rows.append({
                "title": card_title,
                "date": article_date,
                "type": _material_type(context),
                "url": url,
                "source": f"微信视频号 · {nickname}" if nickname else f"微信视频号（{article_source}嵌入）",
            })
            seen.add(url)

    context = clean(f"{article_title} {article_summary}", 1600)
    if any(marker in context.casefold() for marker in ALL_VIDEO_MARKERS):
        for url in _share_urls(decoded):
            if not url or url in seen:
                continue
            rows.append({
                "title": article_title,
                "date": article_date,
                "type": _material_type(context),
                "url": url,
                "source": f"微信视频号（{article_source}嵌入）",
            })
            seen.add(url)
    return rows


def _sogou_articles(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    if os.getenv("PERSON_VIDEO_SOGOU", "").strip() not in {"1", "true", "yes"}:
        return []
    try:
        from tools import wechat_sogou_index as sogou
    except ImportError:
        return []
    name = clean(candidate.get("name") or candidate.get("englishName"), 80)
    override = candidate.get("override") or {}
    spec = {
        "name": name,
        "expectedAccounts": [name],
        "sector": (candidate.get("sectors") or ["人物研究"])[0],
        "keywords": ["视频号", "演讲", "访谈", *(override.get("organizationHints") or [])],
    }
    try:
        rows, _ = sogou.discover(spec)
    except Exception:
        return []
    alias_keys = _alias_keys(candidate)
    result: list[dict[str, Any]] = []
    for row in rows:
        direct = str(row.get("directUrl") or "")
        try:
            host = (urlsplit(direct).hostname or "").casefold()
        except ValueError:
            continue
        article = {
            "title": clean(row.get("title"), 260),
            "summary": clean(row.get("summary"), 900),
            "publishedAt": clean(row.get("publishedAt"), 40) or "持续更新",
            "url": direct,
            "sourceName": clean(row.get("account"), 120) or "微信公众号",
        }
        if host == WECHAT_ARTICLE_HOST and _article_matches_person(
            {**article, "source": {"name": article["sourceName"]}}, alias_keys
        ):
            result.append(article)
    return result[:4]


def discover_person_wechat_video_materials(candidate: dict[str, Any]) -> list[dict[str, str]]:
    articles = matching_public_wechat_articles(candidate)
    known = {row["url"] for row in articles}
    for row in _sogou_articles(candidate):
        if row["url"] not in known:
            articles.append(row)
            known.add(row["url"])
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for article in articles[:MAX_ARTICLES]:
        body = request_text(
            article["url"],
            {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
        )
        if not body:
            continue
        for item in extract_embedded_wechat_videos(body, article):
            if item["url"] in seen:
                continue
            result.append(item)
            seen.add(item["url"])
            if len(result) >= MAX_RESULTS:
                return result
    return result
