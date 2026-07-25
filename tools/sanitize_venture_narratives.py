#!/usr/bin/env python3
"""Remove navigation and page-chrome noise from venture narrative fields.

Structured fields such as products, team members, and capital events are handled
by ``sanitize_venture_profiles.py``. This pass focuses on long-form text rendered
on company and institution detail pages: background, technology, overview, and
strategy. It is deterministic and supports an idempotence check for CI.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable

try:
    from .venture_profile_extraction import clean_text
except ImportError:
    from venture_profile_extraction import clean_text


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"

COMPANY_NARRATIVE_FIELDS = ("background", "technology")
INSTITUTION_NARRATIVE_FIELDS = ("overview", "strategy")

NAVIGATION_LABELS = {
    "home",
    "about",
    "company",
    "companies",
    "products",
    "solutions",
    "research",
    "policy",
    "commitments",
    "learn",
    "news",
    "insights",
    "investments",
    "projects",
    "more",
    "careers",
    "contact",
    "privacy",
    "terms",
    "portfolio",
    "team",
    "people",
    "首页",
    "关于我们",
    "公司介绍",
    "产品中心",
    "产品资料",
    "产品资料与下载",
    "数据服务",
    "解决方案",
    "新闻资讯",
    "加入我们",
    "联系我们",
    "招聘",
    "团队",
    "投资组合",
    "被投企业",
    "投资项目",
    "更多",
}

NAVIGATION_TERMS = tuple(sorted(NAVIGATION_LABELS, key=len, reverse=True))
CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+|(?<=\.)\s+(?=[A-Z\u3400-\u9fff])")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u3400-\u9fff]")
PAGE_TITLE_PREFIX_RE = re.compile(
    r"^[^.!?。！？\n]{8,180}\s+::\s+[^.!?。！？\n]{2,100}[.!?。！？]\s*",
    re.IGNORECASE,
)
PAGE_TAIL_RE = re.compile(
    r"\b(?:investor relations|transfer agent|toll[- ]?free|media kit|"
    r"featured\s*\(\d+\)|cookie settings|all rights reserved)\b|"
    r"(?:投资者关系|联系我们|加入我们|媒体资料|版权所有|备案号)",
    re.IGNORECASE,
)
STREET_ADDRESS_RE = re.compile(
    r"\b\d{2,6}\s+[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,3}\s+"
    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Drive|Dr\.?|Way)\b",
    re.IGNORECASE,
)


def _compact(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3400-\u9fff]+",
        "",
        clean_text(value, 2000).casefold(),
    )


NAVIGATION_COMPACTS = {_compact(item) for item in NAVIGATION_LABELS}


def _navigation_hits(value: str) -> list[str]:
    lowered = value.casefold()
    return [term for term in NAVIGATION_TERMS if term.casefold() in lowered]


def _looks_like_navigation(value: str) -> bool:
    text = clean_text(value, 1600)
    lowered = text.casefold()
    compact = _compact(text)
    if not text or not compact:
        return True
    if compact in NAVIGATION_COMPACTS:
        return True
    if re.search(r"all rights reserved|cookie settings|版权所有|备案号", lowered):
        return True

    hits = _navigation_hits(text)
    separator_hint = "\\" in text or "|" in text or "｜" in text
    if len(hits) >= 4:
        return True
    if separator_hint and len(hits) >= 2:
        return True
    if len(text) >= 220 and len(hits) >= 3:
        return True

    tokens = WORD_RE.findall(text)
    short_tokens = sum(len(token) <= 8 for token in tokens)
    if len(tokens) >= 18 and short_tokens / max(1, len(tokens)) >= 0.85:
        if len(hits) >= 3 and not re.search(r"\d", text):
            return True
    return False


def _trim_page_chrome(value: Any) -> str:
    text = PAGE_TITLE_PREFIX_RE.sub("", clean_text(value, 5000), count=1)
    candidates = [
        match.start()
        for pattern in (PAGE_TAIL_RE, STREET_ADDRESS_RE)
        if (match := pattern.search(text)) is not None and match.start() >= 32
    ]
    if candidates:
        text = text[: min(candidates)]
    return clean_text(text, 5000)


def _split_clauses(value: str) -> list[str]:
    text = _trim_page_chrome(value)
    if not text:
        return []
    text = text.replace("\u00a0", " ")
    result: list[str] = []
    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = clean_text(raw, 900).strip(" .。|｜\\-")
        if len(clause) < 18:
            continue
        if len(clause) > 520:
            clause = clause[:520].rsplit(" ", 1)[0] or clause[:520]
        result.append(clause)
    return result


def _deduplicate(clauses: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: list[str] = []
    for clause in clauses:
        key = _compact(clause)
        if not key:
            continue
        if any(
            key == previous
            or (len(key) >= 40 and len(previous) >= 40 and (key in previous or previous in key))
            for previous in seen
        ):
            continue
        result.append(clause)
        seen.append(key)
    return result


def sanitize_narrative(value: Any, fallback: str = "", *, limit: int = 780) -> str:
    """Keep concise evidence-bearing clauses and discard page navigation tails."""

    clauses = _deduplicate(
        clause
        for clause in _split_clauses(clean_text(value, 5000))
        if not _looks_like_navigation(clause)
    )

    selected: list[str] = []
    total = 0
    for clause in clauses:
        if total + len(clause) > limit and selected:
            continue
        selected.append(clause)
        total += len(clause)
        if len(selected) >= 4 or total >= limit:
            break

    if not selected:
        return clean_text(_trim_page_chrome(fallback), limit)

    cjk_count = sum(len(CJK_RE.findall(clause)) for clause in selected)
    character_count = sum(len(clause) for clause in selected)
    if cjk_count / max(1, character_count) >= 0.18:
        return clean_text("。".join(item.rstrip("。") for item in selected) + "。", limit)
    return clean_text(". ".join(item.rstrip(".") for item in selected) + ".", limit)


def _residual_narrative_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for kind, collection, fields in (
        ("company", payload.get("companies", {}), COMPANY_NARRATIVE_FIELDS),
        ("institution", payload.get("institutions", {}), INSTITUTION_NARRATIVE_FIELDS),
    ):
        if not isinstance(collection, dict):
            continue
        for slug, profile in collection.items():
            if not isinstance(profile, dict):
                continue
            for field in fields:
                text = clean_text(profile.get(field), 5000)
                if PAGE_TAIL_RE.search(text) or STREET_ADDRESS_RE.search(text) or PAGE_TITLE_PREFIX_RE.search(text):
                    errors.append(f"{kind}:{slug}:{field}")
    return errors


def sanitize_snapshot_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    cleaned = copy.deepcopy(payload)
    changed_fields = 0

    for profile in cleaned.get("companies", {}).values():
        if not isinstance(profile, dict):
            continue
        for field in COMPANY_NARRATIVE_FIELDS:
            original = clean_text(profile.get(field), 5000)
            normalized = sanitize_narrative(original)
            if normalized != original:
                changed_fields += 1
            profile[field] = normalized

    for profile in cleaned.get("institutions", {}).values():
        if not isinstance(profile, dict):
            continue
        for field in INSTITUTION_NARRATIVE_FIELDS:
            original = clean_text(profile.get(field), 5000)
            normalized = sanitize_narrative(original)
            if normalized != original:
                changed_fields += 1
            profile[field] = normalized

    errors = _residual_narrative_errors(cleaned)
    quality_gate = cleaned.setdefault("qualityGate", {})
    checks = quality_gate.setdefault("checks", {})
    checks["narrativeNoise"] = {
        "actual": len(errors),
        "required": 0,
        "passed": not errors,
    }
    quality_gate["narrativeErrors"] = errors[:50]
    quality_gate["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    return cleaned, changed_fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--path", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args()

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    cleaned, changed_fields = sanitize_snapshot_payload(payload)
    rendered = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    current = args.path.read_text(encoding="utf-8")

    if args.check:
        if rendered != current:
            print(f"Narrative sanitation required in {changed_fields} fields.")
            return 1
        if not cleaned.get("qualityGate", {}).get("checks", {}).get("narrativeNoise", {}).get("passed", False):
            print("Residual venture narrative noise remains.")
            return 1
        print("Venture narrative fields are sanitized.")
        return 0

    if rendered == current:
        print("No venture narrative changes.")
        return 0
    args.path.write_text(rendered, encoding="utf-8")
    print(f"Sanitized {changed_fields} venture narrative fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
