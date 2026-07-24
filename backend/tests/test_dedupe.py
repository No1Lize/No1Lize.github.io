from datetime import UTC, datetime

from workers.ingestion.base import Candidate, normalize_url
from workers.ingestion.dedupe import deduplicate


def candidate(url: str) -> Candidate:
    return Candidate(
        title="Official event",
        summary="",
        canonical_url=normalize_url(url),
        source_name="Official",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        event_type="融资",
        region="美国",
        sector="AI / AGI",
        entity_name="Example",
    )


def test_url_normalization_and_deduplication() -> None:
    first = candidate("https://example.com/news/?utm_source=x")
    second = candidate("https://example.com/news")
    unique, skipped = deduplicate([first, second])
    assert len(unique) == 1
    assert skipped == 1
