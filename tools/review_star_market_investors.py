#!/usr/bin/env python3
"""Apply evidence and human-review gates to STAR Market investor snapshots.

The upstream PDF parser is recall-oriented and can discover text fragments outside a
clean shareholder-table row. This post-processing stage makes publication
precision-oriented:

* holding values are rebuilt only from the same evidence line after the candidate;
* obvious legal-form and narrative fragments are marked ``rejected``;
* every remaining machine candidate is ``needs_review`` by default;
* human ``verified`` or ``rejected`` decisions come only from a versioned manifest;
* contact fields are withheld until the candidate is explicitly verified.

Rejected rows remain in the machine-readable snapshot for auditability, while the
frontend review gate excludes them from the public candidate list.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .star_investor_quality import derive_review, extract_same_line_holding
except ImportError:
    from star_investor_quality import derive_review, extract_same_line_holding

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "public" / "data" / "star_market_investors.json"
DEFAULT_REVIEW_PATH = ROOT / "config" / "star_market_investor_reviews.json"
REVIEW_STATUSES = {"verified", "needs_review", "rejected"}
MANIFEST_STATUSES = {"verified", "rejected"}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return payload


def _valid_review_time(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def load_review_manifest(path: Path = DEFAULT_REVIEW_PATH) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    if int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported STAR investor review manifest schema")
    reviews = payload.get("reviews")
    if not isinstance(reviews, dict):
        raise ValueError("STAR investor review manifest requires a reviews object")

    result: dict[str, dict[str, Any]] = {}
    for key, raw in reviews.items():
        if not isinstance(key, str) or ":" not in key:
            raise ValueError(f"invalid review key: {key!r}")
        if not isinstance(raw, dict):
            raise ValueError(f"{key}: review decision must be an object")
        status = str(raw.get("status", ""))
        reviewer = str(raw.get("reviewer", "")).strip()
        reviewed_at = str(raw.get("reviewedAt", "")).strip()
        note = str(raw.get("note", "")).strip()
        reasons = raw.get("reasons", [])
        if status not in MANIFEST_STATUSES:
            raise ValueError(f"{key}: status must be verified or rejected")
        if not reviewer:
            raise ValueError(f"{key}: reviewer is required")
        if not reviewed_at or not _valid_review_time(reviewed_at):
            raise ValueError(f"{key}: reviewedAt must be an ISO-8601 date or timestamp")
        if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
            raise ValueError(f"{key}: reasons must be an array of strings")
        result[key] = {
            "status": status,
            "reviewer": reviewer,
            "reviewedAt": reviewed_at,
            "note": note,
            "reasons": list(dict.fromkeys(reason for reason in reasons if reason)),
        }
    return result


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def review_key(company_slug: str, investor: dict[str, Any]) -> str:
    investor_id = str(investor.get("id", "")).strip()
    if not company_slug or not investor_id:
        raise ValueError("review key requires company slug and investor id")
    return f"{company_slug}:{investor_id}"


def _clear_review_metadata(investor: dict[str, Any]) -> None:
    for key in ("reviewedBy", "reviewedAt", "reviewNote", "reviewSource"):
        investor.pop(key, None)


def _apply_candidate_review(
    company_slug: str,
    company: dict[str, Any],
    investor: dict[str, Any],
    decision: dict[str, Any] | None,
) -> None:
    name = str(investor.get("name", ""))
    evidence = str(investor.get("evidence", ""))
    key = review_key(company_slug, investor)
    investor["reviewKey"] = key
    _clear_review_metadata(investor)

    shares, ownership_pct, holding_reasons = extract_same_line_holding(evidence, name)
    investor.pop("preIpoShares", None)
    investor.pop("preIpoOwnershipPct", None)
    if shares is not None:
        investor["preIpoShares"] = round(shares, 4)
    if ownership_pct is not None:
        investor["preIpoOwnershipPct"] = round(ownership_pct, 6)

    derived_status, derived_reasons = derive_review(
        name=name,
        company_name=str(company.get("name", "")),
        evidence=evidence,
        pre_ipo_shares=shares,
        pre_ipo_ownership_pct=ownership_pct,
    )
    derived_reasons = _unique([*derived_reasons, *holding_reasons])

    if decision is None:
        status = derived_status
        reasons = derived_reasons
    elif decision["status"] == "rejected":
        status = "rejected"
        reasons = _unique(["human-rejected", *decision["reasons"], *derived_reasons])
    elif derived_status == "rejected":
        status = "rejected"
        reasons = _unique(["review-manifest-evidence-conflict", *derived_reasons])
    else:
        status = "verified"
        reasons = _unique(decision["reasons"])

    investor["reviewStatus"] = status
    investor["reviewReasons"] = reasons

    if decision is not None:
        investor["reviewedBy"] = decision["reviewer"]
        investor["reviewedAt"] = decision["reviewedAt"]
        investor["reviewNote"] = decision["note"]
        investor["reviewSource"] = "manifest"

    # Contact attribution cannot be established from the short evidence line alone.
    # Keep fields private until a human decision verifies this exact review key.
    if status != "verified":
        investor.pop("publicContact", None)
        investor["contactStatus"] = "withheld-pending-review"
    elif investor.get("publicContact"):
        investor["contactStatus"] = "prospectus-public"
    else:
        investor["contactStatus"] = "not-disclosed-in-prospectus"


def review_snapshot(
    snapshot: dict[str, Any],
    review_manifest: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reviewed = deepcopy(snapshot)
    decisions = review_manifest or {}
    used_decisions: set[str] = set()
    companies = reviewed.get("companies")
    if not isinstance(companies, dict):
        raise ValueError("STAR investor snapshot requires a companies object")

    status_counts = {status: 0 for status in REVIEW_STATUSES}
    raw_count = 0

    for company_slug, company in companies.items():
        if not isinstance(company, dict):
            continue
        investors = company.get("investors")
        if not isinstance(investors, list):
            continue

        company_counts = {status: 0 for status in REVIEW_STATUSES}
        for investor in investors:
            if not isinstance(investor, dict):
                continue
            key = review_key(str(company_slug), investor)
            decision = decisions.get(key)
            if decision is not None:
                used_decisions.add(key)
            _apply_candidate_review(str(company_slug), company, investor, decision)
            status = str(investor.get("reviewStatus", "needs_review"))
            company_counts[status] += 1
            status_counts[status] += 1
            raw_count += 1

        company["institutionalInvestorCount"] = len(investors)
        company["reviewCandidateCount"] = company_counts["verified"] + company_counts["needs_review"]
        company["verifiedInvestorCount"] = company_counts["verified"]
        company["rejectedInvestorCount"] = company_counts["rejected"]

    unmatched = sorted(set(decisions) - used_decisions)
    if unmatched:
        raise ValueError("review manifest contains unmatched keys: " + ", ".join(unmatched))

    reviewed["investorCount"] = raw_count
    reviewed["reviewCandidateCount"] = status_counts["verified"] + status_counts["needs_review"]
    reviewed["verifiedInvestorCount"] = status_counts["verified"]
    reviewed["needsReviewInvestorCount"] = status_counts["needs_review"]
    reviewed["rejectedInvestorCount"] = status_counts["rejected"]
    reviewed["reviewManifestDecisionCount"] = len(used_decisions)

    methodology = reviewed.setdefault("methodology", {})
    if isinstance(methodology, dict):
        methodology["holdingBinding"] = (
            "shares and ownership are rebuilt only from the same evidence line "
            "after the candidate institution name"
        )
        methodology["reviewGate"] = (
            "machine candidates are needs_review by default; obvious fragments and "
            "evidence conflicts are rejected"
        )
        methodology["humanReview"] = (
            "verified and human-rejected decisions are loaded from the versioned "
            "config/star_market_investor_reviews.json manifest"
        )
        methodology["contactPublication"] = (
            "institution contact fields are withheld until the candidate review key "
            "is explicitly human-verified"
        )

    return reviewed


def validate_reviewed_snapshot(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    companies = snapshot.get("companies")
    if not isinstance(companies, dict):
        return ["companies must be an object"]

    counts = {status: 0 for status in REVIEW_STATUSES}
    decision_count = 0
    total = 0
    for slug, company in companies.items():
        if not isinstance(company, dict):
            errors.append(f"{slug}: invalid company record")
            continue
        investors = company.get("investors")
        if not isinstance(investors, list):
            errors.append(f"{slug}: investors must be an array")
            continue
        for investor in investors:
            if not isinstance(investor, dict):
                errors.append(f"{slug}: invalid investor record")
                continue
            name = str(investor.get("name", ""))
            status = str(investor.get("reviewStatus", ""))
            reasons = investor.get("reviewReasons")
            expected_key = f"{slug}:{investor.get('id', '')}"
            if investor.get("reviewKey") != expected_key:
                errors.append(f"{slug}: {name} has invalid reviewKey")
            if status not in REVIEW_STATUSES:
                errors.append(f"{slug}: {name} has invalid reviewStatus")
                continue
            if not isinstance(reasons, list):
                errors.append(f"{slug}: {name} reviewReasons must be an array")
            independent_status, independent_reasons = derive_review(
                name=name,
                company_name=str(company.get("name", "")),
                evidence=str(investor.get("evidence", "")),
                pre_ipo_shares=investor.get("preIpoShares"),
                pre_ipo_ownership_pct=investor.get("preIpoOwnershipPct"),
            )
            if status in {"verified", "needs_review"} and independent_status == "rejected":
                errors.append(
                    f"{slug}: {name} bypasses review gate: {','.join(independent_reasons)}"
                )
            if status == "verified":
                if investor.get("reviewSource") != "manifest":
                    errors.append(f"{slug}: {name} verified without manifest source")
                if not str(investor.get("reviewedBy", "")).strip():
                    errors.append(f"{slug}: {name} verified without reviewer")
                if not _valid_review_time(str(investor.get("reviewedAt", ""))):
                    errors.append(f"{slug}: {name} verified without valid reviewedAt")
            if investor.get("reviewSource") == "manifest":
                decision_count += 1
            if status != "verified" and investor.get("publicContact"):
                errors.append(f"{slug}: {name} exposes unverified contact fields")
            counts[status] += 1
            total += 1

    expected = {
        "investorCount": total,
        "reviewCandidateCount": counts["verified"] + counts["needs_review"],
        "verifiedInvestorCount": counts["verified"],
        "needsReviewInvestorCount": counts["needs_review"],
        "rejectedInvestorCount": counts["rejected"],
        "reviewManifestDecisionCount": decision_count,
    }
    for key, value in expected.items():
        if int(snapshot.get(key, -1)) != value:
            errors.append(f"{key} mismatch: expected {value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    review_manifest = load_review_manifest(args.reviews)
    snapshot = load_json(args.input)
    if args.check:
        errors = validate_reviewed_snapshot(snapshot)
        if errors:
            raise SystemExit("STAR investor review snapshot invalid:\n- " + "\n- ".join(errors))
        print(
            json.dumps(
                {
                    "valid": True,
                    "reviewManifestDecisionCount": len(review_manifest),
                },
                ensure_ascii=False,
            )
        )
        return 0

    reviewed = review_snapshot(snapshot, review_manifest)
    errors = validate_reviewed_snapshot(reviewed)
    if errors:
        raise SystemExit("reviewed STAR investor snapshot invalid:\n- " + "\n- ".join(errors))
    output = args.output or args.input
    output.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "investorCount": reviewed.get("investorCount", 0),
                "reviewCandidateCount": reviewed.get("reviewCandidateCount", 0),
                "verifiedInvestorCount": reviewed.get("verifiedInvestorCount", 0),
                "rejectedInvestorCount": reviewed.get("rejectedInvestorCount", 0),
                "reviewManifestDecisionCount": reviewed.get("reviewManifestDecisionCount", 0),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
