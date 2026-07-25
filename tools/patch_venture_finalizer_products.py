#!/usr/bin/env python3
"""Patch permanent venture narrative cleanup and regression tests.

The owner-only venture PR runner executes and removes this migration after the
patched files and regenerated snapshot pass the full venture test suite.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SANITIZER = ROOT / "tools" / "sanitize_venture_narratives.py"
TESTS = ROOT / "tests" / "test_venture_narrative_sanitizer.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_sanitizer() -> None:
    old_constants = '''CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\\n]+|(?<=\\.)\\s+(?=[A-Z\\u3400-\\u9fff])")
CJK_RE = re.compile(r"[\\u3400-\\u9fff]")
WORD_RE = re.compile(r"[A-Za-z0-9]+|[\\u3400-\\u9fff]")
'''
    new_constants = '''CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\\n]+|(?<=\\.)\\s+(?=[A-Z0-9\\u3400-\\u9fff])")
CJK_RE = re.compile(r"[\\u3400-\\u9fff]")
WORD_RE = re.compile(r"[A-Za-z0-9]+|[\\u3400-\\u9fff]")
DATE_TOKEN_RE = re.compile(
    r"\\b(?:20\\d{2}[-/.]\\d{1,2}(?:[-/.]\\d{1,2})?|"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\\s+\\d{1,2},\\s+20\\d{2})\\b",
    re.IGNORECASE,
)
STREET_ADDRESS_RE = re.compile(
    r"\\b\\d{2,6}\\s+[A-Z][A-Za-z.-]+(?:\\s+[A-Z][A-Za-z.-]+){0,4}\\s+"
    r"(?:Street|St\\.?|Avenue|Ave\\.?|Road|Rd\\.?|Boulevard|Blvd\\.?|"
    r"Drive|Dr\\.?|Lane|Ln\\.?|Way)\\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r"(?:toll[- ]?free|phone|tel(?:ephone)?|传真|电话)\\s*[:：]?\\s*"
    r"(?:\\+?\\d[\\d() .-]{7,}\\d)",
    re.IGNORECASE,
)
PAGE_CHROME_TERMS = (
    "investor relations",
    "transfer agent",
    "toll-free",
    "featured",
    "media kit",
    "locations",
    "latest news and events",
    "privacy policy",
    "cookie settings",
    "all rights reserved",
    "投资者关系",
    "联系方式",
    "联系我们",
    "加入我们",
    "版权所有",
)
'''
    replace_once(SANITIZER, old_constants, new_constants, "narrative constants")

    navigation_anchor = '''def _looks_like_navigation(value: str) -> bool:
'''
    helper = '''def _trim_page_chrome(value: str) -> str:
    text = clean_text(value, 1600)
    if not text:
        return ""
    lowered = text.casefold()
    cut_points = [
        index
        for term in PAGE_CHROME_TERMS
        if (index := lowered.find(term.casefold())) >= 0
    ]
    address = STREET_ADDRESS_RE.search(text)
    if address:
        cut_points.append(address.start())
    phone = PHONE_RE.search(text)
    if phone:
        cut_points.append(phone.start())
    dates = list(DATE_TOKEN_RE.finditer(text))
    if len(dates) >= 2:
        cut_points.append(dates[0].start())
    if not cut_points:
        return text
    prefix = text[: min(cut_points)].strip(" .。|｜\\-")
    return prefix if len(prefix) >= 18 else ""


'''
    text = SANITIZER.read_text(encoding="utf-8")
    if "def _trim_page_chrome(" not in text:
        if navigation_anchor not in text:
            raise SystemExit("page chrome helper insertion point not found")
        SANITIZER.write_text(text.replace(navigation_anchor, helper + navigation_anchor, 1), encoding="utf-8")
        print("page chrome helper: applied")
    else:
        print("page chrome helper: already applied")

    old_checks = '''    if re.search(r"all rights reserved|cookie settings|版权所有|备案号", lowered):
        return True

    hits = _navigation_hits(text)
'''
    new_checks = '''    if re.search(r"all rights reserved|cookie settings|版权所有|备案号", lowered):
        return True
    if STREET_ADDRESS_RE.search(text) or PHONE_RE.search(text):
        return True
    if len(DATE_TOKEN_RE.findall(text)) >= 2:
        return True
    if "::" in text and len(text) <= 240:
        return True
    if any(term in lowered for term in PAGE_CHROME_TERMS):
        return True

    hits = _navigation_hits(text)
'''
    replace_once(SANITIZER, old_checks, new_checks, "navigation checks")

    old_clause = '''    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = clean_text(raw, 900).strip(" .。|｜\\-")
        if len(clause) < 18:
'''
    new_clause = '''    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = _trim_page_chrome(raw).strip(" .。|｜\\-")
        if len(clause) < 18:
'''
    replace_once(SANITIZER, old_clause, new_clause, "clause page chrome trimming")


def patch_tests() -> None:
    anchor = '''    def test_snapshot_sanitation_is_idempotent(self) -> None:
'''
    additions = '''    def test_trims_contact_address_and_date_tail(self) -> None:
        value = (
            "We work with urgency and focus on the work that will accelerate our "
            "progress towards our mission and strengthen our company. "
            "1654 Smallman Street Pittsburgh, PA 15222 Toll-Free: (888) 583-9506 "
            "Investor Relations Email Transfer Agent Equiniti Trust Company, LLC. "
            "Featured July 22, 2026 August 7, 2025 May 1, 2025 Locations Our Company."
        )
        cleaned = sanitizer.sanitize_narrative(value)
        self.assertIn("accelerate our progress towards our mission", cleaned)
        self.assertNotIn("1654 Smallman Street", cleaned)
        self.assertNotIn("Investor Relations", cleaned)
        self.assertNotIn("July 22, 2026", cleaned)

    def test_removes_headline_fragment_but_keeps_technology_claims(self) -> None:
        value = (
            "Consumers’ Pockets Annually by 2035 :: Aurora Innovation, Inc. "
            "We are building a technology and a company to serve all people and all communities. "
            "We are committed to safely developing and deploying transformational self-driving technology."
        )
        cleaned = sanitizer.sanitize_narrative(value)
        self.assertNotIn("Consumers’ Pockets", cleaned)
        self.assertIn("serve all people and all communities", cleaned)
        self.assertIn("transformational self-driving technology", cleaned)

'''
    text = TESTS.read_text(encoding="utf-8")
    if "def test_trims_contact_address_and_date_tail" not in text:
        if anchor not in text:
            raise SystemExit("narrative test insertion point not found")
        TESTS.write_text(text.replace(anchor, additions + anchor, 1), encoding="utf-8")
        print("narrative regression tests: applied")
    else:
        print("narrative regression tests: already applied")


def main() -> int:
    patch_sanitizer()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
