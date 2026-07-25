#!/usr/bin/env python3
"""Generic taxonomy helpers for arbitrary user-created tracking sectors.

The module derives aliases from names, keeps sector identity terms separate from
actor terms, and prevents terms shared by multiple sectors from becoming
unscoped standalone discovery seeds.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable

SPLIT_PATTERN = re.compile(r"[/／|｜,，;；、&＆+＋()（）\[\]【】]+")
TRIM_PATTERN = re.compile(r"^[\s._:：\-—–]+|[\s._:：\-—–]+$")
NORMALIZE_PATTERN = re.compile(r"[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+")


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
    values_by_slug: dict[str, list[str]] = {}

    for track in tracks:
        slug = clean(track.get("slug"), 80)
        values = terms_for_track(track)
        values_by_slug[slug] = values
        counts.update({normalize_term(value) for value in values})

    return {
        slug: [value for value in values if counts[normalize_term(value)] == 1]
        for slug, values in values_by_slug.items()
    }


def unique_identity_terms_by_track(
    tracks: list[dict[str, Any]],
) -> dict[str, list[str]]:
    unique_keywords = _unique_terms_by_track(
        tracks,
        lambda track: unique(track.get("keywords", []), 60),
    )
    return {
        clean(track.get("slug"), 80): unique(
            [
                *name_aliases(track.get("name")),
                *unique_keywords.get(clean(track.get("slug"), 80), []),
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
        query = f"({tracking_module._quoted_or_query(terms)}) ({event_terms})"
        sources.append(
            {
                "id": f"user-track-{slug}",
                "name": f"{track['name']} · 用户追踪",
                "url": tracking_module._bing_rss(query),
                "adapter": "rss",
                "platform": "用户追踪",
                "sourceLevel": "待交叉验证",
                "region": "全球",
                "sector": track["name"],
                "maxItems": 8,
                "keywords": terms,
                "strictTitleKeywords": False,
                "enabled": True,
            }
        )
    return sources


def install(tracking_module: Any) -> None:
    """Patch the legacy adapter without duplicating its remaining behavior."""

    tracking_module._track_terms = lambda track: all_track_terms(track, tracking_module)
    tracking_module._generated_track_sources = lambda tracks: generated_track_sources(
        tracks, tracking_module
    )
