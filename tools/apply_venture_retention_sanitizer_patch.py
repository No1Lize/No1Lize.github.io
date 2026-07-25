#!/usr/bin/env python3
from pathlib import Path

extraction_path = Path("tools/venture_profile_extraction.py")
extraction = extraction_path.read_text(encoding="utf-8")

product_marker = '''def extract_products(pages: Sequence[ParsedPage], fallback: str) -> list[str]:
'''
product_sanitizer = '''def sanitize_product_items(values: Sequence[Any]) -> list[str]:
    """Remove generic navigation/document labels from current or retained data."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = clean_text(raw, 180).strip(" >›→-|｜")
        lowered = item.casefold()
        compact = re.sub(r"[^a-z0-9\\u3400-\\u9fff]+", "", lowered)
        if not item or lowered in NAVIGATION_NOISE or lowered in GENERIC_PRODUCT_LABELS:
            continue
        if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):
            continue
        if compact in {
            re.sub(r"\\W+", "", label).casefold()
            for label in GENERIC_PRODUCT_LABELS
        }:
            continue
        if compact in seen:
            continue
        result.append(item)
        seen.add(compact)
        if len(result) >= 10:
            break
    return result


'''
if product_sanitizer not in extraction:
    if product_marker not in extraction:
        raise SystemExit("product marker not found")
    extraction = extraction.replace(product_marker, product_sanitizer + product_marker, 1)

team_marker = '''def extract_team(pages: Sequence[ParsedPage], aliases: Sequence[str]) -> list[dict[str, str]]:
'''
team_sanitizer = '''def sanitize_team_members(
    members: Sequence[dict[str, Any]], aliases: Sequence[str]
) -> list[dict[str, str]]:
    """Apply current person-name rules to newly crawled and retained history."""
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    alias_keys = {clean_text(alias, 120).casefold() for alias in aliases if alias}
    for member in members:
        if not isinstance(member, dict):
            continue
        name = clean_text(member.get("name"), 120).strip(" ,，:：;；-|｜")
        role = clean_text(member.get("role"), 160)
        if not _valid_person_name(name):
            continue
        if any(alias in name.casefold() for alias in alias_keys if len(alias) >= 2):
            continue
        key = name.casefold()
        if key in seen:
            existing = next(item for item in result if item["name"].casefold() == key)
            if not existing.get("role") and role:
                existing["role"] = role
            continue
        result.append(
            {
                "name": name,
                "role": role,
                "summary": clean_text(member.get("summary"), 320),
                "sourceUrl": normalize_url(member.get("sourceUrl", "")),
            }
        )
        seen.add(key)
        if len(result) >= 16:
            break
    return result


'''
if team_sanitizer not in extraction:
    if team_marker not in extraction:
        raise SystemExit("team marker not found")
    extraction = extraction.replace(team_marker, team_sanitizer + team_marker, 1)

extraction_path.write_text(extraction, encoding="utf-8")

crawler_path = Path("tools/crawl_venture_profiles.py")
crawler = crawler_path.read_text(encoding="utf-8")
for old, new in (
    (
        '''        extract_team,\n        normalize_url,\n''',
        '''        extract_team,\n        sanitize_product_items,\n        sanitize_team_members,\n        normalize_url,\n''',
    ),
):
    if new not in crawler:
        if crawler.count(old) != 2:
            raise SystemExit(f"expected two import markers, found {crawler.count(old)}")
        crawler = crawler.replace(old, new)

company_old = '''    profile = build_company_profile(company, pages, warnings, updated_at)
    profile, retained = retain_richer_profile(profile, previous, "company")
    status = {
'''
company_new = '''    profile = build_company_profile(company, pages, warnings, updated_at)
    profile, retained = retain_richer_profile(profile, previous, "company")
    # Retained history must pass the latest semantic rules too. Otherwise a
    # temporary homepage outage could resurrect navigation labels from an old
    # snapshot even though new extraction is already stricter.
    profile["team"] = sanitize_team_members(profile.get("team", []), company.aliases)
    profile["products"] = sanitize_product_items(profile.get("products", []))
    profile["evidenceScore"] = evidence_score(profile, "company")
    status = {
'''
if company_new not in crawler:
    if company_old not in crawler:
        raise SystemExit("company retention marker not found")
    crawler = crawler.replace(company_old, company_new, 1)

institution_old = '''    profile = build_institution_profile(institution, pages, companies, warnings, updated_at)
    profile, retained = retain_richer_profile(profile, previous, "institution")
    status = {
'''
institution_new = '''    profile = build_institution_profile(institution, pages, companies, warnings, updated_at)
    profile, retained = retain_richer_profile(profile, previous, "institution")
    profile["team"] = sanitize_team_members(
        profile.get("team", []), institution.aliases
    )
    profile["evidenceScore"] = evidence_score(profile, "institution")
    status = {
'''
if institution_new not in crawler:
    if institution_old not in crawler:
        raise SystemExit("institution retention marker not found")
    crawler = crawler.replace(institution_old, institution_new, 1)

quality_old = '''    invalid = _invalid_source_urls(companies) + _invalid_source_urls(institutions)
    checks = {
'''
quality_new = '''    invalid = _invalid_source_urls(companies) + _invalid_source_urls(institutions)
    semantic_errors: list[str] = []
    for slug, profile in companies.items():
        products = profile.get("products", [])
        if products != sanitize_product_items(products):
            semantic_errors.append(f"company:{slug}:product-noise")
        team = profile.get("team", [])
        if team != sanitize_team_members(team, (profile.get("name", ""),)):
            semantic_errors.append(f"company:{slug}:team-noise")
    for slug, profile in institutions.items():
        team = profile.get("team", [])
        if team != sanitize_team_members(team, (profile.get("name", ""),)):
            semantic_errors.append(f"institution:{slug}:team-noise")
    checks = {
'''
if quality_new not in crawler:
    if quality_old not in crawler:
        raise SystemExit("quality marker not found")
    crawler = crawler.replace(quality_old, quality_new, 1)

checks_old = '''        "invalidSourceUrls": {
            "actual": len(invalid),
            "required": 0,
            "passed": not invalid,
        },
    }
'''
checks_new = '''        "invalidSourceUrls": {
            "actual": len(invalid),
            "required": 0,
            "passed": not invalid,
        },
        "semanticNoise": {
            "actual": len(semantic_errors),
            "required": 0,
            "passed": not semantic_errors,
        },
    }
'''
if checks_new not in crawler:
    if checks_old not in crawler:
        raise SystemExit("quality checks marker not found")
    crawler = crawler.replace(checks_old, checks_new, 1)

result_old = '''        "invalidSourceUrls": invalid[:30],
        "productiveCompanies": sum(profile.get("status") in {"ok", "partial", "retained"} for profile in companies.values()),
'''
result_new = '''        "invalidSourceUrls": invalid[:30],
        "semanticErrors": semantic_errors[:30],
        "productiveCompanies": sum(profile.get("status") in {"ok", "partial", "retained"} for profile in companies.values()),
'''
if result_new not in crawler:
    if result_old not in crawler:
        raise SystemExit("quality result marker not found")
    crawler = crawler.replace(result_old, result_new, 1)

crawler_path.write_text(crawler, encoding="utf-8")
print("retained venture profiles now use current semantic sanitizers")
