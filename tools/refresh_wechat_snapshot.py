#!/usr/bin/env python3
"""Refresh only verified WeChat sources while preserving all other snapshot data."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

try:  # Imported by tests as tools.refresh_wechat_snapshot.
    from . import crawl_articles as crawler
    from . import crawl_with_tracking as tracking
    from . import wechat_index_context_guard
    from . import wechat_index_record_fallback
    from . import wechat_public_sources
    from . import wechat_registry_bridge
    from . import wechat_sogou_bridge
except ImportError:  # Executed directly with python tools/...
    import crawl_articles as crawler
    import crawl_with_tracking as tracking
    import wechat_index_context_guard
    import wechat_index_record_fallback
    import wechat_public_sources
    import wechat_registry_bridge
    import wechat_sogou_bridge

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"


def install_wechat_pipeline() -> None:
    wechat_registry_bridge.install(wechat_public_sources)
    wechat_index_context_guard.install(wechat_registry_bridge)
    wechat_index_record_fallback.install(
        wechat_public_sources,
        wechat_registry_bridge,
    )
    wechat_sogou_bridge.install(wechat_public_sources)


def configured_sources(account_ids: set[str] | None = None) -> list[dict[str, Any]]:
    install_wechat_pipeline()
    payload = tracking.load_tracking()
    tracks = tracking._enabled_tracks(payload)
    sources = wechat_public_sources.generated_wechat_sources(tracks, tracking)
    if account_ids:
        sources = [
            source
            for source in sources
            if str(source.get("accountConfigId") or source.get("id")) in account_ids
        ]
    return sources


def crawl_sources(
    sources: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incoming: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or crawler.DEFAULT_USER_AGENT
    for source in sources:
        try:
            articles, status = wechat_public_sources.crawl_wechat_source(
                source,
                user_agent,
                crawler,
            )
        except Exception as exc:  # noqa: BLE001 - retain the previous source batch.
            articles = []
            status = crawler._status(
                source["id"],
                source["name"],
                "error",
                0,
                0,
                failed=1,
                platform="微信",
                error=f"{type(exc).__name__}: {exc}",
            )
            status["retainedPrevious"] = True
        incoming.extend(articles)
        statuses.append(status)
        print(
            "wechat={id} sector={sector} status={status} scanned={scanned} "
            "accepted={accepted}".format(
                id=source.get("id"),
                sector=source.get("sector"),
                status=status.get("status"),
                scanned=status.get("scanned", 0),
                accepted=status.get("accepted", 0),
            )
        )
    return incoming, statuses


def merge_wechat_snapshot(
    payload: dict[str, Any],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    existing_articles = [
        article for article in payload.get("articles", []) if isinstance(article, dict)
    ]
    merged_articles = crawler.replace_source_batches(
        existing_articles,
        incoming,
        statuses,
    )
    invalid = [
        {"id": article.get("id", "unknown"), "errors": crawler.validate_article(article)}
        for article in merged_articles
        if crawler.validate_article(article)
    ]
    if invalid:
        raise ValueError(f"invalid WeChat snapshot articles: {invalid[:5]}")

    merged_status = crawler.merge_source_status(
        [item for item in payload.get("sourceStatus", []) if isinstance(item, dict)],
        statuses,
    )
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    next_payload = dict(payload)
    next_payload.update(
        {
            "schemaVersion": 3,
            "generatedAt": generated_at,
            "articleCount": len(merged_articles),
            "articles": merged_articles,
            "sourceStatus": merged_status,
            "wechatIngestion": {
                "generatedAt": generated_at,
                "configuredSources": len(statuses),
                "successfulSources": sum(
                    1
                    for status in statuses
                    if status.get("status") in {"ok", "partial"}
                    and int(status.get("accepted", 0) or 0) > 0
                ),
                "acceptedArticles": len(incoming),
                "fullTextArticles": sum(
                    1
                    for article in incoming
                    if article.get("wechatContentMode") != "index-only"
                ),
                "indexOnlyArticles": sum(
                    1
                    for article in incoming
                    if article.get("wechatContentMode") == "index-only"
                ),
                "retainedSources": sum(
                    1
                    for status in statuses
                    if status.get("retainedPrevious")
                    or int(status.get("accepted", 0) or 0) == 0
                ),
                "mentionedCompanyLinks": sum(
                    len(article.get("mentionedCompanies", [])) for article in incoming
                ),
                "mentionedPeopleLinks": sum(
                    len(article.get("mentionedPeople", [])) for article in incoming
                ),
            },
        }
    )
    return next_payload


def write_snapshot(next_payload: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = {}
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
    comparable_previous = dict(previous)
    comparable_next = dict(next_payload)
    comparable_previous.pop("generatedAt", None)
    comparable_next.pop("generatedAt", None)
    previous_ingestion = comparable_previous.get("wechatIngestion")
    next_ingestion = comparable_next.get("wechatIngestion")
    if isinstance(previous_ingestion, dict):
        previous_ingestion = dict(previous_ingestion)
        previous_ingestion.pop("generatedAt", None)
        comparable_previous["wechatIngestion"] = previous_ingestion
    if isinstance(next_ingestion, dict):
        next_ingestion = dict(next_ingestion)
        next_ingestion.pop("generatedAt", None)
        comparable_next["wechatIngestion"] = next_ingestion
    if comparable_previous == comparable_next:
        print("No WeChat snapshot changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            next_payload.get("wechatIngestion", {}),
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        help="Refresh only one configured account id; repeat to select several.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    account_ids = {value.strip() for value in args.account if value.strip()} or None
    sources = configured_sources(account_ids)
    if not sources:
        raise SystemExit("No configured WeChat sources matched the request")
    incoming, statuses = crawl_sources(sources)
    payload = crawler.load_existing_payload()
    next_payload = merge_wechat_snapshot(payload, incoming, statuses)
    if args.dry_run:
        print(json.dumps(next_payload.get("wechatIngestion", {}), ensure_ascii=False))
        return 0
    write_snapshot(next_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
