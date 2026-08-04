#!/usr/bin/env python3
"""Build and maintain the event-driven company profile refresh queue.

Only high-signal events already resolved to a catalog company are eligible. The
queue is bounded, persistent and idempotent: processed article/company pairs are
remembered so the same event cannot repeatedly trigger a profile crawl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    from .venture_profile_extraction import parse_catalog
except ImportError:
    from venture_profile_extraction import parse_catalog

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
PROFILES_PATH = ROOT / "public" / "data" / "venture_profiles.json"
QUEUE_PATH = ROOT / "public" / "data" / "company_profile_refresh_queue.json"
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"

EVENT_WEIGHTS = {
    "并购": 100,
    "IPO": 100,
    "融资": 95,
    "产业投资": 92,
    "监管文件": 90,
    "技术突破": 86,
    "财报": 82,
    "产品发布": 78,
    "商业进展": 66,
    "公司动态": 45,
}
OFFICIAL_LEVELS = {"官方披露", "原始材料", "监管文件"}
GENERIC_COMPANIES = {"", "科技产业", "产业", "行业", "公司", "科技公司", "未识别"}
PROCESSED_RETENTION_DAYS = 90
MAX_PROCESSED_EVENTS = 2000


def clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def load_json(path: Path, fallback: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    return value


def parse_datetime(value: Any) -> datetime | None:
    text = clean(value, 50)
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def article_company_slugs(article: dict[str, Any], known_slugs: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(article.get("companySlugs"), list):
        values.extend(clean(item, 100) for item in article["companySlugs"])
    values.append(clean(article.get("companySlug"), 100))
    result: list[str] = []
    seen: set[str] = set()
    for slug in values:
        if not slug or slug not in known_slugs or slug in seen:
            continue
        result.append(slug)
        seen.add(slug)
    return result


def event_fingerprint(article: dict[str, Any], slug: str) -> str:
    article_id = clean(article.get("id"), 240)
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    identity = article_id or "|".join(
        [
            clean(source.get("url"), 1200),
            clean(article.get("title"), 500),
            clean(article.get("publishedAt"), 50),
        ]
    )
    digest = hashlib.sha1(f"{slug}|{identity}".encode("utf-8")).hexdigest()
    return f"{slug}:{digest}"


def source_identity(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return (
        clean(article.get("sourceId"), 200)
        or clean(source.get("url"), 1200)
        or clean(source.get("name"), 200)
        or "unknown"
    ).casefold()


def event_priority(article: dict[str, Any], now: datetime) -> int:
    event_type = clean(article.get("type"), 80)
    importance = max(0, min(100, int(article.get("importance", 0) or 0)))
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    level = clean(source.get("level"), 80)
    published = parse_datetime(article.get("publishedAt"))
    recency_bonus = 0
    if published is not None:
        age_days = max(0, (now.date() - published.date()).days)
        recency_bonus = max(0, 10 - age_days * 2)
    return min(
        140,
        EVENT_WEIGHTS.get(event_type, 0)
        + min(20, importance // 5)
        + (10 if level in OFFICIAL_LEVELS else 0)
        + recency_bonus,
    )


def eligible_event(article: dict[str, Any]) -> bool:
    event_type = clean(article.get("type"), 80)
    importance = int(article.get("importance", 0) or 0)
    if event_type not in EVENT_WEIGHTS:
        return False
    if event_type == "公司动态" and importance < 85:
        return False
    if event_type == "商业进展" and importance < 65:
        return False
    return True


def normalize_processed(previous_queue: dict[str, Any], now: datetime) -> dict[str, dict[str, str]]:
    rows = previous_queue.get("processedEvents", {})
    if not isinstance(rows, dict):
        return {}
    cutoff = now - timedelta(days=PROCESSED_RETENTION_DAYS)
    kept: list[tuple[str, dict[str, str], datetime]] = []
    for fingerprint, raw in rows.items():
        if not isinstance(raw, dict):
            continue
        processed_at = parse_datetime(raw.get("processedAt"))
        if processed_at is None or processed_at < cutoff:
            continue
        row = {
            "companySlug": clean(raw.get("companySlug"), 100),
            "articleId": clean(raw.get("articleId"), 240),
            "processedAt": processed_at.isoformat(timespec="seconds"),
        }
        kept.append((str(fingerprint), row, processed_at))
    kept.sort(key=lambda item: item[2], reverse=True)
    return {fingerprint: row for fingerprint, row, _ in kept[:MAX_PROCESSED_EVENTS]}


def build_queue(
    articles_payload: dict[str, Any],
    profile_snapshot: dict[str, Any],
    company_names: dict[str, str],
    previous_queue: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    lookback_days: int = 7,
    select_limit: int = 10,
    processed_events: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    current = now or parse_datetime(articles_payload.get("generatedAt")) or datetime.now(UTC)
    current = current.astimezone(UTC)
    previous = previous_queue if isinstance(previous_queue, dict) else {}
    processed = processed_events or normalize_processed(previous, current)
    known_slugs = set(company_names)
    profiles = profile_snapshot.get("companies", {})
    profiles = profiles if isinstance(profiles, dict) else {}
    cutoff = current.date() - timedelta(days=max(1, lookback_days) - 1)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in articles_payload.get("articles", []):
        if not isinstance(raw, dict) or not eligible_event(raw):
            continue
        published = parse_datetime(raw.get("publishedAt"))
        if published is None or published.date() < cutoff or published.date() > current.date():
            continue
        for slug in article_company_slugs(raw, known_slugs):
            fingerprint = event_fingerprint(raw, slug)
            if fingerprint in processed:
                continue
            profile = profiles.get(slug) if isinstance(profiles.get(slug), dict) else {}
            updated = parse_datetime(profile.get("updatedAt"))
            # A later calendar-day crawl already covers the event. Same-day
            # events remain eligible because many sources provide date-only data.
            if updated is not None and published.date() < updated.date():
                continue
            source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
            grouped[slug].append(
                {
                    "fingerprint": fingerprint,
                    "articleId": clean(raw.get("id"), 240),
                    "title": clean(raw.get("title"), 300),
                    "eventType": clean(raw.get("type"), 80),
                    "publishedAt": clean(raw.get("publishedAt"), 50),
                    "importance": max(0, min(100, int(raw.get("importance", 0) or 0))),
                    "priority": event_priority(raw, current),
                    "sourceKey": source_identity(raw),
                    "sourceName": clean(source.get("platform") or source.get("name"), 160),
                    "sourceUrl": clean(source.get("url"), 1200),
                    "sourceLevel": clean(source.get("level"), 80),
                }
            )

    entries: list[dict[str, Any]] = []
    for slug, events in grouped.items():
        events.sort(
            key=lambda item: (
                -int(item["priority"]),
                str(item["publishedAt"]),
                str(item["title"]),
            )
        )
        sources = {str(item["sourceKey"]) for item in events}
        type_counts = Counter(str(item["eventType"]) for item in events)
        priority = min(
            180,
            max(int(item["priority"]) for item in events)
            + min(15, max(0, len(sources) - 1) * 3)
            + min(10, max(0, len(events) - 1) * 2),
        )
        newest = max(str(item["publishedAt"]) for item in events)
        reasons = [f"{event_type} {count} 条" for event_type, count in type_counts.most_common(3)]
        if len(sources) >= 2:
            reasons.append(f"{len(sources)} 个独立来源")
        if any(item["sourceLevel"] in OFFICIAL_LEVELS for item in events):
            reasons.append("含官方或监管证据")
        entries.append(
            {
                "companySlug": slug,
                "companyName": company_names[slug],
                "priority": priority,
                "status": "pending",
                "eventCount": len(events),
                "sourceCount": len(sources),
                "eventTypes": dict(type_counts),
                "newestPublishedAt": newest,
                "reasons": reasons,
                "eventFingerprints": [str(item["fingerprint"]) for item in events],
                "evidence": [
                    {key: value for key, value in item.items() if key not in {"sourceKey"}}
                    for item in events[:5]
                ],
            }
        )

    entries.sort(
        key=lambda item: (
            -int(item["priority"]),
            str(item["newestPublishedAt"]),
            str(item["companySlug"]),
        )
    )
    limit = max(0, min(10, int(select_limit)))
    selected_slugs = [str(item["companySlug"]) for item in entries[:limit]]
    selected_set = set(selected_slugs)
    for entry in entries:
        if entry["companySlug"] in selected_set:
            entry["status"] = "selected"

    last_processed_at = max(
        (clean(row.get("processedAt"), 50) for row in processed.values()),
        default="",
    )
    return {
        "schemaVersion": 1,
        "generatedAt": current.isoformat(timespec="seconds"),
        "lookbackDays": max(1, lookback_days),
        "selectionLimit": limit,
        "pendingCount": len(entries),
        "selectedCount": len(selected_slugs),
        "selectedSlugs": selected_slugs,
        "lastProcessedAt": last_processed_at,
        "entries": entries[:100],
        "processedEvents": processed,
    }


def mark_processed_events(
    queue: dict[str, Any],
    company_slugs: Iterable[str],
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, str]]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    selected = {clean(slug, 100) for slug in company_slugs if clean(slug, 100)}
    processed = normalize_processed(queue, current)
    for entry in queue.get("entries", []):
        if not isinstance(entry, dict) or clean(entry.get("companySlug"), 100) not in selected:
            continue
        slug = clean(entry.get("companySlug"), 100)
        article_ids = {
            clean(item.get("fingerprint"), 200): clean(item.get("articleId"), 240)
            for item in entry.get("evidence", [])
            if isinstance(item, dict)
        }
        for fingerprint in entry.get("eventFingerprints", []):
            key = clean(fingerprint, 200)
            if not key:
                continue
            processed[key] = {
                "companySlug": slug,
                "articleId": article_ids.get(key, ""),
                "processedAt": current.isoformat(timespec="seconds"),
            }
    return processed


def validate_queue(payload: dict[str, Any], known_slugs: set[str]) -> list[str]:
    errors: list[str] = []
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return ["entries must be a list"]
    seen_fingerprints: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry {index} must be an object")
            continue
        slug = clean(entry.get("companySlug"), 100)
        if slug not in known_slugs:
            errors.append(f"entry {index} has unknown company slug {slug!r}")
        if int(entry.get("priority", 0) or 0) <= 0:
            errors.append(f"entry {index} has invalid priority")
        for fingerprint in entry.get("eventFingerprints", []):
            key = clean(fingerprint, 200)
            if not key or key in seen_fingerprints:
                errors.append(f"entry {index} has duplicate or empty fingerprint")
            seen_fingerprints.add(key)
    selected = payload.get("selectedSlugs", [])
    if not isinstance(selected, list) or len(selected) > 10:
        errors.append("selectedSlugs exceeds the hard limit")
    return errors


def semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "generatedAt"}


def write_queue(path: Path, payload: dict[str, Any], *, force: bool = False) -> bool:
    previous = load_json(path, {})
    if not force and semantic_payload(previous) == semantic_payload(payload) and path.exists():
        print("No semantic company profile queue changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--profiles", type=Path, default=PROFILES_PATH)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--select-limit", type=int, default=10)
    parser.add_argument("--mark-processed", nargs="*", default=[])
    parser.add_argument("--force-write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    company_specs, _ = parse_catalog(args.catalog.read_text(encoding="utf-8"))
    company_names = {item.slug: item.name for item in company_specs}
    previous_queue = load_json(args.queue, {})
    if args.check:
        errors = validate_queue(previous_queue, set(company_names))
        print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
        return 0 if not errors else 1

    processed = normalize_processed(previous_queue, datetime.now(UTC))
    if args.mark_processed:
        processed = mark_processed_events(previous_queue, args.mark_processed)
    payload = build_queue(
        load_json(args.articles, {"articles": []}),
        load_json(args.profiles, {"companies": {}}),
        company_names,
        previous_queue,
        lookback_days=max(1, args.lookback_days),
        select_limit=args.select_limit,
        processed_events=processed,
    )
    errors = validate_queue(payload, set(company_names))
    if errors:
        print(json.dumps({"passed": False, "errors": errors}, ensure_ascii=False))
        return 1
    write_queue(args.queue, payload, force=args.force_write)
    print(
        json.dumps(
            {
                "pendingCount": payload["pendingCount"],
                "selectedCount": payload["selectedCount"],
                "selectedSlugs": payload["selectedSlugs"],
                "lastProcessedAt": payload["lastProcessedAt"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
