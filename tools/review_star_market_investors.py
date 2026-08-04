#!/usr/bin/env python3
"""Apply a conservative review gate to STAR Market investor snapshots.

The upstream PDF parser is intentionally recall-oriented and can discover text
fragments outside a clean shareholder-table row. This post-processing stage makes
the published snapshot precision-oriented:

* holding values are rebuilt only from the same evidence line after the candidate;
* obvious legal-form and narrative fragments are marked ``rejected``;
* every other machine candidate remains ``needs_review`` unless an explicit human
  ``verified`` status already exists and is consistent with the evidence line;
* contact fields are withheld until the candidate is explicitly verified.

Rejected rows remain in the machine-readable snapshot for auditability, while the
frontend review gate excludes them from the public candidate list.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from .star_investor_quality import derive_review, extract_same_line_holding
except ImportError:
    from star_investor_quality import derive_review, extract_same_line_holding

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "public" / "data" / "star_market_investors.json"
REVIEW_STATUSES = {"verified", "needs_review", "rejected"}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("STAR investor snapshot must be a JSON object")
    return payload


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _apply_candidate_review(company: dict[str, Any], investor: dict[str, Any]) -> None:
    name = str(investor.get("name", ""))
    evidence = str(investor.get("evidence", ""))

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

    explicit_status = str(investor.get("reviewStatus", ""))
    explicit_reasons = investor.get("reviewReasons")
    if not isinstance(explicit_reasons, list):
        explicit_reasons = []
    explicit_reasons = [str(reason) for reason in explicit_reasons]

    if explicit_status == "rejected":
        status = "rejected"
        reasons = _unique([*explicit_reasons, *derived_reasons])
    elif explicit_status == "verified":
        if derived_status == "rejected":
            status = "rejected"
            reasons = _unique(["verified-evidence-conflict", *derived_reasons])
        else:
            status = "verified"
            reasons = _unique(explicit_reasons)
    elif explicit_status == "needs_review":
        status = "rejected" if derived_status == "rejected" else "needs_review"
        reasons = _unique([*explicit_reasons, *derived_reasons])
    else:
        status = derived_status
        reasons = derived_reasons

    investor["reviewStatus"] = status
    investor["reviewReasons"] = reasons

    # Contact attribution cannot be established from the short evidence line alone.
    # Keep the fields private until a human explicitly verifies the institution row.
    if status != "verified":
        investor.pop("publicContact", None)
        investor["contactStatus"] = "withheld-pending-review"


def review_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    reviewed = deepcopy(snapshot)
    companies = reviewed.get("companies")
    if not isinstance(companies, dict):
        raise ValueError("STAR investor snapshot requires a companies object")

    status_counts = {status: 0 for status in REVIEW_STATUSES}
    raw_count = 0

    for company in companies.values():
        if not isinstance(company, dict):
            continue
        investors = company.get("investors")
        if not isinstance(investors, list):
            continue

        company_counts = {status: 0 for status in REVIEW_STATUSES}
        for investor in investors:
            if not isinstance(investor, dict):
                continue
            _apply_candidate_review(company, investor)
            status = str(investor.get("reviewStatus", "needs_review"))
            company_counts[status] += 1
            status_counts[status] += 1
            raw_count += 1

        company["institutionalInvestorCount"] = len(investors)
        company["reviewCandidateCount"] = company_counts["verified"] + company_counts["needs_review"]
        company["verifiedInvestorCount"] = company_counts["verified"]
        company["rejectedInvestorCount"] = company_counts["rejected"]

    reviewed["investorCount"] = raw_count
    reviewed["reviewCandidateCount"] = status_counts["verified"] + status_counts["needs_review"]
    reviewed["verifiedInvestorCount"] = status_counts["verified"]
    reviewed["needsReviewInvestorCount"] = status_counts["needs_review"]
    reviewed["rejectedInvestorCount"] = status_counts["rejected"]

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
        methodology["contactPublication"] = (
            "institution contact fields are withheld until the candidate row is "
            "explicitly human-verified"
        )

    return reviewed


def validate_reviewed_snapshot(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    companies = snapshot.get("companies")
    if not isinstance(companies, dict):
        return ["companies must be an object"]

    counts = {status: 0 for status in REVIEW_STATUSES}
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
    }
    for key, value in expected.items():
        if int(snapshot.get(key, -1)) != value:
            errors.append(f"{key} mismatch: expected {value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    snapshot = load_json(args.input)
    if args.check:
        errors = validate_reviewed_snapshot(snapshot)
        if errors:
            raise SystemExit("STAR investor review snapshot invalid:\n- " + "\n- ".join(errors))
        print(json.dumps({"valid": True}, ensure_ascii=False))
        return 0

    reviewed = review_snapshot(snapshot)
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
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
