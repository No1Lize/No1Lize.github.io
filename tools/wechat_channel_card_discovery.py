#!/usr/bin/env python3
"""Discover original WeChat Channels links embedded in public WeChat articles.

The adapter uses two compliant article-discovery inputs: the site's existing public
WeChat article snapshot and Sogou's server-rendered public WeChat index. It fetches
only public ``mp.weixin.qq.com`` pages, inspects ``mp-common-videosnap`` cards, and
retains only original ``channels.weixin.qq.com`` or ``weixin.qq.com/sph`` links.
No article body, video, audio, subtitle or transcript is persisted.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any, Callable, Iterable, Sequence

try:
    from tools import person_video_discovery as video_core
except ImportError:  # Direct execution from tools/.
    import person_video_discovery as video_core  # type: ignore

WECHAT_ARTICLE_HOST = "mp.weixin.qq.com"
MAX_ARTICLE_PAGES = 8
MAX_RESULTS = 4
BLOCK_PAGE_MARKERS = (
    "环境异常",
    "访问过于频繁",
    "请在微信客户端打开链接",
    "该内容已被发布者删除",
    "此内容因违规无法查看",
    "当前环境存在异常",
)


def _normalize_original_video_url(value: Any) -> str:
    text = str(value or "").strip().strip("'\"")
    if not text:
        return ""
    for _ in range(3):
        decoded = html.unescape(urllib.parse.unquote(text))
        decoded = (
            decoded.replace("\\/", "/")
            .replace("\\u0026", "&")
            .replace("\\x26", "&")
            .replace("\\u003d", "=")
        )
        if decoded == text:
            break
        text = decoded
    match = re.search(r"https?://[^\s'\"<>]+", text, flags=re.IGNORECASE)
    if match:
        text = match.group(0)
    text = text.rstrip("),.;，。；")
    try:
        parsed = urllib.parse.urlsplit(text)
    except ValueError:
        return ""
    host = (parsed.hostname or "").casefold()
    path = parsed.path or ""
    if host == "channels.weixin.qq.com":
        pass
    elif host == "weixin.qq.com" and path.casefold().startswith("/sph"):
        pass
    else:
        return ""
    return urllib.parse.urlunsplit(("https", parsed.netloc, path, parsed.query, ""))


def _tag_attributes(tag: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in re.finditer(
        r"([:\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
        tag,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        value = (
            match.group(2)
            if match.group(2) is not None
            else match.group(3)
            if match.group(3) is not None
            else match.group(4)
        )
        attributes[match.group(1).casefold()] = html.unescape(value)
    return attributes


def _candidate_urls(snippet: str, attributes: dict[str, str]) -> Iterable[str]:
    yield from attributes.values()
    for match in re.finditer(
        r"(?:href|data-(?:url|link|share-url|page-url|origin-url))\s*=\s*['\"]([^'\"]+)['\"]",
        snippet,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        yield match.group(1)
    for match in re.finditer(
        r"https?(?::|%3A)(?:\\?/|%2F){2}(?:channels\.weixin\.qq\.com|weixin\.qq\.com)(?:[^\s'\"<>]|&amp;)+",
        snippet,
        flags=re.IGNORECASE,
    ):
        yield match.group(0)


def extract_videosnap_cards(
    body: str,
    *,
    article_title: str = "",
    article_summary: str = "",
    article_date: str = "持续更新",
    article_source: str = "微信公众号",
) -> list[dict[str, str]]:
    """Parse ``mp-common-videosnap`` cards without synthesizing share links."""
    if (
        not body
        or "mp-common-videosnap" not in body.casefold()
        or any(marker in body for marker in BLOCK_PAGE_MARKERS)
    ):
        return []
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    starts = list(
        re.finditer(
            r"<mp-common-videosnap\b[^>]*>",
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    for start in starts:
        tag = start.group(0)
        end = body.find("</mp-common-videosnap>", start.end())
        snippet = (
            body[start.start() : end + len("</mp-common-videosnap>")]
            if end >= 0
            else body[start.start() : start.end() + 5000]
        )
        attrs = _tag_attributes(tag)
        title = video_core.clean(
            attrs.get("data-title")
            or attrs.get("data-desc")
            or attrs.get("title")
            or article_title,
            260,
        )
        description = video_core.clean(
            " ".join(
                value
                for value in (
                    article_title,
                    article_summary,
                    attrs.get("data-desc", ""),
                    attrs.get("data-nickname", ""),
                )
                if value
            ),
            800,
        )
        nickname = video_core.clean(attrs.get("data-nickname"), 100)
        for raw_url in _candidate_urls(snippet, attrs):
            url = _normalize_original_video_url(raw_url)
            key = url.casefold()
            if not url or key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "title": title or video_core.clean(article_title, 260) or "微信视频号公开内容",
                    "description": description,
                    "cardText": video_core.clean(
                        " ".join(
                            value
                            for value in (
                                attrs.get("data-title", ""),
                                attrs.get("data-desc", ""),
                                attrs.get("title", ""),
                            )
                            if value
                        ),
                        600,
                    ),
                    "date": video_core.clean(article_date, 40) or "持续更新",
                    "url": url,
                    "source": (
                        f"微信视频号 · {nickname}"
                        if nickname
                        else f"微信视频号 · {video_core.clean(article_source, 100)}"
                    ),
                }
            )
    return results


def _is_public_article_url(value: Any) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(value or ""))
    except ValueError:
        return False
    return (
        (parsed.hostname or "").casefold() == WECHAT_ARTICLE_HOST
        and parsed.path.startswith("/s")
    )


def _aliases(candidate: dict[str, Any]) -> list[str]:
    return video_core.unique(
        [
            candidate.get("name"),
            candidate.get("englishName"),
            *(candidate.get("aliases") or []),
        ]
    )


def _article_matches(article: dict[str, Any], aliases: Sequence[str]) -> bool:
    source = article.get("source") or {}
    text = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("summary") or ""),
            " ".join(str(value) for value in article.get("mentionedPeople") or []),
            " ".join(str(value) for value in article.get("authors") or []),
            str(source.get("name") or ""),
        ]
    )
    haystack = video_core.normalize(text)
    return any(
        len(video_core.normalize(alias)) >= 3
        and video_core.normalize(alias) in haystack
        for alias in aliases
    )


def _stored_articles(
    candidate: dict[str, Any], articles: Sequence[dict[str, Any]]
) -> list[dict[str, str]]:
    aliases = _aliases(candidate)
    rows: list[dict[str, str]] = []
    for article in articles:
        source = article.get("source") or {}
        url = str(source.get("url") or "")
        if not _is_public_article_url(url) or not _article_matches(article, aliases):
            continue
        rows.append(
            {
                "url": url,
                "title": str(article.get("title") or ""),
                "summary": str(article.get("summary") or ""),
                "publishedAt": str(article.get("publishedAt") or "持续更新"),
                "account": str(
                    article.get("wechatAccount")
                    or source.get("name")
                    or "微信公众号"
                ),
            }
        )
    rows.sort(key=lambda row: row["publishedAt"], reverse=True)
    return rows[:MAX_ARTICLE_PAGES]


def _sogou_articles(candidate: dict[str, Any]) -> list[dict[str, str]]:
    try:
        from tools import wechat_sogou_index
    except ImportError:
        try:
            import wechat_sogou_index  # type: ignore
        except ImportError:
            return []
    aliases = _aliases(candidate)
    identity = aliases[0] if aliases else ""
    override = candidate.get("override") or {}
    spec = {
        "name": f"人物视频号 · {identity}",
        "queryIdentity": identity,
        "sector": (candidate.get("sectors") or [""])[0],
        "keywords": ["演讲", "采访", "对话", "论坛"],
        "expectedAccounts": override.get("wechatAccounts") or [],
    }
    try:
        rows, _status = wechat_sogou_index.discover(spec)
    except Exception:
        return []
    results: list[dict[str, str]] = []
    for row in rows:
        direct = str(row.get("directUrl") or "")
        synthetic = {
            "title": row.get("title"),
            "summary": row.get("summary"),
            "mentionedPeople": [],
            "authors": [],
            "source": {"url": direct, "name": row.get("account")},
        }
        if (
            not direct
            or not _is_public_article_url(direct)
            or not _article_matches(synthetic, aliases)
        ):
            continue
        results.append(
            {
                "url": direct,
                "title": str(row.get("title") or ""),
                "summary": str(row.get("summary") or ""),
                "publishedAt": str(row.get("publishedAt") or "持续更新"),
                "account": str(row.get("account") or "微信公众号"),
            }
        )
    return results[:MAX_ARTICLE_PAGES]


def _material_type(text: str) -> str:
    folded = video_core.clean(text, 1000).casefold()
    if any(marker in folded for marker in video_core.INTERVIEW_MARKERS):
        return "interview"
    if any(marker in folded for marker in video_core.QA_MARKERS):
        return "qa"
    return "speech"


def discover_embedded_wechat_video_materials(
    candidate: dict[str, Any],
    articles: Sequence[dict[str, Any]] | None = None,
    *,
    article_discoverer: Callable[[dict[str, Any]], list[dict[str, str]]] | None = None,
    fetcher: Callable[[str, dict[str, str] | None], str | None] | None = None,
) -> list[dict[str, str]]:
    """Discover and identity-filter video cards from public WeChat articles."""
    article_discoverer = article_discoverer or _sogou_articles
    fetcher = fetcher or video_core.request_text
    aliases = _aliases(candidate)
    override = candidate.get("override") or {}
    identity_terms = video_core.unique(
        [
            *(override.get("organizationHints") or []),
            str(override.get("roleHint") or ""),
            *(override.get("productHints") or []),
            *(candidate.get("sectors") or []),
        ]
    )
    try:
        indexed = article_discoverer(candidate)
    except Exception:
        indexed = []
    combined = [*_stored_articles(candidate, articles or []), *indexed]
    ranked: list[tuple[int, dict[str, str]]] = []
    seen_articles: set[str] = set()
    seen_videos: set[str] = set()
    for row in combined:
        article_url = str(row.get("url") or "")
        article_key = article_url.casefold()
        if not article_url or article_key in seen_articles:
            continue
        seen_articles.add(article_key)
        if len(seen_articles) > MAX_ARTICLE_PAGES:
            break
        try:
            body = fetcher(
                article_url,
                {
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://mp.weixin.qq.com/",
                },
            )
        except Exception:
            body = None
        for row_item in extract_videosnap_cards(
            body or "",
            article_title=str(row.get("title") or ""),
            article_summary=str(row.get("summary") or ""),
            article_date=str(row.get("publishedAt") or "持续更新"),
            article_source=str(row.get("account") or "微信公众号"),
        ):
            title = video_core.clean(row_item.get("title"), 260)
            description = video_core.clean(row_item.get("description"), 800)
            url = video_core.clean(row_item.get("url"), 1000)
            key = url.casefold()
            card_text = video_core.normalize(row_item.get("cardText"))
            alias_keys = [
                video_core.normalize(alias)
                for alias in aliases
                if len(video_core.normalize(alias)) >= 3
            ]
            if (
                not title
                or not url
                or key in seen_videos
                or (card_text and not any(alias in card_text for alias in alias_keys))
                or not video_core._matches_identity(  # Reuse the main pipeline's identity gate.
                    title, description, aliases, identity_terms
                )
            ):
                continue
            seen_videos.add(key)
            material = {
                "title": title,
                "date": video_core.clean(row_item.get("date"), 40) or "持续更新",
                "type": _material_type(f"{title} {description}"),
                "url": url,
                "source": video_core.clean(row_item.get("source"), 140) or "微信视频号",
            }
            ranked.append(
                (
                    video_core._score_item(title, description, aliases, identity_terms),
                    material,
                )
            )
    ranked.sort(key=lambda item: (item[0], item[1]["date"]), reverse=True)
    return [item for _score, item in ranked[:MAX_RESULTS]]
