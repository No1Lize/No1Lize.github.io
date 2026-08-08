#!/usr/bin/env python3
"""Run automatic company onboarding with evidence-linked official-site discovery.

Resolution order stays authority-first:

1. existing formal official-source registry (handled by the core preparer);
2. exact Wikidata identity with one official website;
3. evidence-linked outbound site or exact brand-domain probe, with deterministic
   homepage identity + sector checks;
4. hold for exception handling.

Only already-verified metadata is passed into the existing onboarding preparer.
Both successful and failed pre-resolution outcomes are cached for the bounded
batch so the core preparer never repeats the same external identity lookup.
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
    registry_payload: dict[str, Any],
    *,
    limit: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    candidates = onboarding.candidate_index(candidates_payload)
    decisions = onboarding.normalize_decisions(decisions_payload)
    verified: dict[str, dict[str, Any]] = {}
    verified_sources: dict[str, str] = {}
    attempted_reasons: dict[str, str] = {}
    holds: list[dict[str, str]] = []
    checked = 0

    for key, decision in decisions["decisions"].items():
        if checked >= max(1, limit):
            break
        if decision.get("status") != "accepted":
            continue
        state = (
            decision.get("onboarding")
            if isinstance(decision.get("onboarding"), dict)
            else {}
        )
        if state.get("status") in {"requested", "published", "failed", "merged"}:
            continue
        candidate = candidates.get(key)
        if not candidate:
            continue
        if preparation.candidate_is_institution_like(candidate):
            continue
        if preparation._registry_match(registry_payload, candidate):
            continue
        if preparation._official_source_match(official_sources_payload, candidate) is not None:
            continue

        checked += 1
        name = preparation.clean(candidate.get("name"), 240)
        name_key = preparation.identity_key(name)
        if not name_key:
            continue

        metadata, wikidata_reason = preparation.resolve_wikidata_company(name)
        if metadata is not None:
            verified[name_key] = metadata
            verified_sources[name_key] = "wikidata"
            continue

        metadata, discovery_reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=preparation.fetch_official_page,
            identity_checker=preparation.page_supports_identity,
            sector_checker=preparation.page_supports_sector,
        )
        if metadata is not None:
            verified[name_key] = metadata
            verified_sources[name_key] = str(metadata.get("source") or "evidence-linked")
            continue

        reason = (
            f"{wikidata_reason or 'Wikidata unresolved'}; "
            f"{discovery_reason or 'no verified evidence-linked official site'}"
        )
        attempted_reasons[name_key] = reason
        holds.append({"candidateKey": key, "reason": reason})

    return verified, {
        "checkedCount": checked,
        "verifiedCount": len(verified),
        "verifiedKeys": sorted(verified),
        "verifiedSources": {
            key: verified_sources[key] for key in sorted(verified_sources)
        },
        "attemptedFailureCount": len(attempted_reasons),
        "attemptedReasons": {
            key: attempted_reasons[key] for key in sorted(attempted_reasons)
        },
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
        registry_payload,
        limit=limit,
    )
    attempted_reasons = discovery_report.get("attemptedReasons", {})
    attempted_reasons = attempted_reasons if isinstance(attempted_reasons, dict) else {}

    def resolver(name: str):
        key = preparation.identity_key(name)
        if key in discovered:
            return discovered[key], ""
        if key in attempted_reasons:
            # The bounded pre-resolution pass already exhausted exact Wikidata and
            # deterministic evidence-linked discovery for this identity. Reusing
            # the cached negative result avoids duplicate network traffic and makes
            # one run internally deterministic even if upstream sources change.
            return None, str(attempted_reasons[key])
        # Candidates beyond the bounded pre-discovery window retain the core
        # exact-Wikidata fallback instead of being silently disabled.
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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=preparation.CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=preparation.DECISIONS_PATH)
    parser.add_argument(
        "--official-sources", type=Path, default=preparation.OFFICIAL_SOURCES_PATH
    )
    parser.add_argument("--registry", type=Path, default=preparation.REGISTRY_PATH)
    parser.add_argument("--captures", type=Path, default=preparation.CAPTURES_PATH)
    parser.add_argument("--limit", type=int, default=preparation.MAX_AUTO_REQUESTS)
    args = parser.parse_args()

    current = onboarding.load_json(
        args.decisions, {"schemaVersion": 1, "decisions": {}}
    )
    next_decisions, report = run(
        candidates_payload=onboarding.load_json(args.candidates, {"candidates": []}),
        decisions_payload=current,
        official_sources_payload=onboarding.load_json(
            args.official_sources, {"companies": []}
        ),
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
