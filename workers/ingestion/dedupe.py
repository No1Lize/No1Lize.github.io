from collections.abc import Iterable

from .base import Candidate


def deduplicate(candidates: Iterable[Candidate]) -> tuple[list[Candidate], int]:
    by_url: dict[str, Candidate] = {}
    fingerprints: set[str] = set()
    skipped = 0
    for candidate in candidates:
        if candidate.canonical_url in by_url or candidate.content_fingerprint in fingerprints:
            skipped += 1
            continue
        by_url[candidate.canonical_url] = candidate
        fingerprints.add(candidate.content_fingerprint)
    return list(by_url.values()), skipped
