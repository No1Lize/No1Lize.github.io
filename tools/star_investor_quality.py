"""Conservative quality helpers for STAR Market prospectus investor extraction.

Holding facts are accepted only when they are present on one explicit evidence
row and unambiguously associated with the disclosed shareholder name. A resolved
legal name may differ from the short name printed in the table; in that case the
strict row structure is used without inventing evidence text.
"""

from __future__ import annotations

import re
from typing import Any

ReviewStatus = str

PERCENT_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{1,6})?)\s*%")
SHARES_PATTERN = re.compile(r"(?<!\d)([\d,]+(?:\.\d+)?)\s*(万)?\s*股")
STRICT_TABLE_ROW_PATTERN = re.compile(
    r"^\s*(?P<rank>\d{1,3})\s+"
    r"(?P<alias>.+?)\s+"
    r"(?P<shares>\d[\d,]*(?:\.\d+)?)\s+"
    r"(?P<pct>\d{1,3}(?:\.\d+)?)\s*%?"
    r"(?:\s+\d[\d,]*(?:\.\d+)?\s+\d{1,3}(?:\.\d+)?\s*%?)?"
    r"\s*$"
)

_GENERIC_LEGAL_FORMS = {
    "有限公司",
    "股份有限公司",
    "有限责任公司",
    "管理有限公司",
    "投资管理有限公司",
    "基金管理有限公司",
    "资本管理有限公司",
    "股权投资有限公司",
    "管理合伙企业（有限合伙）",
    "管理合伙企业(有限合伙)",
    "投资管理中心（有限合伙）",
    "投资管理中心(有限合伙)",
    "有限合伙",
    "有限合伙企业",
}

_NARRATIVE_PREFIXES = (
    "整体变更",
    "事务合伙人为",
    "执行事务合伙人为",
    "伙人暨执行事务合伙人为",
    "普通合伙人为",
    "均为",
    "立群通过",
    "雨持有",
)

_NARRATIVE_MARKERS = (
    "的董事长",
    "的普通合伙人",
    "的执行事务合伙人",
    "担任",
    "持有公司股票",
    "间接持有",
    "的出资额",
    "为发行人",
)


def normalize_review_text(value: Any) -> str:
    return re.sub(
        r"[\s·•・()（）\[\]【】{}<>《》,，.。:：;；'\"“”‘’_\-/\\&+－—]",
        "",
        str(value or "").casefold(),
    ).strip()


_GENERIC_KEYS = {normalize_review_text(value) for value in _GENERIC_LEGAL_FORMS}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _strict_table_match(evidence: str) -> re.Match[str] | None:
    return STRICT_TABLE_ROW_PATTERN.match(str(evidence or "").strip())


def _tail_after_name(evidence: str, name: str, limit: int = 220) -> str:
    evidence = str(evidence or "")
    name = str(name or "")
    position = evidence.find(name)
    if position >= 0:
        return evidence[position + len(name) : position + len(name) + limit]
    strict = _strict_table_match(evidence)
    if strict:
        return evidence[strict.start("shares") : strict.end()]
    return evidence[:limit]


def extract_same_line_holding(
    evidence: str,
    name: str,
) -> tuple[float | None, float | None, list[str]]:
    """Extract one pre-IPO share value and percentage from one evidence row."""

    strict = _strict_table_match(evidence)
    if strict:
        shares = float(strict.group("shares").replace(",", ""))
        ownership = float(strict.group("pct"))
        if shares > 0 and 0 < ownership <= 100:
            return shares, ownership, []

    tail = _tail_after_name(evidence, name)
    reasons: list[str] = []

    percent_matches = list(PERCENT_PATTERN.finditer(tail))
    ownership: float | None = None
    if len(percent_matches) == 1:
        candidate = float(percent_matches[0].group(1))
        if 0 < candidate <= 100:
            ownership = candidate
    elif len(percent_matches) > 1:
        reasons.append("ambiguous-holding-row")

    share_matches = list(SHARES_PATTERN.finditer(tail))
    shares: float | None = None
    if len(share_matches) == 1:
        candidate = float(share_matches[0].group(1).replace(",", ""))
        if share_matches[0].group(2):
            candidate *= 10_000
        if candidate > 0:
            shares = candidate
    elif len(share_matches) > 1:
        reasons.append("ambiguous-holding-row")

    return shares, ownership, _unique(reasons)


def _same_number(left: float | int | None, right: float | int | None) -> bool:
    if left is None or right is None:
        return left is right
    return abs(float(left) - float(right)) <= max(1e-6, abs(float(right)) * 1e-9)


def derive_review(
    *,
    name: str,
    company_name: str = "",
    evidence: str = "",
    pre_ipo_shares: float | int | None = None,
    pre_ipo_ownership_pct: float | int | None = None,
    explicit_status: str = "",
    explicit_reasons: list[str] | None = None,
) -> tuple[ReviewStatus, list[str]]:
    if explicit_status in {"verified", "needs_review", "rejected"}:
        return explicit_status, _unique(list(explicit_reasons or []))

    compact_name = re.sub(r"\s+", "", str(name or "").strip())
    name_key = normalize_review_text(compact_name)
    company_key = normalize_review_text(company_name)
    evidence_key = normalize_review_text(evidence)
    strict_row = _strict_table_match(evidence)

    if not name_key:
        return "rejected", ["invalid-name"]

    if (
        len(company_key) >= 3
        and company_key in name_key
        and re.search(r"(?:股份有限公司|有限责任公司|有限公司)$", compact_name)
    ):
        return "rejected", ["issuer-name"]

    if name_key in _GENERIC_KEYS or re.fullmatch(
        r"[（(]?[一二三四五六七八九十百0-9]+[）)]?(?:有限公司|股份有限公司|有限合伙企业?)",
        compact_name,
    ):
        return "rejected", ["generic-legal-form"]

    if compact_name.startswith(_NARRATIVE_PREFIXES) or any(
        marker in compact_name for marker in _NARRATIVE_MARKERS
    ):
        return "rejected", ["narrative-name-fragment"]

    if re.match(r"^(管理|投资管理|基金管理|资本管理)[（(]", compact_name):
        return "rejected", ["generic-legal-form"]

    # Resolved legal names can differ from the alias printed in the shareholder
    # table. A strict table row is accepted as name evidence because its alias is
    # separately preserved as disclosedName by the parser.
    if not evidence_key or (name_key not in evidence_key and strict_row is None):
        return "rejected", ["name-not-in-evidence"]

    extracted_shares, extracted_pct, holding_reasons = extract_same_line_holding(
        evidence,
        compact_name,
    )
    if holding_reasons:
        return "rejected", holding_reasons

    mismatches: list[str] = []
    if pre_ipo_shares is not None and not _same_number(pre_ipo_shares, extracted_shares):
        mismatches.append("holding-value-mismatch")
    if pre_ipo_ownership_pct is not None and not _same_number(
        pre_ipo_ownership_pct,
        extracted_pct,
    ):
        mismatches.append("holding-value-mismatch")
    if mismatches:
        return "rejected", _unique(mismatches)

    reasons: list[str] = []
    if pre_ipo_shares is None and pre_ipo_ownership_pct is None:
        reasons.append("no-holding-fact")
    reasons.append("awaiting-human-review")
    return "needs_review", _unique(reasons)
