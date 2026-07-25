#!/usr/bin/env python3
"""Run the official crawler with shared adaptive public-web transport.

Eastmoney still has stricter detail-page, attribution and rolling-history rules,
but HTTP headers, retries and charset decoding now come from the same adaptive
kernel used by every user-added public website. The adaptive layer performs
shared discovery and diagnostics; this plugin exclusively owns the published
Eastmoney article batch so the two stages cannot double-count the same stories.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlsplit

try:
    from . import adaptive_public_sources as adaptive
    from . import crawl_official_with_source_categories as category_crawler
    from . import crawl_official_with_tracking as tracking_crawler
except ImportError:
    import adaptive_public_sources as adaptive
    import crawl_official_with_source_categories as category_crawler
    import crawl_official_with_tracking as tracking_crawler


EASTMONEY_HOST_SUFFIX = "eastmoney.com"
EASTMONEY_HISTORY_LIMIT = 12
EASTMONEY_ORIGIN_FIELD = "_eastmoneyBatchOrigin"
EASTMONEY_ORIGIN_NEW = "new"
EASTMONEY_ORIGIN_RETAINED = "retained"
BROWSER_USER_AGENT = adaptive.BROWSER_USER_AGENT


def _normalized_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def is_eastmoney_url(url: str) -> bool:
    host = _normalized_host(url)
    return host == EASTMONEY_HOST_SUFFIX or host.endswith(f".{EASTMONEY_HOST_SUFFIX}")


def _normalize_charset(value: str | None) -> str:
    """Compatibility wrapper around the shared charset normalizer."""

    return adaptive._normalize_charset(value)


def decode_eastmoney_bytes(payload: bytes, header_charset: str | None = None) -> str:
    """Compatibility wrapper using the shared profile-aware decoder."""

    return adaptive.decode_public_bytes(
        payload,
        "https://www.eastmoney.com/",
        header_charset,
    )


def eastmoney_fetch_text(
    url: str,
    user_agent: str,
    timeout: int,
    attempts: int,
) -> str:
    """Fetch Eastmoney through the same transport used by adaptive sources."""

    return adaptive.fetch_public_text(
        url,
        user_agent,
        timeout=timeout,
        attempts=attempts,
    )


def install_transport() -> None:
    official = tracking_crawler.official
    original: Callable[..., str] = official.fetch_text
    if getattr(original, "_eastmoney_aware", False):
        return

    def fetch_text(
        url: str,
        user_agent: str,
        timeout: int = 10,
        attempts: int = 2,
    ) -> str:
        if is_eastmoney_url(url):
            return eastmoney_fetch_text(url, user_agent, timeout, attempts)
        return original(url, user_agent, timeout=timeout, attempts=attempts)

    setattr(fetch_text, "_eastmoney_aware", True)
    official.fetch_text = fetch_text


def install_handoff_cleanup() -> None:
    """Remove generic Eastmoney articles before the strict publisher merges data.

    The generic adaptive status remains in ``sourceStatus`` as proof that common
    discovery ran. Only its article batch is removed; the strict detail crawler
    publishes validated ``/a/<id>.html`` records under its own source identity.
    """

    official = tracking_crawler.official
    original_load_payload = official.load_existing_payload
    if getattr(original_load_payload, "_eastmoney_handoff_cleanup", False):
        return

    def load_existing_payload(path=official.OUTPUT_PATH) -> dict[str, Any]:
        payload = original_load_payload(path)
        payload["articles"] = [
            article
            for article in payload.get("articles", [])
            if not (
                str(article.get("sourceId", "")).startswith("user-source-")
                and is_eastmoney_url(_article_source_url(article))
            )
        ]
        return payload

    setattr(load_existing_payload, "_eastmoney_handoff_cleanup", True)
    official.load_existing_payload = load_existing_payload


def _is_eastmoney_status(status: dict[str, Any]) -> bool:
    text = " ".join(
        str(status.get(key, "")) for key in ("id", "name", "company")
    )
    return "东方财富" in text


def _article_source_url(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url", "")).strip()


def _is_eastmoney_detail_for_source(
    article: dict[str, Any], source_id: str
) -> bool:
    return (
        str(article.get("sourceId", "")) == source_id
        and tracking_crawler._is_eastmoney_article_url(_article_source_url(article))
    )


def _has_existing_eastmoney_details(
    existing: list[dict[str, Any]], source_id: str
) -> bool:
    return any(
        _is_eastmoney_detail_for_source(article, source_id)
        for article in existing
    )


def _article_identity(article: dict[str, Any]) -> str:
    return _article_source_url(article) or str(article.get("id", ""))


def _article_sort_key(article: dict[str, Any]) -> tuple[str, int, str]:
    try:
        importance = int(article.get("importance", 0) or 0)
    except (TypeError, ValueError):
        importance = 0
    return (
        str(article.get("publishedAt", "")),
        importance,
        str(article.get("id", "")),
    )


def _with_origin(article: dict[str, Any], origin: str) -> dict[str, Any]:
    marked = dict(article)
    marked[EASTMONEY_ORIGIN_FIELD] = origin
    return marked


def merge_eastmoney_history(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    limit: int = EASTMONEY_HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    """Merge successful Eastmoney batches with a bounded prior detail history."""

    source_ids = {
        str(status.get("id", ""))
        for status in statuses
        if _is_eastmoney_status(status)
        and int(status.get("accepted", 0) or 0) > 0
    }
    if not source_ids:
        return list(incoming)

    merged_incoming = [
        article
        for article in incoming
        if str(article.get("sourceId", "")) not in source_ids
    ]

    for source_id in source_ids:
        incoming_group = [
            article
            for article in incoming
            if _is_eastmoney_detail_for_source(article, source_id)
        ]
        existing_group = [
            article
            for article in existing
            if _is_eastmoney_detail_for_source(article, source_id)
        ]

        by_identity: dict[str, dict[str, Any]] = {}
        for article in existing_group:
            key = _article_identity(article)
            if key:
                by_identity[key] = _with_origin(
                    article,
                    EASTMONEY_ORIGIN_RETAINED,
                )
        for article in incoming_group:
            key = _article_identity(article)
            if key:
                by_identity[key] = _with_origin(
                    article,
                    EASTMONEY_ORIGIN_NEW,
                )

        history = sorted(
            by_identity.values(),
            key=_article_sort_key,
            reverse=True,
        )[: max(1, limit)]
        retained_count = sum(
            article.get(EASTMONEY_ORIGIN_FIELD) == EASTMONEY_ORIGIN_RETAINED
            for article in history
        )

        for status in statuses:
            if str(status.get("id", "")) != source_id:
                continue
            status["newAccepted"] = int(status.get("accepted", 0) or 0)
            status["accepted"] = len(history)
            if retained_count:
                status["retainedPrevious"] = True
                status["retainedPreviousCount"] = retained_count
            else:
                status.pop("retainedPrevious", None)
                status.pop("retainedPreviousCount", None)

        merged_incoming.extend(history)

    return merged_incoming


def replacement_statuses_for_eastmoney(
    existing: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Retain valid details when a portal run returns no new article links."""

    replacement_statuses: list[dict[str, Any]] = []
    for status in statuses:
        shadow = dict(status)
        source_id = str(status.get("id", ""))
        should_retain = (
            _is_eastmoney_status(status)
            and int(status.get("accepted", 0) or 0) == 0
            and _has_existing_eastmoney_details(existing, source_id)
        )
        if should_retain:
            status["status"] = "partial"
            status["retainedPrevious"] = True
            status["error"] = (
                "No new Eastmoney detail pages discovered; previous detail snapshot retained"
            )
            shadow["status"] = "error"
        replacement_statuses.append(shadow)
    return replacement_statuses


def install_snapshot_retention() -> None:
    official = tracking_crawler.official
    original_replace = official.replace_official_source_batches
    if getattr(original_replace, "_retains_eastmoney_snapshot", False):
        return

    def replace_official_source_batches(
        existing: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
        statuses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged_incoming = merge_eastmoney_history(existing, incoming, statuses)
        replacement_statuses = replacement_statuses_for_eastmoney(existing, statuses)
        return original_replace(existing, merged_incoming, replacement_statuses)

    setattr(
        replace_official_source_batches,
        "_retains_eastmoney_snapshot",
        True,
    )
    official.replace_official_source_batches = replace_official_source_batches


def install_quality_preservation() -> None:
    official = tracking_crawler.official
    original_evaluate_quality = official.evaluate_quality
    if getattr(original_evaluate_quality, "_preserves_tracking_quality", False):
        return

    original_load_payload = official.load_existing_payload
    tracking_report: dict[str, Any] = {}

    def load_existing_payload(path=official.OUTPUT_PATH) -> dict[str, Any]:
        payload = original_load_payload(path)
        tracking_report.clear()
        quality_gate = payload.get("qualityGate", {})
        report = (
            quality_gate.get("trackingQuality")
            if isinstance(quality_gate, dict)
            else None
        )
        if isinstance(report, dict):
            tracking_report.update(report)
        return payload

    def evaluate_quality(
        articles: list[dict[str, Any]],
        source_status: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        quality = original_evaluate_quality(articles, source_status, settings)
        if tracking_report:
            quality["trackingQuality"] = dict(tracking_report)
        return quality

    setattr(evaluate_quality, "_preserves_tracking_quality", True)
    official.load_existing_payload = load_existing_payload
    official.evaluate_quality = evaluate_quality


def main() -> int:
    install_transport()
    install_handoff_cleanup()
    install_snapshot_retention()
    install_quality_preservation()
    return category_crawler.main()


if __name__ == "__main__":
    raise SystemExit(main())
