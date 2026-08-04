#!/usr/bin/env python3
"""Normalize and retire unsafe auto-discovered tracking sources.

The tracking discovery loop may observe articles that were themselves collected by
an auto-generated source. Without an explicit provenance boundary, that derived
source name can be promoted again (for example ``Slashdot · 风险投资信源 · 风险投资信源``).
This module provides the shared canonicalization and cleanup rules used by discovery
and source-health persistence.

Owner-entered sources are never retired by this module. Automatic media sources may
be removed when they are recursive duplicates, canonical duplicates in the same
track, or have reached quarantine without ever producing an accepted article.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "user_tracking.json"
DEFAULT_LEDGER_PATH = ROOT / "config" / "tracking_auto_discovery.json"
DEFAULT_HEALTH_PATH = ROOT / "public" / "data" / "source_health.json"

AUTO_SOURCE_PREFIX = "source-auto-"
AUTO_MEDIA_PREFIX = "source-auto-media-"
PUBLISHER_ROOT_DOMAINS = {
    # Slashdot exposes topic-specific hosts that are one publisher and one
    # discovery source for a given track. Keep this explicit rather than
    # broadly collapsing every news.* or tech.* subdomain on the web.
    "slashdot.org",
}
FEED_SUBDOMAIN_PREFIXES = {
    "www",
    "www1",
    "www2",
    "m",
    "mobile",
    "amp",
    "rss",
    "feed",
    "feeds",
    "feeds2",
}
AUTO_SOURCE_SUFFIX_RE = re.compile(
    r"\s*·\s*[^·\n]{1,80}?信源(?:\s+官方动态)?\s*$",
    re.IGNORECASE,
)


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return deepcopy(fallback)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_text(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value or "")),
    ).strip().casefold()


def canonical_source_host(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = (parsed.hostname or "").strip(".").casefold()
    for root in PUBLISHER_ROOT_DOMAINS:
        if host == root or host.endswith(f".{root}"):
            return root
    labels = [label for label in host.split(".") if label]
    while len(labels) > 2 and labels[0] in FEED_SUBDOMAIN_PREFIXES:
        labels.pop(0)
    return ".".join(labels)


def canonical_source_url(value: Any) -> str:
    host = canonical_source_host(value)
    return f"https://{host}/" if host else ""


def strip_discovery_source_suffix(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ·")
    while text:
        cleaned = AUTO_SOURCE_SUFFIX_RE.sub("", text).strip(" ·")
        if cleaned == text:
            break
        text = cleaned
    return text


def discovery_suffix_count(value: Any) -> int:
    text = re.sub(r"\s+", " ", str(value or ""))
    count = 0
    while text:
        cleaned = AUTO_SOURCE_SUFFIX_RE.sub("", text).strip(" ·")
        if cleaned == text:
            break
        count += 1
        text = cleaned
    return count


def is_auto_source(source: dict[str, Any] | None) -> bool:
    return str((source or {}).get("id") or "").startswith(AUTO_SOURCE_PREFIX)


def runtime_source_id(config_source_id: Any) -> str:
    source_id = str(config_source_id or "").strip()
    return f"user-source-{source_id}" if source_id else ""


def config_source_id(runtime_id: Any) -> str:
    source_id = str(runtime_id or "").strip()
    if source_id.startswith("user-source-"):
        return source_id[len("user-source-") :]
    return source_id


def runtime_source_ids(config_source_id_value: Any) -> set[str]:
    source_id = str(config_source_id_value or "").strip()
    return {value for value in (source_id, runtime_source_id(source_id)) if value}


def is_runtime_auto_source_id(value: Any) -> bool:
    return config_source_id(value).startswith(AUTO_SOURCE_PREFIX)


def is_auto_media_source(source: dict[str, Any] | None) -> bool:
    row = source or {}
    source_id = str(row.get("id") or "")
    return source_id.startswith(AUTO_MEDIA_PREFIX) or (
        source_id.startswith(AUTO_SOURCE_PREFIX)
        and str(row.get("sourceCategory") or "") == "media"
    )


def looks_like_derived_source_name(value: Any) -> bool:
    return discovery_suffix_count(value) > 0


def normalized_auto_media_name(source: dict[str, Any]) -> str:
    base = strip_discovery_source_suffix(source.get("name"))
    if not base:
        base = canonical_source_host(source.get("url")) or "公开媒体"
    sector = re.sub(r"\s+", " ", str(source.get("sector") or "行业")).strip()
    return f"{base} · {sector}信源"


def source_scope_key(source: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        canonical_source_host(source.get("url")),
        normalize_text(source.get("sector")),
        normalize_text(source.get("sourceCategory")),
        normalize_text(source.get("company")),
    )


def _source_score(source: dict[str, Any], index: int) -> tuple[int, int, int, int, int]:
    # Owner-entered sources always win over derived sources. For automatic
    # duplicates prefer enabled, non-recursive, root/canonical records while
    # retaining stable earlier ordering as the final tie-breaker.
    return (
        1 if not is_auto_source(source) else 0,
        1 if bool(source.get("enabled", True)) else 0,
        1 if discovery_suffix_count(source.get("name")) <= 1 else 0,
        1 if str(source.get("url") or "") == canonical_source_url(source.get("url")) else 0,
        -index,
    )


def _health_entry_is_dead_auto_source(
    source: dict[str, Any],
    health_entry: dict[str, Any] | None,
) -> bool:
    if not is_auto_media_source(source) or not isinstance(health_entry, dict):
        return False
    threshold = max(7, int(health_entry.get("quarantineThreshold") or 0))
    failures = int(health_entry.get("consecutiveFailures") or 0)
    return (
        str(health_entry.get("collectionState") or "") == "quarantined"
        and failures >= threshold
        and not health_entry.get("lastProductiveAt")
    )


def _unique_rows(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = tuple(normalize_text(row.get(field)) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _normalize_ledger(
    ledger: dict[str, Any],
    *,
    url_rewrites: dict[str, str],
    removed_sources: list[dict[str, Any]],
    retained_urls: set[str],
) -> tuple[dict[str, Any], dict[str, int]]:
    result = deepcopy(ledger)
    added = result.get("added") if isinstance(result.get("added"), list) else []
    removed = result.get("removed") if isinstance(result.get("removed"), list) else []
    removed_raw_urls = {
        str(source.get("_originalUrl") or source.get("url") or "")
        for source in removed_sources
    }
    rewritten = 0
    dropped = 0
    next_added: list[dict[str, Any]] = []
    for raw in added:
        if not isinstance(raw, dict):
            continue
        row = deepcopy(raw)
        if str(row.get("kind") or "") == "sources":
            value = str(row.get("value") or "")
            if value in url_rewrites:
                row["value"] = url_rewrites[value]
                rewritten += 1
            elif value in removed_raw_urls and value not in retained_urls:
                dropped += 1
                continue
        next_added.append(row)
    next_added = _unique_rows(next_added, ("track", "kind", "value"))

    existing_removed = {
        (normalize_text(row.get("track")), normalize_text(row.get("kind")), normalize_text(row.get("value")))
        for row in removed
        if isinstance(row, dict)
    }
    added_tombstones = 0
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    for source in removed_sources:
        raw_url = str(source.get("_originalUrl") or source.get("url") or "")
        if not raw_url or raw_url in retained_urls:
            continue
        key = (
            normalize_text(source.get("_trackSlug")),
            "sources",
            normalize_text(raw_url),
        )
        if key in existing_removed:
            continue
        removed.append(
            {
                "track": str(source.get("_trackSlug") or ""),
                "kind": "sources",
                "value": raw_url,
                "removedAt": now,
                "reason": "auto-source-governance",
            }
        )
        existing_removed.add(key)
        added_tombstones += 1

    result["added"] = next_added
    result["removed"] = _unique_rows(removed, ("track", "kind", "value"))
    if rewritten or dropped or added_tombstones:
        result["updatedAt"] = now
    return result, {
        "ledgerValuesRewritten": rewritten,
        "ledgerRowsDropped": dropped,
        "ledgerTombstonesAdded": added_tombstones,
    }


def _rebuild_health_summary(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    sources = result.get("sources") if isinstance(result.get("sources"), dict) else {}

    def ids_for(predicate: Any) -> list[str]:
        return sorted(
            source_id
            for source_id, item in sources.items()
            if isinstance(item, dict) and predicate(item)
        )

    active = ids_for(lambda item: bool(item.get("alertActive")))
    quarantined = ids_for(lambda item: item.get("collectionState") == "quarantined")
    probation = ids_for(lambda item: item.get("collectionState") == "probation")
    low_priority = ids_for(lambda item: item.get("priority") == "low")
    performance_review = ids_for(
        lambda item: isinstance(item.get("performance"), dict)
        and bool(item["performance"].get("reviewRequired"))
    )
    downgrade = ids_for(
        lambda item: isinstance(item.get("performance"), dict)
        and item["performance"].get("reviewState") == "downgrade-candidate"
    )
    retirement = ids_for(
        lambda item: isinstance(item.get("performance"), dict)
        and item["performance"].get("reviewState") == "retire-candidate"
    )
    monitor = ids_for(
        lambda item: isinstance(item.get("performance"), dict)
        and item["performance"].get("reviewState") == "monitor"
    )
    result.update(
        {
            "sourceCount": len(sources),
            "activeAlertCount": len(active),
            "activeAlerts": active,
            "quarantinedSourceCount": len(quarantined),
            "quarantinedSources": quarantined,
            "probationSourceCount": len(probation),
            "probationSources": probation,
            "lowPrioritySourceCount": len(low_priority),
            "lowPrioritySources": low_priority,
            "performanceReviewSourceCount": len(performance_review),
            "performanceReviewSources": performance_review,
            "downgradeCandidateCount": len(downgrade),
            "downgradeCandidates": downgrade,
            "retirementCandidateCount": len(retirement),
            "retirementCandidates": retirement,
            "monitorSourceCount": len(monitor),
            "monitorSources": monitor,
            "sources": dict(sorted(sources.items())),
        }
    )
    return result


def normalize_tracking_sources(
    config: dict[str, Any],
    ledger: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    next_config = deepcopy(config)
    next_ledger = deepcopy(ledger or {})
    next_health = deepcopy(health or {})
    sources = next_config.get("sources") if isinstance(next_config.get("sources"), list) else []
    health_sources = next_health.get("sources") if isinstance(next_health.get("sources"), dict) else {}

    prepared: list[dict[str, Any]] = []
    renamed = 0
    canonicalized = 0
    dead_removed = 0
    removed_sources: list[dict[str, Any]] = []
    url_rewrites: dict[str, str] = {}

    track_by_sector = {
        normalize_text(track.get("name")): str(track.get("slug") or "")
        for track in next_config.get("tracks", [])
        if isinstance(track, dict)
    }

    for index, raw in enumerate(sources):
        if not isinstance(raw, dict):
            continue
        source = deepcopy(raw)
        source["_index"] = index
        source["_originalName"] = str(source.get("name") or "")
        source["_originalUrl"] = str(source.get("url") or "")
        source["_trackSlug"] = track_by_sector.get(normalize_text(source.get("sector")), "")
        if is_auto_media_source(source):
            clean_name = normalized_auto_media_name(source)
            if clean_name != str(source.get("name") or ""):
                source["name"] = clean_name
                renamed += 1
            clean_url = canonical_source_url(source.get("url"))
            if clean_url and clean_url != str(source.get("url") or ""):
                url_rewrites[str(source.get("url") or "")] = clean_url
                source["url"] = clean_url
                canonicalized += 1
        source_health = next(
            (
                health_sources.get(source_id)
                for source_id in runtime_source_ids(source.get("id"))
                if isinstance(health_sources.get(source_id), dict)
            ),
            None,
        )
        if _health_entry_is_dead_auto_source(source, source_health):
            source["_removalReason"] = "never-productive-quarantine"
            removed_sources.append(source)
            dead_removed += 1
            continue
        prepared.append(source)

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for source in prepared:
        grouped.setdefault(source_scope_key(source), []).append(source)

    keep_ids: set[int] = set()
    duplicate_removed = 0
    recursive_removed = 0
    for rows in grouped.values():
        manual_rows = [row for row in rows if not is_auto_source(row)]
        if manual_rows:
            # Governance never removes owner-entered duplicates. It only
            # removes automatic rows colliding with an owner source.
            for manual in manual_rows:
                keep_ids.add(int(manual.get("_index") or 0))
            duplicates = [row for row in rows if is_auto_source(row)]
        else:
            ranked = sorted(
                rows,
                key=lambda row: _source_score(row, int(row.get("_index") or 0)),
                reverse=True,
            )
            winner = ranked[0]
            keep_ids.add(int(winner.get("_index") or 0))
            duplicates = ranked[1:]
        for duplicate in duplicates:
            duplicate["_removalReason"] = "canonical-duplicate"
            removed_sources.append(duplicate)
            duplicate_removed += 1
            if discovery_suffix_count(duplicate.get("_originalName")) > 1:
                recursive_removed += 1

    final_sources: list[dict[str, Any]] = []
    for source in prepared:
        if int(source.get("_index") or 0) not in keep_ids:
            continue
        final_sources.append(
            {
                key: value
                for key, value in source.items()
                if not str(key).startswith("_")
            }
        )
    next_config["sources"] = final_sources

    retained_urls = {str(source.get("url") or "") for source in final_sources}
    next_ledger, ledger_stats = _normalize_ledger(
        next_ledger,
        url_rewrites=url_rewrites,
        removed_sources=removed_sources,
        retained_urls=retained_urls,
    )

    configured_ids = {str(source.get("id") or "") for source in final_sources}
    removed_config_ids = {
        str(source.get("id") or "") for source in removed_sources if source.get("id")
    }
    removed_ids = {
        source_id
        for config_id in removed_config_ids
        for source_id in runtime_source_ids(config_id)
    }
    health_removed = 0
    if health_sources:
        for source_id in list(health_sources):
            if source_id in removed_ids or (
                is_runtime_auto_source_id(source_id)
                and config_source_id(source_id) not in configured_ids
            ):
                health_sources.pop(source_id, None)
                health_removed += 1
        next_health["sources"] = health_sources
        next_health = _rebuild_health_summary(next_health)

    errors = validate_tracking_sources(next_config, next_health)
    stats = {
        "sourceCountBefore": len(sources),
        "sourceCountAfter": len(final_sources),
        "renamed": renamed,
        "urlsCanonicalized": canonicalized,
        "duplicatesRemoved": duplicate_removed,
        "recursiveDuplicatesRemoved": recursive_removed,
        "deadAutoSourcesRemoved": dead_removed,
        "healthRowsRemoved": health_removed,
        "removedSourceIds": sorted(removed_ids),
        "errors": errors,
        **ledger_stats,
    }
    return next_config, next_ledger, next_health, stats


def validate_tracking_sources(
    config: dict[str, Any],
    health: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    configured_ids: set[str] = set()
    for source in config.get("sources", []):
        if not isinstance(source, dict):
            errors.append("source entry must be an object")
            continue
        source_id = str(source.get("id") or "")
        configured_ids.add(source_id)
        key = source_scope_key(source)
        if not key[0]:
            errors.append(f"{source_id}: missing canonical host")
        previous = seen.get(key)
        if previous and (is_auto_source(source) or is_auto_source(previous)):
            errors.append(
                f"{source_id}: duplicates canonical source {previous.get('id', '')}"
            )
        elif previous is None:
            seen[key] = source
        if is_auto_media_source(source):
            if discovery_suffix_count(source.get("name")) != 1:
                errors.append(f"{source_id}: recursive or missing discovery suffix")
            if str(source.get("url") or "") != canonical_source_url(source.get("url")):
                errors.append(f"{source_id}: auto media URL is not canonical")
    health_sources = (health or {}).get("sources")
    if isinstance(health_sources, dict):
        for source_id in health_sources:
            if (
                is_runtime_auto_source_id(source_id)
                and config_source_id(source_id) not in configured_ids
            ):
                errors.append(f"{source_id}: stale automatic source-health row")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH_PATH)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config = _read_json(args.config, {})
    ledger = _read_json(args.ledger, {})
    health = _read_json(args.health, {})
    next_config, next_ledger, next_health, stats = normalize_tracking_sources(
        config,
        ledger,
        health,
    )
    changed = (
        next_config != config
        or next_ledger != ledger
        or next_health != health
    )
    stats["changed"] = changed

    if args.check:
        if stats["errors"]:
            print(json.dumps(stats, ensure_ascii=False))
            return 1
        if changed:
            stats["errors"] = ["tracking source governance changes have not been applied"]
            print(json.dumps(stats, ensure_ascii=False))
            return 1
    elif not args.dry_run:
        if stats["errors"]:
            print(json.dumps(stats, ensure_ascii=False))
            return 1
        if next_config != config:
            _write_json(args.config, next_config)
        if next_ledger != ledger:
            _write_json(args.ledger, next_ledger)
        if next_health != health:
            _write_json(args.health, next_health)

    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
