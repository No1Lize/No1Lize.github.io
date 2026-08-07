#!/usr/bin/env python3
"""Run automatic company onboarding with evidence-linked official-site discovery.

The core onboarding preparer keeps source authority narrow. This wrapper expands the
source-discovery layer without changing that contract: it pre-verifies candidate
homepages from traceable source-article links or exact brand-domain probes, then
passes only verified identities into the existing preparer. Wikidata remains the
fallback resolver.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import company_official_source_discovery as discovery
    from . import onboard_company_candidates as onboarding
    from . import prepare_company_candidate_onboarding as preparation
except ImportError:  # pragma: no cover - direct execution
    import company_official_source_discovery as discovery  # type: ignore
    import onboard_company_candidates as onboarding  # type: ignore
    import prepare_company_candidate_onboarding as preparation  # type: ignore


def discover_candidate_identities(
    candidates_payload: dict[str, Any],
    decisions_payload: dict[str, Any],
    official_sources_payload: dict[str, Any],
    *,
    limit: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    candidates = onboarding.candidate_index(candidates_payload)
    decisions = onboarding.normalize_decisions(decisions_payload)
    verified: dict[str, dict[str, Any]] = {}
    holds: list[dict[str, str]] = []
    checked = 0

    for key, decision in decisions["decisions"].items():
        if checked >= max(1, limit):
            break
        if decision.get("status") != "accepted":
            continue
        state = decision.get("onboarding") if isinstance(decision.get("onboarding"), dict) else {}
        if state.get("status") in {"requested", "published", "failed", "merged"}:
            continue
        candidate = candidates.get(key)
        if not candidate:
            continue
        if preparation.candidate_is_institution_like(candidate):
            continue
        if preparation._official_source_match(official_sources_payload, candidate) is not None:
            continue
        checked += 1
        metadata, reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=preparation.fetch_official_page,
            identity_checker=preparation.page_supports_identity,
            sector_checker=preparation.page_supports_sector,
        )
        name_key = preparation.identity_key(candidate.get("name"))
        if metadata is not None and name_key:
            verified[name_key] = metadata
        else:
            holds.append(
                {
                    "candidateKey": key,
                    "reason": reason or "no verified evidence-linked official site",
                }
            )

    return verified, {
        "checkedCount": checked,
        "verifiedCount": len(verified),
        "verifiedKeys": sorted(verified),
        "holdCount": len(holds),
        "holds": sorted(holds, key=lambda row: row["candidateKey"]),
    }


def run(
    *,
    candidates_payload: dict[str, Any],
    decisions_payload: dict[str, Any],
    official_sources_payload: dict[str, Any],
    registry_payload: dict[str, Any],
    captures_payload: dict[str, Any],
    limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    discovered, discovery_report = discover_candidate_identities(
        candidates_payload,
        decisions_payload,
        official_sources_payload,
        limit=limit,
    )

    def resolver(name: str):
        key = preparation.identity_key(name)
        if key in discovered:
            return discovered[key], ""
        return preparation.resolve_wikidata_company(name)

    next_decisions, onboarding_report = preparation.prepare_automatic_onboarding(
        candidates_payload,
        decisions_payload,
        official_sources_payload,
        registry_payload,
        captures_payload,
        resolver=resolver,
        limit=limit,
    )
    return next_decisions, {
        **onboarding_report,
        "sourceDiscovery": discovery_report,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=preparation.CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=preparation.DECISIONS_PATH)
    parser.add_argument("--official-sources", type=Path, default=preparation.OFFICIAL_SOURCES_PATH)
    parser.add_argument("--registry", type=Path, default=preparation.REGISTRY_PATH)
    parser.add_argument("--captures", type=Path, default=preparation.CAPTURES_PATH)
    parser.add_argument("--limit", type=int, default=preparation.MAX_AUTO_REQUESTS)
    args = parser.parse_args()

    current = onboarding.load_json(args.decisions, {"schemaVersion": 1, "decisions": {}})
    next_decisions, report = run(
        candidates_payload=onboarding.load_json(args.candidates, {"candidates": []}),
        decisions_payload=current,
        official_sources_payload=onboarding.load_json(args.official_sources, {"companies": []}),
        registry_payload=onboarding.load_json(args.registry, {"companies": []}),
        captures_payload=onboarding.load_json(args.captures, {"records": []}),
        limit=max(1, args.limit),
    )
    changed = onboarding.normalize_decisions(current) != next_decisions
    if changed:
        write_json(args.decisions, next_decisions)
    print(json.dumps({"changed": changed, **report}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
