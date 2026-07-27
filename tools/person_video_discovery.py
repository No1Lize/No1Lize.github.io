#!/usr/bin/env python3
"""Discover public person speeches, interviews and conversations on video platforms.

The adapter stores only public metadata and original links. It does not download video,
audio, captions or full transcripts. YouTube and Bilibili are searched directly through
their public web endpoints. WeChat Channels has no stable public search API, so discovery
uses public search-index RSS and accepts only original WeChat Channels share URLs.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Callable, Iterable

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 "
    "No1Lize-PeopleVideo/1.0"
)
REQUEST_TIMEOUT = 14
MAX_RESULTS_PER_PLATFORM = 4
MAX_TOTAL_RESULTS = 10

SPEECH_MARKERS = {
    "演讲", "主题演讲", "主旨演讲", "公开课", "讲座", "论坛", "分享", "报告",
    "keynote", "speech", "talk", "lecture", "presentation", "fireside chat",
}
INTERVIEW_MARKERS = {
    "采访", "访谈", "专访", "播客", "对谈", "conversation", "interview", "podcast",
}
QA_MARKERS = {"对话", "圆桌", "问答", "qa", "q&a", "panel", "roundtable", "dialogue"}
ALL_VIDEO_MARKERS = SPEECH_MARKERS | INTERVIEW_MARKERS | QA_MARKERS
WECHAT_VIDEO_HOSTS = {"channels.weixin.qq.com", "weixin.qq.com"}


def clean(value: Any, limit: int = 600) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean(value, 1200).casefold())


def unique(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean(value, 240)
        key = normalize(text)
        if not text or not key or key in seen:
            continue
        result.append(text)
        seen.add(key)
    return result


def request_text(url: str, headers: dict[str, str] | None = None) -> str | None:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        **(headers or {}),
    }
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
        return None


def request_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    text = request_text(url, headers)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _simple_text(value: Any) -> str:
    if isinstance(value, str):
        return clean(value)
    if not isinstance(value, dict):
        return ""
    if value.get("simpleText"):
        return clean(value.get("simpleText"))
    return clean("".join(str(item.get("text") or "") for item in value.get("runs") or []))


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _extract_balanced_json(text: str, marker: str) -> dict[str, Any] | None:
    start = text.find(marker)
    if start < 0:
        return None
    start = text.find("{", start + len(marker))
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(text[start:index + 1])
                except json.JSONDecodeError:
                    return None
                return payload if isinstance(payload, dict) else None
    return None


def _material_type(text: str) -> str:
    folded = clean(text, 1000).casefold()
    if any(marker in folded for marker in INTERVIEW_MARKERS):
        return "interview"
    if any(marker in folded for marker in QA_MARKERS):
        return "qa"
    return "speech"


def _matches_identity(title: str, description: str, aliases: list[str], identity_terms: list[str]) -> bool:
    haystack = normalize(f"{title} {description}")
    alias_hits = [normalize(alias) for alias in aliases if len(normalize(alias)) >= 3]
    if not alias_hits or not any(alias in haystack for alias in alias_hits):
        return False
    folded = clean(f"{title} {description}", 1800).casefold()
    if not any(marker in folded for marker in ALL_VIDEO_MARKERS):
        return False
    expected = [normalize(term) for term in identity_terms if len(normalize(term)) >= 3]
    # Exact person-name evidence is required. Context terms are a ranking signal rather
    # than a hard gate because many legitimate video titles omit the employer.
    return True if not expected else any(term in haystack for term in expected) or any(alias in normalize(title) for alias in alias_hits)


def _score_item(title: str, description: str, aliases: list[str], identity_terms: list[str]) -> int:
    title_norm = normalize(title)
    body_norm = normalize(f"{title} {description}")
    folded = clean(f"{title} {description}", 1800).casefold()
    score = 0
    for alias in aliases:
        alias_norm = normalize(alias)
        if not alias_norm:
            continue
        if alias_norm in title_norm:
            score = max(score, 12)
        elif alias_norm in body_norm:
            score = max(score, 7)
    score += min(4, sum(1 for term in identity_terms if normalize(term) and normalize(term) in body_norm) * 2)
    score += 3 if any(marker in folded for marker in ALL_VIDEO_MARKERS) else 0
    return score


def _date_from_epoch(value: Any) -> str:
    try:
        timestamp = int(value)
        return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return "持续更新"


def _date_from_rfc822(value: Any) -> str:
    try:
        parsed = email.utils.parsedate_to_datetime(str(value or ""))
        return parsed.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return "持续更新"


def discover_youtube(query: str) -> list[dict[str, str]]:
    search_terms = f"{query} interview talk keynote conversation"
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(search_terms)}"
    text = request_text(url, {"Accept": "text/html"})
    if not text:
        return []
    payload = (
        _extract_balanced_json(text, "var ytInitialData =")
        or _extract_balanced_json(text, "ytInitialData =")
        or _extract_balanced_json(text, '"ytInitialData":')
    )
    if not payload:
        return []
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in _walk(payload):
        renderer = node.get("videoRenderer")
        if not isinstance(renderer, dict):
            continue
        video_id = clean(renderer.get("videoId"), 32)
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id) or video_id in seen:
            continue
        seen.add(video_id)
        title = _simple_text(renderer.get("title"))
        author = _simple_text(renderer.get("ownerText") or renderer.get("longBylineText"))
        description = _simple_text(renderer.get("descriptionSnippet"))
        published = _simple_text(renderer.get("publishedTimeText")) or "持续更新"
        results.append({
            "title": title,
            "description": description,
            "date": published,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "source": f"YouTube · {author}" if author else "YouTube",
        })
    return results


def discover_bilibili(query: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({
        "search_type": "video",
        "keyword": f"{query} 演讲 采访 对话",
        "page": 1,
        "page_size": 12,
    })
    payload = request_json(
        f"https://api.bilibili.com/x/web-interface/search/type?{params}",
        {"Referer": f"https://search.bilibili.com/all?keyword={urllib.parse.quote_plus(query)}"},
    ) or {}
    rows = ((payload.get("data") or {}).get("result") or []) if payload.get("code") in (0, None) else []
    if not rows:
        page = request_text(
            f"https://search.bilibili.com/all?keyword={urllib.parse.quote_plus(query)}",
            {"Accept": "text/html"},
        ) or ""
        initial = _extract_balanced_json(page, "window.__INITIAL_STATE__=") or _extract_balanced_json(page, "__INITIAL_STATE__ =")
        rows = [node for node in _walk(initial or {}) if node.get("bvid") and node.get("title")]
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        bvid = clean(row.get("bvid"), 24)
        arcurl = clean(row.get("arcurl"), 500)
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
        elif "bilibili.com/video/" in arcurl:
            url = arcurl.replace("http://", "https://")
        else:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({
            "title": clean(row.get("title"), 260),
            "description": clean(row.get("description"), 800),
            "date": _date_from_epoch(row.get("pubdate")),
            "url": url,
            "source": f"Bilibili · {clean(row.get('author'), 100)}" if clean(row.get("author"), 100) else "Bilibili",
        })
    return results


def discover_wechat_channels(query: str) -> list[dict[str, str]]:
    search_query = f'(site:channels.weixin.qq.com OR site:weixin.qq.com) ({query}) (演讲 OR 采访 OR 对话 OR 论坛)'
    url = f"https://www.bing.com/search?format=rss&q={urllib.parse.quote_plus(search_query)}"
    text = request_text(url, {"Accept": "application/rss+xml, application/xml, text/xml"})
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    results: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        link = clean(item.findtext("link"), 1000)
        try:
            parsed = urllib.parse.urlsplit(link)
        except ValueError:
            continue
        host = (parsed.hostname or "").casefold()
        if host not in WECHAT_VIDEO_HOSTS:
            continue
        path_query = f"{parsed.path} {parsed.query}".casefold()
        if host == "weixin.qq.com" and not any(marker in path_query for marker in ("finder", "sph", "channel")):
            continue
        results.append({
            "title": clean(item.findtext("title"), 260),
            "description": clean(item.findtext("description"), 800),
            "date": _date_from_rfc822(item.findtext("pubDate")),
            "url": urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, parsed.path, parsed.query, "")),
            "source": "微信视频号",
        })
    return results


def build_video_query(candidate: dict[str, Any]) -> str:
    override = candidate.get("override") or {}
    explicit = unique(override.get("videoQueries") or [])
    if explicit:
        return explicit[0]
    aliases = unique([candidate.get("name"), candidate.get("englishName"), *(candidate.get("aliases") or [])])
    name = next((alias for alias in aliases if alias), "")
    organizations = unique(override.get("organizationHints") or [])
    context = organizations[0] if organizations else ""
    return clean(f"{name} {context}", 180)


def discover_person_video_materials(
    candidate: dict[str, Any],
    *,
    discoverers: dict[str, Callable[[str], list[dict[str, str]]]] | None = None,
) -> list[dict[str, str]]:
    aliases = unique([candidate.get("name"), candidate.get("englishName"), *(candidate.get("aliases") or [])])
    override = candidate.get("override") or {}
    identity_terms = unique([
        *(override.get("organizationHints") or []),
        str(override.get("roleHint") or ""),
        *(override.get("productHints") or []),
        *(candidate.get("sectors") or []),
    ])
    query = build_video_query(candidate)
    if not query or not aliases:
        return []
    discoverers = discoverers or {
        "YouTube": discover_youtube,
        "Bilibili": discover_bilibili,
        "微信视频号": discover_wechat_channels,
    }
    ranked: list[tuple[int, dict[str, str]]] = []
    for platform, discover in discoverers.items():
        accepted = 0
        try:
            rows = discover(query)
        except Exception:  # platform failure must not clear the person snapshot
            rows = []
        for row in rows:
            title = clean(row.get("title"), 260)
            description = clean(row.get("description"), 800)
            url = clean(row.get("url"), 1000)
            if not title or not url or not _matches_identity(title, description, aliases, identity_terms):
                continue
            ranked.append((_score_item(title, description, aliases, identity_terms), {
                "title": title,
                "date": clean(row.get("date"), 40) or "持续更新",
                "type": _material_type(f"{title} {description}"),
                "url": url,
                "source": clean(row.get("source"), 140) or platform,
            }))
            accepted += 1
            if accepted >= MAX_RESULTS_PER_PLATFORM:
                break
    ranked.sort(key=lambda item: (item[0], item[1]["date"]), reverse=True)
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, item in ranked:
        key = item["url"].casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= MAX_TOTAL_RESULTS:
            break
    return result
