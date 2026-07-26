#!/usr/bin/env python3
"""Generic taxonomy helpers for arbitrary user-created tracking sectors.

The module derives aliases from names, keeps sector identity terms separate from
actor terms, prevents shared terms from becoming unscoped discovery seeds, and
builds several independent discovery sources for every enabled track.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable
from urllib.parse import quote_plus

SPLIT_PATTERN = re.compile(r"[/／|｜,，;；、&＆+＋()（）\[\]【】]+")
TRIM_PATTERN = re.compile(r"^[\s._:：\-—–]+|[\s._:：\-—–]+$")
NORMALIZE_PATTERN = re.compile(r"[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+")
TRACK_SOURCE_SUFFIXES = ("bing", "google-cn", "google-us", "toutiao")
TOUTIAO_HOST = "toutiao.com"


def clean(value: Any, limit: int = 160) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalize_term(value: Any) -> str:
    return NORMALIZE_PATTERN.sub("", clean(value).casefold())


def unique(values: Iterable[Any], limit: int = 80) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = TRIM_PATTERN.sub("", clean(raw)).strip()
        key = normalize_term(value)
        if not value or len(key) < 2 or key in seen:
            continue
        result.append(value)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def name_aliases(name: Any) -> list[str]:
    normalized = clean(name)
    pieces = [TRIM_PATTERN.sub("", item).strip() for item in SPLIT_PATTERN.split(normalized)]
    compact = re.sub(r"\s+", "", normalized)
    return unique([normalized, compact, *pieces], 12)


def identity_terms(track: dict[str, Any]) -> list[str]:
    return unique([*name_aliases(track.get("name")), *track.get("keywords", [])], 24)


def actor_terms(track: dict[str, Any], tracking_module: Any) -> list[str]:
    people = tracking_module._person_search_terms(track.get("people", []))
    return unique([*track.get("sampleCompanies", []), *people], 40)


def all_track_terms(track: dict[str, Any], tracking_module: Any) -> list[str]:
    return unique([*identity_terms(track), *actor_terms(track, tracking_module)], 80)


def _unique_terms_by_track(
    tracks: list[dict[str, Any]],
    terms_for_track: Any,
) -> dict[str, list[str]]:
    counts: Counter[str] = Counter()
    terms_by_slug: dict[str, list[str]] = {}
    for track in tracks:
        slug = clean(track.get("slug"), 80)
        terms = terms_for_track(track)
        terms_by_slug[slug] = terms
        counts.update({normalize_term(value) for value in terms})
    return {
        slug: [value for value in terms if counts[normalize_term(value)] == 1]
        for slug, terms in terms_by_slug.items()
    }


def unique_identity_terms_by_track(
    tracks: list[dict[str, Any]],
) -> dict[str, list[str]]:
    keyword_counts: Counter[str] = Counter()
    for track in tracks:
        keyword_counts.update(
            {normalize_term(value) for value in unique(track.get("keywords", []), 60)}
        )
    return {
        clean(track.get("slug"), 80): unique(
            [
                *name_aliases(track.get("name")),
                *[
                    value
                    for value in unique(track.get("keywords", []), 60)
                    if keyword_counts[normalize_term(value)] == 1
                ],
            ],
            24,
        )
        for track in tracks
    }


def unique_actor_terms_by_track(
    tracks: list[dict[str, Any]], tracking_module: Any
) -> dict[str, list[str]]:
    return _unique_terms_by_track(
        tracks,
        lambda track: actor_terms(track, tracking_module),
    )


def expected_source_ids(slug: str) -> list[str]:
    return [f"user-track-{slug}-{suffix}" for suffix in TRACK_SOURCE_SUFFIXES]


def toutiao_source_spec(
    slug: str,
    sector: str,
    query_url: str,
    terms: list[str],
    max_items: int = 8,
) -> dict[str, Any]:
    """Build the per-track 今日头条 discovery source.

    Discovery goes through a public search index restricted to
    ``site:toutiao.com``; only links on the Toutiao domain whitelist are
    accepted, and the crawler keeps title, short summary, date and the
    original link only — the same boundary as every other media source.
    """

    return {
        "id": f"user-track-{slug}-toutiao",
        "name": f"{sector} · 今日头条",
        "url": query_url,
        "adapter": "rss",
        "platform": "今日头条",
        "sourceLevel": "媒体报道",
        "region": "中国",
        "sector": sector,
        "maxItems": max_items,
        "keywords": terms,
        "strictTitleKeywords": False,
        "allowedHosts": [TOUTIAO_HOST],
        "enabled": True,
    }


def _google_news_url(query: str, *, chinese: bool) -> str:
    encoded = quote_plus(query)
    if chinese:
        return (
            "https://news.google.com/rss/search?"
            f"q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        )
    return (
        "https://news.google.com/rss/search?"
        f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )


def generated_track_sources(
    tracks: list[dict[str, Any]], tracking_module: Any
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    unique_identities = unique_identity_terms_by_track(tracks)
    unique_actors = unique_actor_terms_by_track(tracks, tracking_module)
    event_terms = (
        "融资 OR 投资 OR IPO OR 上市 OR 发布 OR 突破 OR 研究 OR 政策 "
        "OR funding OR investment OR launch OR research OR policy"
    )

    for track in tracks:
        slug = clean(track.get("slug"), 80)
        core = unique_identities.get(slug, name_aliases(track.get("name")))
        actors = unique_actors.get(slug, [])
        terms = unique([*core, *actors], 80)
        if not core:
            continue
        quoted_terms = tracking_module._quoted_or_query(terms)
        query = f"({quoted_terms}) ({event_terms})"
        common = {
            "name": track["name"],
            "adapter": "rss",
            "sourceLevel": "待交叉验证",
            "sector": track["name"],
            "keywords": terms,
            "strictTitleKeywords": False,
            "enabled": True,
        }
        sources.extend(
            [
                {
                    **common,
                    "id": f"user-track-{slug}-bing",
                    "name": f"{track['name']} · Bing 发现",
                    "url": tracking_module._bing_rss(query),
                    "platform": "Bing 搜索",
                    "region": "全球",
                    "maxItems": 8,
                },
                {
                    **common,
                    "id": f"user-track-{slug}-google-cn",
                    "name": f"{track['name']} · Google News 中文",
                    "url": _google_news_url(query, chinese=True),
                    "platform": "Google News",
                    "region": "中国",
                    "maxItems": 8,
                },
                {
                    **common,
                    "id": f"user-track-{slug}-google-us",
                    "name": f"{track['name']} · Google News 英文",
                    "url": _google_news_url(query, chinese=False),
                    "platform": "Google News",
                    "region": "美国",
                    "maxItems": 8,
                },
                toutiao_source_spec(
                    slug,
                    track["name"],
                    tracking_module._bing_rss(f"site:{TOUTIAO_HOST} {query}"),
                    terms,
                ),
            ]
        )
    return sources


def install(tracking_module: Any) -> None:
    """Patch the legacy adapter without duplicating its remaining behavior."""

    tracking_module._track_terms = lambda track: all_track_terms(track, tracking_module)
    tracking_module._generated_track_sources = lambda tracks: generated_track_sources(
        tracks, tracking_module
    )
