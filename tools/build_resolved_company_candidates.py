#!/usr/bin/env python3
"""Build the company candidate pool after cross-type entity resolution."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .build_company_candidates import (
        ARTICLES_PATH,
        CAPTURE_INBOX_PATH,
        DECISIONS_PATH as COMPANY_DECISIONS_PATH,
        OUTPUT_PATH,
        build_candidate_snapshot,
        load_json,
        semantic_payload,
        write_snapshot,
    )
    from .entity_resolution import (
        COMPANY_REGISTRY_PATH,
        DECISIONS_PATH as ENTITY_DECISIONS_PATH,
        PEOPLE_PATH,
        TRACKING_PATH,
        clean,
        resolve_entity,
    )
    from .resolve_company_entities import load_registry
    from .resolved_company_captures import resolved_company_captures
except ImportError:
    from build_company_candidates import (  # type: ignore
        ARTICLES_PATH,
        CAPTURE_INBOX_PATH,
        DECISIONS_PATH as COMPANY_DECISIONS_PATH,
        OUTPUT_PATH,
        build_candidate_snapshot,
        load_json,
        semantic_payload,
        write_snapshot,
    )
    from entity_resolution import (  # type: ignore
        COMPANY_REGISTRY_PATH,
        DECISIONS_PATH as ENTITY_DECISIONS_PATH,
        PEOPLE_PATH,
        TRACKING_PATH,
        clean,
        resolve_entity,
    )
    from resolve_company_entities import load_registry  # type: ignore
    from resolved_company_captures import resolved_company_captures  # type: ignore


def build_resolved_candidate_snapshot(
    articles_payload: dict[str, Any],
    company_decisions_payload: dict[str, Any],
    captures_payload: dict[str, Any],
    entity_decisions_payload: dict[str, Any],
    company_registry_payload: dict[str, Any],
    people_payload: dict[str, Any],
    tracking_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    captures, stats = resolved_company_captures(
        captures_payload,
        entity_decisions_payload=entity_decisions_payload,
        company_registry_payload=company_registry_payload,
        people_payload=people_payload,
        tracking_payload=tracking_payload,
    )
    snapshot = build_candidate_snapshot(
        articles_payload,
        load_registry(COMPANY_REGISTRY_PATH),
        company_decisions_payload,
        captures,
    )
    snapshot["entityResolution"] = stats
    return snapshot, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--company-decisions", type=Path, default=COMPANY_DECISIONS_PATH)
    parser.add_argument("--captures", type=Path, default=CAPTURE_INBOX_PATH)
    parser.add_argument("--entity-decisions", type=Path, default=ENTITY_DECISIONS_PATH)
    parser.add_argument("--companies", type=Path, default=COMPANY_REGISTRY_PATH)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    snapshot, stats = build_resolved_candidate_snapshot(
        load_json(args.articles, {"articles": []}),
        load_json(args.company_decisions, {"decisions": {}}),
        load_json(args.captures, {"records": []}),
        load_json(args.entity_decisions, {"decisions": {}}),
        load_json(args.companies, {"companies": []}),
        load_json(args.people, {"people": []}),
        load_json(args.tracking, {"tracks": []}),
    )
    if args.check:
        current = load_json(args.output, {})
        if semantic_payload(current) != semantic_payload(snapshot):
            raise SystemExit("resolved company candidate snapshot is not current")
        print(json.dumps({"valid": True, "candidateCount": snapshot["candidateCount"], **stats}, ensure_ascii=False))
        return 0

    changed = write_snapshot(snapshot, args.output)
    print(
        json.dumps(
            {
                "changed": changed,
                "generatedAt": snapshot.get("generatedAt") or datetime.now(UTC).isoformat(),
                "candidateCount": snapshot["candidateCount"],
                "pendingCount": snapshot["pendingCount"],
                **stats,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
