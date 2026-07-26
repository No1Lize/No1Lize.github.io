"""Load and route the owner-curated professional technology media catalog.

The catalog may contain many media outlets, so the crawler does not issue one
request per website. Sources are grouped by primary sector into bounded Bing
RSS discovery queries. Every returned URL is checked against the original media
host and, when a source uses a section path, against that path as well.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
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


def _chunks(values: Sequence[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(values), size):
        yield list(values[index : index + size])


def grouped_specs(
    tracks: Sequence[dict[str, Any]],
    tracking: Any,
    path: Path = REGISTRY_PATH,
) -> list[dict[str, Any]]:
    """Build a small number of allowlisted discovery sources for the full catalog."""

    payload = load_registry(path)
    settings = payload["settings"]
    max_hosts = max(2, min(int(settings.get("maxHostsPerGroup", 8) or 8), 12))
    max_items = max(4, min(int(settings.get("maxItemsPerGroup", 12) or 12), 20))
    event_terms = _unique(settings.get("eventTerms", []), 18)
    event_query = " OR ".join(event_terms)
    track_by_name = {
        _clean(track.get("name"), 60).casefold(): track
        for track in tracks
        if isinstance(track, dict)
    }

    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in payload["sources"]:
        if source["enabled"]:
            by_sector[source["primarySector"]].append(source)

    specs: list[dict[str, Any]] = []
    for sector in sorted(by_sector):
        sources = sorted(
            by_sector[sector],
            key=lambda source: (source["priority"], int(source.get("order", 0))),
        )
        track = track_by_name.get(sector.casefold())
        track_terms = tracking._track_terms(track) if track else [sector]
        for group_index, group in enumerate(_chunks(sources, max_hosts), start=1):
            focus_terms = [term for source in group for term in source.get("focus", [])]
            query_terms = tracking._unique([sector, *track_terms, *focus_terms], 18)
            site_query = " OR ".join(
                f"site:{source['searchScope']}" for source in group
            )
            term_query = tracking._quoted_or_query(query_terms, 18)
            query = f"({site_query}) ({term_query}) ({event_query})"
            source_id = f"professional-media-{_slug(sector)}-{group_index:02d}"
            specs.append(
                {
                    "id": source_id,
                    "name": f"专业科技媒体 · {sector} · {group_index:02d}",
                    "url": tracking._bing_rss(query),
                    "sourceUrl": group[0]["url"],
                    "adapter": "rss",
                    "platform": "专业科技媒体",
                    "sourceCategory": "media",
                    "sourceLevel": "媒体报道",
                    "region": "全球",
                    "sector": sector,
                    "maxItems": max_items,
                    "keywords": query_terms,
                    "strictTitleKeywords": False,
                    "allowedHosts": _unique(
                        (source["host"] for source in group), max_hosts
                    ),
                    "professionalMedia": [
                        {
                            "id": source["id"],
                            "name": source["name"],
                            "url": source["url"],
                            "host": source["host"],
                            "pathPrefix": _path(source["url"]),
                            "region": source["region"],
                            "focus": source.get("focus", []),
                            "priority": source["priority"],
                        }
                        for source in group
                    ],
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
    media = match_media(str(source.get("url", "")), rows)
    if not media:
        return None
    result = copy.deepcopy(article)
    next_source = dict(source)
    next_source["name"] = media["name"]
    next_source["platform"] = media["name"]
    result["source"] = next_source
    result["professionalMediaId"] = media["id"]
    result["professionalMediaUrl"] = media["url"]
    result["professionalMediaFocus"] = list(media.get("focus", []))[:12]
    if result.get("region") == "全球" and media.get("region") in VALID_REGIONS:
        result["region"] = media["region"]
    return result


def install(crawler: Any) -> None:
    """Enforce original-domain attribution on grouped professional media feeds."""

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
