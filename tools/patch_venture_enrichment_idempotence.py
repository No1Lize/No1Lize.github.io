#!/usr/bin/env python3
"""One-time patch for stable company project-background enrichment."""

from pathlib import Path

PATH = Path(__file__).with_name("enrich_venture_profiles.py")

OLD = '''    raw_background = profile.get("background", "")
    summary = _select_sentences(
        [raw_background, *article_values],
        aliases,
        (
            "founded",
            "mission",
            "company",
            "成立",
            "使命",
            "致力于",
            "总部",
            "研发",
        ),
        maximum=3,
        limit=760,
    )
    if not summary or _navigation_heavy(raw_background):
        summary = clean_text(company.summary, 760) or summary
'''

NEW = '''    raw_background = profile.get("background", "")
    existing_project = (
        profile.get("projectBackground")
        if isinstance(profile.get("projectBackground"), dict)
        else {}
    )
    stable_summary = (
        clean_text(existing_project.get("summary"), 760)
        or clean_text(company.summary, 760)
    )
    summary = _select_sentences(
        [raw_background, *article_values],
        aliases,
        (
            "founded",
            "mission",
            "company",
            "成立",
            "使命",
            "致力于",
            "总部",
            "研发",
        ),
        maximum=3,
        limit=760,
    )
    raw_key = re.sub(
        r"[^A-Za-z0-9\\u3400-\\u9fff]+", "", clean_text(raw_background, 760)
    ).casefold()
    stable_key = re.sub(
        r"[^A-Za-z0-9\\u3400-\\u9fff]+", "", stable_summary
    ).casefold()
    if (
        not summary
        or _navigation_heavy(raw_background)
        or (stable_key and raw_key == stable_key)
    ):
        summary = stable_summary or summary
'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"expected one project-background block, found {count}")
    PATH.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Patched stable project-background enrichment.")


if __name__ == "__main__":
    main()
