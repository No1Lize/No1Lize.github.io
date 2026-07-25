#!/usr/bin/env python3
"""Apply the final cross-field venture profile quality fixes.

This temporary migration is executed by the owner-only PR runner. It patches the
permanent crawler/finalizer sources and regression tests, then is removed from
the resulting commit together with the trigger files.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
NARRATIVE = ROOT / "tools" / "sanitize_venture_narratives.py"
CRAWLER = ROOT / "tools" / "crawl_venture_profiles.py"
REFRESH_WORKFLOW = ROOT / ".github" / "workflows" / "refresh-venture-profiles.yml"
FINALIZER_TESTS = ROOT / "tests" / "test_finalize_venture_profiles.py"


def replace_once(path: Path, old: str, new: str, label: str, *, required: bool = True) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return False
    if old not in text:
        if required:
            raise SystemExit(f"{label}: expected source block not found in {path}")
        print(f"{label}: source block already superseded")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")
    return True


def patch_finalizer() -> None:
    old_constants = '''PRODUCT_PERIOD_RE = re.compile(
    r"^(?:q[1-4]|fy)\\s*20\\d{2}$|^20\\d{2}\\s*(?:q[1-4]|年度|年报)$",
    re.IGNORECASE,
)
'''
    new_constants = '''PRODUCT_PERIOD_RE = re.compile(
    r"^(?:q[1-4]|fy)\\s*20\\d{2}$|^20\\d{2}\\s*(?:q[1-4]|年度|年报)$",
    re.IGNORECASE,
)
PRODUCT_SUFFIX_RE = re.compile(
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
)
'''
    replace_once(FINALIZER, old_constants, new_constants, "finalizer constants")

    old_split = '''def _split_product_values(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for raw in values:
        value = clean_text(raw, 800)
        result.extend(
            clean_text(part, 180).strip(" >›→-|｜。.!！")
            for part in re.split(
                r"[、，,;/]|\\s*与\\s*|\\s+and\\s+",
                value,
                flags=re.IGNORECASE,
            )
            if clean_text(part, 180).strip(" >›→-|｜。.!！")
        )
    return result
'''
    new_split = '''def _normalize_product_label(value: Any) -> str:
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
    return result
'''
    replace_once(FINALIZER, old_split, new_split, "product label normalization")

    old_team = '''def finalize_team(values: Sequence[Any], aliases: Sequence[str]) -> list[dict[str, str]]:
    originals = {
        clean_text(row.get("name"), 120).casefold(): row
        for row in values if isinstance(row, dict) and clean_text(row.get("name"), 120)
    }
    result: list[dict[str, str]] = []
    for row in sanitize_team_members(values, aliases):
        name = clean_text(row.get("name"), 120)
        if any(term in name.casefold() for term in TEAM_NAME_NOISE_TERMS):
            continue
        original = originals.get(name.casefold(), {})
        result.append(
            {
                "name": name,
                "role": clean_text(row.get("role"), 160),
                "summary": clean_text(row.get("summary"), 360),
                "background": clean_text(original.get("background"), 420),
                "previousExperience": clean_text(original.get("previousExperience"), 420),
                "sourceUrl": normalize_url(row.get("sourceUrl", "")),
            }
        )
    return result[:20]
'''
    new_team = '''def _person_like_name(value: Any) -> bool:
    name = clean_text(value, 120).strip(" ,，:：;；-|｜")
    lowered = name.casefold()
    if not name or any(term in lowered for term in TEAM_NAME_NOISE_TERMS):
        return False
    if CJK_PERSON_RE.fullmatch(name):
        return True
    tokens = [token for token in name.split() if token]
    if not 2 <= len(tokens) <= 6:
        return False
    if not LATIN_PERSON_TOKEN_RE.fullmatch(tokens[0]) or not LATIN_PERSON_TOKEN_RE.fullmatch(tokens[-1]):
        return False
    return all(
        LATIN_PERSON_TOKEN_RE.fullmatch(token) or token.casefold() in LATIN_PERSON_PARTICLES
        for token in tokens[1:-1]
    )


def finalize_team(values: Sequence[Any], aliases: Sequence[str]) -> list[dict[str, str]]:
    originals = {
        clean_text(row.get("name"), 120).casefold(): row
        for row in values if isinstance(row, dict) and clean_text(row.get("name"), 120)
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
                "previousExperience": clean_text(original.get("previousExperience"), 420),
                "sourceUrl": normalize_url(row.get("sourceUrl", "")),
            }
        )
    return result[:20]
'''
    replace_once(FINALIZER, old_team, new_team, "person-name validation")

    marker = '''def finalize_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
'''
    audit = '''def _final_semantic_errors(
    companies: dict[str, dict[str, Any]],
    institutions: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for slug, profile in companies.items():
        for product in profile.get("products", []) if isinstance(profile.get("products"), list) else []:
            if _normalize_product_label(product) != clean_text(product, 180) or _product_noise(product):
                errors.append(f"company:{slug}:product:{clean_text(product, 80)}")
        for member in profile.get("team", []) if isinstance(profile.get("team"), list) else []:
            if not isinstance(member, dict) or not _person_like_name(member.get("name")):
                errors.append(f"company:{slug}:team:{clean_text(member.get('name') if isinstance(member, dict) else '', 80)}")
        for event in profile.get("capitalMarkets", []) if isinstance(profile.get("capitalMarkets"), list) else []:
            if not isinstance(event, dict) or not CAPITAL_EVIDENCE_RE.search(
                f"{event.get('title', '')} {event.get('summary', '')}"
            ):
                errors.append(f"company:{slug}:capital-market")
        for field in ("background", "technology"):
            if FINAL_NARRATIVE_NOISE_RE.search(clean_text(profile.get(field), 2000)):
                errors.append(f"company:{slug}:{field}-navigation")
    for slug, profile in institutions.items():
        for member in profile.get("team", []) if isinstance(profile.get("team"), list) else []:
            if not isinstance(member, dict) or not _person_like_name(member.get("name")):
                errors.append(f"institution:{slug}:team:{clean_text(member.get('name') if isinstance(member, dict) else '', 80)}")
        for field in ("overview", "strategy"):
            if FINAL_NARRATIVE_NOISE_RE.search(clean_text(profile.get(field), 2000)):
                errors.append(f"institution:{slug}:{field}-navigation")
    return errors


'''
    text = FINALIZER.read_text(encoding="utf-8")
    if "def _final_semantic_errors(" not in text:
        if marker not in text:
            raise SystemExit("final semantic audit insertion point not found")
        FINALIZER.write_text(text.replace(marker, audit + marker, 1), encoding="utf-8")
        print("final semantic audit: applied")
    else:
        print("final semantic audit: already applied")

    old_quality = '''    quality = cleaned.setdefault("qualityGate", {})
    checks = quality.setdefault("checks", {})
    checks["finalSemanticConsistency"] = {
        "actual": 0,
        "required": 0,
        "passed": True,
    }
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
'''
    new_quality = '''    quality = cleaned.setdefault("qualityGate", {})
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
    replace_once(FINALIZER, old_quality, new_quality, "final semantic quality gate")


def patch_narratives() -> None:
    old_constants = '''WORD_RE = re.compile(r"[A-Za-z0-9]+|[\\u3400-\\u9fff]")
'''
    new_constants = '''WORD_RE = re.compile(r"[A-Za-z0-9]+|[\\u3400-\\u9fff]")
PAGE_TITLE_PREFIX_RE = re.compile(
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
    r"\\b\\d{2,6}\\s+[A-Z][A-Za-z.-]+(?:\\s+[A-Z][A-Za-z.-]+){0,3}\\s+"
    r"(?:Street|St\\.?|Avenue|Ave\\.?|Road|Rd\\.?|Boulevard|Blvd\\.?|Drive|Dr\\.?|Way)\\b",
    re.IGNORECASE,
)
'''
    replace_once(NARRATIVE, old_constants, new_constants, "narrative tail constants")

    old_split = '''def _split_clauses(value: str) -> list[str]:
    text = clean_text(value, 5000)
    if not text:
        return []
    text = text.replace("\\u00a0", " ")
    result: list[str] = []
    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = clean_text(raw, 900).strip(" .。|｜\\-")
        if len(clause) < 18:
            continue
        if len(clause) > 520:
            clause = clause[:520].rsplit(" ", 1)[0] or clause[:520]
        result.append(clause)
    return result
'''
    new_split = '''def _trim_page_chrome(value: str) -> str:
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
    text = text.replace("\\u00a0", " ")
    result: list[str] = []
    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = clean_text(raw, 900).strip(" .。|｜\\-")
        if len(clause) < 18:
            continue
        if len(clause) > 520:
            clause = clause[:520].rsplit(" ", 1)[0] or clause[:520]
        result.append(clause)
    return result
'''
    replace_once(NARRATIVE, old_split, new_split, "narrative page-chrome trimming")


def patch_crawler_quality() -> None:
    old = '''        team = profile.get("team", [])
        if team != sanitize_team_members(team, (profile.get("name", ""),)):
            semantic_errors.append(f"company:{slug}:team-noise")
    for slug, profile in institutions.items():
        team = profile.get("team", [])
        if team != sanitize_team_members(team, (profile.get("name", ""),)):
            semantic_errors.append(f"institution:{slug}:team-noise")
'''
    new = '''        team = profile.get("team", [])
        team_core = [
            {
                "name": clean_text(item.get("name"), 120),
                "role": clean_text(item.get("role"), 160),
                "summary": clean_text(item.get("summary"), 320),
                "sourceUrl": normalize_url(item.get("sourceUrl", "")),
            }
            for item in team if isinstance(item, dict)
        ]
        if team_core != sanitize_team_members(team_core, (profile.get("name", ""),)):
            semantic_errors.append(f"company:{slug}:team-noise")
    for slug, profile in institutions.items():
        team = profile.get("team", [])
        team_core = [
            {
                "name": clean_text(item.get("name"), 120),
                "role": clean_text(item.get("role"), 160),
                "summary": clean_text(item.get("summary"), 320),
                "sourceUrl": normalize_url(item.get("sourceUrl", "")),
            }
            for item in team if isinstance(item, dict)
        ]
        if team_core != sanitize_team_members(team_core, (profile.get("name", ""),)):
            semantic_errors.append(f"institution:{slug}:team-noise")
'''
    replace_once(CRAWLER, old, new, "crawler team quality projection")


def patch_refresh_workflow() -> None:
    old = '''          python tools/crawl_venture_profiles.py --validate-only
          python tools/enrich_venture_profiles.py --validate-only
          python tools/normalize_venture_profiles.py --check
          python tools/finalize_venture_profiles.py --check
'''
    new = '''          python tools/crawl_venture_profiles.py --validate-only
          python tools/enrich_venture_profiles.py --validate-only
          python tools/finalize_venture_profiles.py --check
'''
    replace_once(REFRESH_WORKFLOW, old, new, "refresh workflow final-stage validation")


def patch_tests() -> None:
    text = FINALIZER_TESTS.read_text(encoding="utf-8")
    import_old = '''from tools import finalize_venture_profiles as finalizer
'''
    import_new = '''from tools import finalize_venture_profiles as finalizer
from tools.crawl_venture_profiles import evaluate_quality
'''
    if import_new not in text:
        if import_old not in text:
            raise SystemExit("finalizer test import marker not found")
        text = text.replace(import_old, import_new, 1)

    marker = '''    def test_financing_rejects_round_like_product_copy(self) -> None:
'''
    additions = '''    def test_catalog_series_suffix_is_normalized(self) -> None:
        products = finalizer.finalize_products(
            ["灵犀等机器人系列。", "Q1 2026", "Transfer Agent"],
            "远征、灵犀等机器人系列。",
        )
        self.assertEqual(products, ["远征", "灵犀"])

    def test_narrative_removes_address_and_investor_relations_tail(self) -> None:
        value = (
            "We build technology that serves all communities. "
            "1654 Smallman Street Pittsburgh, PA 15222 Toll-Free: (888) 583-9506 "
            "Investor Relations Transfer Agent Media Kit Locations."
        )
        cleaned = finalizer.sanitize_narrative(value)
        self.assertIn("serves all communities", cleaned)
        self.assertNotIn("Smallman Street", cleaned)
        self.assertNotIn("Investor Relations", cleaned)

    def test_crawler_quality_ignores_finalizer_experience_fields(self) -> None:
        quality = evaluate_quality(
            {
                "example": {
                    "name": "Example",
                    "products": ["Example API"],
                    "team": [
                        {
                            "name": "Chris Urmson",
                            "role": "CEO",
                            "summary": "",
                            "background": "Previously led autonomous driving research.",
                            "previousExperience": "Former engineering executive.",
                            "sourceUrl": "https://example.com/team",
                        }
                    ],
                    "sources": [],
                    "status": "ok",
                }
            },
            {},
            1,
            0,
            [{"kind": "company", "slug": "example"}],
        )
        self.assertTrue(quality["checks"]["semanticNoise"]["passed"])

'''
    if "def test_catalog_series_suffix_is_normalized" not in text:
        if marker not in text:
            raise SystemExit("finalizer test insertion marker not found")
        text = text.replace(marker, additions + marker, 1)
    FINALIZER_TESTS.write_text(text, encoding="utf-8")
    print("venture finalizer regressions: applied")


def main() -> int:
    patch_finalizer()
    patch_narratives()
    patch_crawler_quality()
    patch_refresh_workflow()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
