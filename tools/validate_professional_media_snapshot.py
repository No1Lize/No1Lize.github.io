#!/usr/bin/env python3
"""Validate that the professional-media catalog actually ran and published originals."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from . import crawl_with_tracking as tracking
    from . import professional_media_sources as media
except ImportError:
    import crawl_with_tracking as tracking
    import professional_media_sources as media

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"


def _host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def validate_payload(
    payload: dict[str, Any],
    *,
    require_articles: bool = False,
) -> dict[str, Any]:
    tracks = tracking._enabled_tracks(tracking.load_tracking())
    specs = media.grouped_specs(tracks, tracking)
    expected_ids = {str(spec["id"]) for spec in specs}
    enabled = media.enabled_sources()
    registry_by_id = {str(row["id"]): row for row in enabled}

    statuses = {
        str(row.get("id")): row
        for row in payload.get("sourceStatus", [])
        if isinstance(row, dict) and str(row.get("id")) in expected_ids
    }
    missing_statuses = sorted(expected_ids - set(statuses))
    if missing_statuses:
        raise ValueError(
            "professional media groups were not executed: "
            + ", ".join(missing_statuses[:12])
        )

    unattempted_statuses = sorted(
        source_id
        for source_id, row in statuses.items()
        if row.get("attempted") is not True
    )
    if unattempted_statuses:
        raise ValueError(
            "professional media statuses are placeholders rather than current attempts: "
            + ", ".join(unattempted_statuses[:12])
        )

    articles = [
        row
        for row in payload.get("articles", [])
        if isinstance(row, dict) and str(row.get("sourceId")) in expected_ids
    ]
    invalid: list[str] = []
    represented_media: set[str] = set()
    for article in articles:
        article_id = str(article.get("id", "unknown"))
        media_id = str(article.get("professionalMediaId", ""))
        source = article.get("source")
        source = source if isinstance(source, dict) else {}
        registry = registry_by_id.get(media_id)
        if not registry:
            invalid.append(f"{article_id}: missing professionalMediaId")
            continue
        candidate_host = _host(str(source.get("url", "")))
        registered_host = str(registry.get("host", "")).casefold().removeprefix("www.")
        if not candidate_host or not (
            candidate_host == registered_host
            or candidate_host.endswith(f".{registered_host}")
        ):
            invalid.append(f"{article_id}: source URL is outside {registered_host}")
            continue
        if str(source.get("name", "")) != str(registry.get("name", "")):
            invalid.append(f"{article_id}: source name was not attributed to the registry")
            continue
        represented_media.add(media_id)

    if invalid:
        raise ValueError("invalid professional media articles: " + "; ".join(invalid[:10]))

    accepted_by_status = sum(int(row.get("accepted", 0) or 0) for row in statuses.values())
    successful_groups = sum(
        1
        for row in statuses.values()
        if row.get("status") in {"ok", "partial"}
        and int(row.get("accepted", 0) or 0) > 0
    )
    attempted_groups = sum(row.get("attempted") is True for row in statuses.values())
    if require_articles and (accepted_by_status <= 0 or not articles):
        raise ValueError(
            "all 100 professional media sources were attempted without publishing any "
            "verifiable original-domain article"
        )

    report = {
        "enabledMediaSources": len(enabled),
        "expectedExecutionGroups": len(expected_ids),
        "executedGroups": len(statuses),
        "attemptedGroups": attempted_groups,
        "missingExecutionGroups": missing_statuses,
        "unattemptedGroups": unattempted_statuses,
        "successfulGroups": successful_groups,
        "acceptedByStatuses": accepted_by_status,
        "snapshotArticles": len(articles),
        "representedMediaSources": len(represented_media),
        "articlesBySector": dict(Counter(str(row.get("sector", "")) for row in articles)),
        "articlesByMedia": dict(
            Counter(str(row.get("professionalMediaId", "")) for row in articles)
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-articles", action="store_true")
    args = parser.parse_args()
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    report = validate_payload(payload, require_articles=args.require_articles)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
