#!/usr/bin/env python3
"""Apply the final cross-field venture profile quality fixes.

The owner-only venture PR runner executes this current-state-aware migration,
runs the full venture suite, regenerates the snapshot, and removes the helper.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
NARRATIVE = ROOT / "tools" / "sanitize_venture_narratives.py"
FINALIZER_TESTS = ROOT / "tests" / "test_finalize_venture_profiles.py"
NARRATIVE_TESTS = ROOT / "tests" / "test_venture_narrative_sanitizer.py"


def replace_function(path: Path, name: str, next_name: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if block in text:
        print(f"{name}: already applied")
        return
    start_marker = f"def {name}("
    end_marker = f"\n\ndef {next_name}("
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit(f"{name}: function boundary not found in {path}")
    path.write_text(text[:start] + block.rstrip() + text[end:], encoding="utf-8")
    print(f"{name}: replaced")


def insert_before(path: Path, marker: str, block: str, sentinel: str) -> None:
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        print(f"{sentinel}: already applied")
        return
    index = text.find(marker)
    if index < 0:
        raise SystemExit(f"{sentinel}: insertion marker not found in {path}")
    path.write_text(text[:index] + block.rstrip() + "\n\n" + text[index:], encoding="utf-8")
    print(f"{sentinel}: inserted")


def patch_finalizer() -> None:
    constants = '''PRODUCT_SUFFIX_RE = re.compile(
    r"(?:等)?(?:机器人|产品|解决方案)?系列$|(?:等产品|等解决方案)$",
    re.IGNORECASE,
)
LATIN_PERSON_PARTICLES = {"de", "del", "da", "di", "van", "von", "la", "le"}
LATIN_PERSON_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’.-]*$")
CJK_PERSON_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
FINAL_NARRATIVE_NOISE_RE = re.compile(
    r"\\b(?:investor relations|transfer agent|toll[- ]?free|media kit|"
    r"cookie settings|all rights reserved)\\b|"
    r"(?:投资者关系|联系我们|媒体资料|版权所有|备案号)",
    re.IGNORECASE,
)'''
    insert_before(FINALIZER, "TEAM_NAME_NOISE_TERMS =", constants, "PRODUCT_SUFFIX_RE")

    split_block = '''def _normalize_product_label(value: Any) -> str:
    item = clean_text(value, 180).strip(" >›→-|｜。.!！")
    item = PRODUCT_SUFFIX_RE.sub("", item).strip(" >›→-|｜。.!！")
    return clean_text(item, 180)


def _split_product_values(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for raw in values:
        value = clean_text(raw, 800)
        for part in re.split(
            r"[、，,;/]|\\s*与\\s*|\\s+and\\s+",
            value,
            flags=re.IGNORECASE,
        ):
            item = _normalize_product_label(part)
            if item:
                result.append(item)
    return result'''
    replace_function(FINALIZER, "_split_product_values", "_product_noise", split_block)

    team_block = '''def _person_like_name(value: Any) -> bool:
    name = clean_text(value, 120).strip(" ,，:：;；-|｜")
    lowered = name.casefold()
    if not name or any(term in lowered for term in TEAM_NAME_NOISE_TERMS):
        return False
    if CJK_PERSON_RE.fullmatch(name):
        return True
    tokens = [token for token in name.split() if token]
    if not 2 <= len(tokens) <= 6:
        return False
    if not LATIN_PERSON_TOKEN_RE.fullmatch(tokens[0]):
        return False
    if not LATIN_PERSON_TOKEN_RE.fullmatch(tokens[-1]):
        return False
    return all(
        LATIN_PERSON_TOKEN_RE.fullmatch(token)
        or token.casefold() in LATIN_PERSON_PARTICLES
        for token in tokens[1:-1]
    )


def finalize_team(values: Sequence[Any], aliases: Sequence[str]) -> list[dict[str, str]]:
    originals = {
        clean_text(row.get("name"), 120).casefold(): row
        for row in values
        if isinstance(row, dict) and clean_text(row.get("name"), 120)
    }
    result: list[dict[str, str]] = []
    for row in sanitize_team_members(values, aliases):
        name = clean_text(row.get("name"), 120)
        if not _person_like_name(name):
            continue
        original = originals.get(name.casefold(), {})
        result.append(
            {
                "name": name,
                "role": clean_text(row.get("role"), 160),
                "summary": clean_text(row.get("summary"), 360),
                "background": clean_text(original.get("background"), 420),
                "previousExperience": clean_text(
                    original.get("previousExperience"), 420
                ),
                "sourceUrl": normalize_url(row.get("sourceUrl", "")),
            }
        )
    return result[:20]'''
    replace_function(FINALIZER, "finalize_team", "finalize_financing", team_block)

    audit = '''def _final_semantic_errors(
    companies: dict[str, dict[str, Any]],
    institutions: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for slug, profile in companies.items():
        products = profile.get("products", [])
        for product in products if isinstance(products, list) else []:
            if (
                _normalize_product_label(product) != clean_text(product, 180)
                or _product_noise(product)
            ):
                errors.append(
                    f"company:{slug}:product:{clean_text(product, 80)}"
                )
        team = profile.get("team", [])
        for member in team if isinstance(team, list) else []:
            if not isinstance(member, dict) or not _person_like_name(
                member.get("name")
            ):
                name = member.get("name") if isinstance(member, dict) else ""
                errors.append(f"company:{slug}:team:{clean_text(name, 80)}")
        events = profile.get("capitalMarkets", [])
        for event in events if isinstance(events, list) else []:
            if not isinstance(event, dict) or not CAPITAL_EVIDENCE_RE.search(
                f"{event.get('title', '')} {event.get('summary', '')}"
            ):
                errors.append(f"company:{slug}:capital-market")
        for field in ("background", "technology"):
            if FINAL_NARRATIVE_NOISE_RE.search(
                clean_text(profile.get(field), 2000)
            ):
                errors.append(f"company:{slug}:{field}-navigation")

    for slug, profile in institutions.items():
        team = profile.get("team", [])
        for member in team if isinstance(team, list) else []:
            if not isinstance(member, dict) or not _person_like_name(
                member.get("name")
            ):
                name = member.get("name") if isinstance(member, dict) else ""
                errors.append(f"institution:{slug}:team:{clean_text(name, 80)}")
        for field in ("overview", "strategy"):
            if FINAL_NARRATIVE_NOISE_RE.search(
                clean_text(profile.get(field), 2000)
            ):
                errors.append(f"institution:{slug}:{field}-navigation")
    return errors'''
    insert_before(FINALIZER, "def finalize_snapshot(", audit, "def _final_semantic_errors(")

    text = FINALIZER.read_text(encoding="utf-8")
    old_start = '    quality = cleaned.setdefault("qualityGate", {})\n'
    schema_marker = '    cleaned["schemaVersion"] = max(2, int(cleaned.get("schemaVersion", 1) or 1))\n'
    start = text.find(old_start)
    end = text.find(schema_marker, start)
    if start < 0 or end < 0:
        raise SystemExit("final semantic quality block not found")
    quality_block = '''    quality = cleaned.setdefault("qualityGate", {})
    checks = quality.setdefault("checks", {})
    final_errors = _final_semantic_errors(companies, institutions)
    checks["finalSemanticConsistency"] = {
        "actual": len(final_errors),
        "required": 0,
        "passed": not final_errors,
    }
    quality["finalSemanticErrors"] = final_errors[:50]
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
'''
    if 'quality["finalSemanticErrors"]' not in text:
        FINALIZER.write_text(
            text[:start] + quality_block + text[end:], encoding="utf-8"
        )
        print("final semantic quality gate: applied")
    else:
        print("final semantic quality gate: already applied")


def patch_narratives() -> None:
    constants = '''PAGE_TITLE_PREFIX_RE = re.compile(
    r"^[^.!?。！？\\n]{8,180}\\s+::\\s+[^.!?。！？\\n]{2,100}[.!?。！？]\\s*",
    re.IGNORECASE,
)
PAGE_TAIL_RE = re.compile(
    r"\\b(?:investor relations|transfer agent|toll[- ]?free|media kit|"
    r"featured\\s*\\(\\d+\\)|cookie settings|all rights reserved)\\b|"
    r"(?:投资者关系|联系我们|加入我们|媒体资料|版权所有|备案号)",
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
DATE_TOKEN_RE = re.compile(
    r"\\b(?:20\\d{2}[-/.]\\d{1,2}(?:[-/.]\\d{1,2})?|"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\\s+\\d{1,2},\\s+20\\d{2})\\b",
    re.IGNORECASE,
)'''
    insert_before(NARRATIVE, "def _compact(", constants, "PAGE_TITLE_PREFIX_RE")

    split_block = '''def _trim_page_chrome(value: str) -> str:
    text = PAGE_TITLE_PREFIX_RE.sub("", clean_text(value, 5000), count=1)
    candidates = [
        match.start()
        for pattern in (PAGE_TAIL_RE, STREET_ADDRESS_RE, PHONE_RE)
        if (match := pattern.search(text)) is not None
        and match.start() >= 18
    ]
    dates = list(DATE_TOKEN_RE.finditer(text))
    if len(dates) >= 2 and dates[0].start() >= 18:
        candidates.append(dates[0].start())
    if candidates:
        text = text[: min(candidates)]
    return clean_text(text, 5000)


def _split_clauses(value: str) -> list[str]:
    text = _trim_page_chrome(value)
    if not text:
        return []
    text = text.replace("\\u00a0", " ")
    result: list[str] = []
    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = clean_text(raw, 900).strip(" .。|｜\\-")
        if len(clause) < 18:
            continue
        if "::" in clause and len(clause) <= 240:
            continue
        if len(clause) > 520:
            clause = clause[:520].rsplit(" ", 1)[0] or clause[:520]
        result.append(clause)
    return result'''
    replace_function(NARRATIVE, "_split_clauses", "_deduplicate", split_block)


def add_test(path: Path, marker: str, sentinel: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        print(f"{sentinel}: already present")
        return
    index = text.find(marker)
    if index < 0:
        raise SystemExit(f"{sentinel}: test insertion marker not found")
    path.write_text(text[:index] + block.rstrip() + "\n\n" + text[index:], encoding="utf-8")
    print(f"{sentinel}: added")


def patch_tests() -> None:
    finalizer_tests = '''    def test_catalog_series_suffix_is_normalized(self) -> None:
        products = finalizer.finalize_products(
            ["灵犀等机器人系列。", "Q1 2026", "Transfer Agent"],
            "远征、灵犀等机器人系列。",
        )
        self.assertEqual(products, ["远征", "灵犀"])

    def test_final_semantic_audit_reports_navigation_noise(self) -> None:
        errors = finalizer._final_semantic_errors(
            {
                "example": {
                    "products": ["Example API"],
                    "team": [],
                    "capitalMarkets": [],
                    "background": "Investor Relations Transfer Agent",
                    "technology": "Verified platform technology.",
                }
            },
            {},
        )
        self.assertIn("company:example:background-navigation", errors)
'''
    add_test(
        FINALIZER_TESTS,
        "    def test_financing_rejects_round_like_product_copy",
        "def test_catalog_series_suffix_is_normalized",
        finalizer_tests,
    )

    narrative_tests = '''    def test_trims_contact_address_and_date_tail(self) -> None:
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
    add_test(
        NARRATIVE_TESTS,
        "    def test_snapshot_sanitation_is_idempotent",
        "def test_trims_contact_address_and_date_tail",
        narrative_tests,
    )


def main() -> int:
    patch_finalizer()
    patch_narratives()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
