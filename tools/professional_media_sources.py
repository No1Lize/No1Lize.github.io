"""Load and route the owner-curated professional technology media catalog.

Every enabled outlet becomes an independent, bounded discovery source. This
prevents large publications from consuming a shared result page and makes the
formal snapshot expose one execution status per registered media outlet. Every
returned URL is checked against the original media host and, when a source uses
a section path, against that path as well.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "professional_technology_media_sources.json"
VALID_REGIONS = {"中国", "美国", "全球"}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _unique(values: Iterable[Any], limit: int = 160) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 160)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _host(value: str) -> str:
    return (urlsplit(str(value or "")).hostname or "").casefold().removeprefix("www.")


def _path(value: str) -> str:
    return urlsplit(str(value or "")).path.rstrip("/")


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    result = []
    previous_dash = False
    for character in text:
        if character.isascii() and character.isalnum():
            result.append(character)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True
    return "".join(result).strip("-")[:60] or "media"


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported professional media registry schema")
    settings = payload.get("settings")
    sources = payload.get("sources")
    if not isinstance(settings, dict) or not isinstance(sources, list):
        raise ValueError("professional media registry requires settings and sources")

    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for raw in sources:
        if not isinstance(raw, dict):
            raise ValueError("professional media source rows must be objects")
        source_id = _clean(raw.get("id"), 80)
        name = _clean(raw.get("name"), 120)
        url = _clean(raw.get("url"), 500)
        host = _clean(raw.get("host"), 200).casefold().removeprefix("www.")
        scope = _clean(raw.get("searchScope"), 300).casefold().removeprefix("www.")
        sector = _clean(raw.get("primarySector"), 60)
        order = int(raw.get("order", 0) or 0)
        if not source_id or not name or not url or not host or not scope or not sector:
            raise ValueError(f"incomplete professional media source: {source_id or name}")
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"invalid professional media URL: {source_id}")
        if _host(url) != host:
            raise ValueError(f"professional media host mismatch: {source_id}")
        if source_id in seen_ids or order in seen_orders:
            raise ValueError(f"duplicate professional media identity: {source_id}")
        seen_ids.add(source_id)
        seen_orders.add(order)
        region = _clean(raw.get("region"), 20)
        normalized.append(
            {
                **raw,
                "id": source_id,
                "name": name,
                "url": url,
                "host": host,
                "searchScope": scope,
                "primarySector": sector,
                "region": region if region in VALID_REGIONS else "全球",
                "priority": max(1, min(int(raw.get("priority", 3) or 3), 3)),
                "focus": _unique(raw.get("focus", []), 20),
                "enabled": raw.get("enabled", True) is not False,
            }
        )
    return {**payload, "sources": normalized}


def enabled_sources(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    return [source for source in load_registry(path)["sources"] if source["enabled"]]


def grouped_specs(
    tracks: Sequence[dict[str, Any]],
    tracking: Any,
    path: Path = REGISTRY_PATH,
) -> list[dict[str, Any]]:
    """Build one independently executable, allowlisted source per media outlet."""

    payload = load_registry(path)
    settings = payload["settings"]
    max_items = max(
        2,
        min(
            int(
                settings.get(
                    "maxItemsPerSource",
                    min(int(settings.get("maxItemsPerGroup", 4) or 4), 4),
                )
                or 4
            ),
            6,
        ),
    )
    event_terms = _unique(settings.get("eventTerms", []), 18)
    track_by_name = {
        _clean(track.get("name"), 60).casefold(): track
        for track in tracks
        if isinstance(track, dict)
    }

    specs: list[dict[str, Any]] = []
    sources = sorted(
        (source for source in payload["sources"] if source["enabled"]),
        key=lambda source: (source["priority"], int(source.get("order", 0))),
    )
    for source in sources:
        sector = source["primarySector"]
        track = track_by_name.get(sector.casefold())
        track_terms = tracking._track_terms(track) if track else [sector]
        relevance_terms = tracking._unique(
            [sector, *track_terms, *source.get("focus", [])],
            20,
        )
        discovery_terms = tracking._unique(
            [*relevance_terms, *event_terms],
            28,
        )
        query = (
            f"site:{source['searchScope']} "
            f"({tracking._quoted_or_query(discovery_terms, 28)})"
        )
        source_id = f"professional-media-{_slug(source['id'])}"
        media_row = {
            "id": source["id"],
            "name": source["name"],
            "url": source["url"],
            "host": source["host"],
            "pathPrefix": _path(source["url"]),
            "region": source["region"],
            "focus": source.get("focus", []),
            "priority": source["priority"],
        }
        specs.append(
            {
                "id": source_id,
                "name": source["name"],
                "url": tracking._bing_rss(query),
                "sourceUrl": source["url"],
                "adapter": "rss",
                "platform": source["name"],
                "sourceCategory": "media",
                "sourceLevel": "媒体报道",
                "region": source["region"],
                "sector": sector,
                "maxItems": max_items,
                "keywords": relevance_terms,
                "strictTitleKeywords": False,
                "allowedHosts": [source["host"]],
                "professionalMedia": [media_row],
                "enabled": True,
            }
        )
    return specs


def match_media(url: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    candidate_host = _host(url)
    candidate_path = _path(url)
    matches: list[dict[str, Any]] = []
    for row in rows:
        host = _clean(row.get("host"), 200).casefold().removeprefix("www.")
        if not host or not (
            candidate_host == host or candidate_host.endswith(f".{host}")
        ):
            continue
        prefix = _clean(row.get("pathPrefix"), 300).rstrip("/")
        if prefix and prefix != "/" and not (
            candidate_path == prefix or candidate_path.startswith(f"{prefix}/")
        ):
            continue
        matches.append(row)
    if not matches:
        return None
    return max(matches, key=lambda row: len(_clean(row.get("pathPrefix"), 300)))


def attribute_article(
    article: dict[str, Any],
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    source = article.get("source")
    if not isinstance(source, dict):
        return None
    matched = match_media(str(source.get("url", "")), rows)
    if not matched:
        return None
    result = copy.deepcopy(article)
    next_source = dict(source)
    next_source["name"] = matched["name"]
    next_source["platform"] = matched["name"]
    result["source"] = next_source
    result["professionalMediaId"] = matched["id"]
    result["professionalMediaUrl"] = matched["url"]
    result["professionalMediaFocus"] = list(matched.get("focus", []))[:12]
    if result.get("region") == "全球" and matched.get("region") in VALID_REGIONS:
        result["region"] = matched["region"]
    return result


def install(crawler: Any) -> None:
    """Enforce original-domain attribution on professional media feeds."""

    original_parse = crawler.parse_feed_items
    if getattr(original_parse, "_professional_media_attribution", False):
        return

    def parse_feed_items(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
        articles = original_parse(body, spec)
        rows = spec.get("professionalMedia")
        if not isinstance(rows, list):
            return articles
        return [
            attributed
            for article in articles
            if (attributed := attribute_article(article, rows)) is not None
        ]

    setattr(parse_feed_items, "_professional_media_attribution", True)
    crawler.parse_feed_items = parse_feed_items
