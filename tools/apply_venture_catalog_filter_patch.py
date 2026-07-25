#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/crawl_venture_profiles.py")
text = path.read_text(encoding="utf-8")
marker = '    ordered_status = sorted(statuses.values(), key=lambda item: (item.get("kind", ""), item.get("slug", "")))\n'
replacement = '''    # Remove profiles and statuses for entities that no longer exist in the
    # production catalog. Partial refreshes may retain current catalog rows,
    # but deleted or renamed entities must not pollute coverage.
    company_keys = {item.slug for item in company_specs}
    institution_keys = {item.slug for item in institution_specs}
    company_profiles = {
        profile_slug: profile
        for profile_slug, profile in company_profiles.items()
        if profile_slug in company_keys
    }
    institution_profiles = {
        profile_slug: profile
        for profile_slug, profile in institution_profiles.items()
        if profile_slug in institution_keys
    }
    statuses = {
        key: status
        for key, status in statuses.items()
        if (key[0] == "company" and key[1] in company_keys)
        or (key[0] == "institution" and key[1] in institution_keys)
    }

    ordered_status = sorted(statuses.values(), key=lambda item: (item.get("kind", ""), item.get("slug", "")))
'''

if replacement in text:
    print("catalog filter already present")
elif marker not in text:
    raise SystemExit("target marker not found")
else:
    path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
    print("catalog filter inserted")
