#!/usr/bin/env python3
"""Preserve short catalog and technology narratives across terminal gates."""

from __future__ import annotations

from pathlib import Path


SEMANTICS = Path(__file__).with_name("enforce_venture_entity_semantics.py")
FINALIZER = Path(__file__).with_name("finalize_venture_profiles.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        SEMANTICS,
        '''        if not background and spec:
            background = sanitize_narrative(spec.summary, limit=900)
''',
        '''        if not background and spec:
            background = (
                sanitize_narrative(spec.summary, limit=900)
                or clean_text(spec.summary, 900)
            )
''',
        "semantic short-summary fallback",
    )
    replace_once(
        FINALIZER,
        '''        profile["background"] = sanitize_narrative(profile.get("background", ""), limit=900)
''',
        '''        profile["background"] = sanitize_narrative(
            profile.get("background", ""),
            fallback=spec.summary if spec else "",
            limit=900,
        )
''',
        "structural background fallback",
    )
    replace_once(
        FINALIZER,
        '''        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
        profile["researchTechnology"] = sanitize_narrative(
            profile.get("researchTechnology", ""),
            fallback=profile.get("technology", ""),
            limit=900,
        )
''',
        '''        technology_raw = clean_text(profile.get("technology", ""), 900)
        profile["technology"] = sanitize_narrative(
            technology_raw,
            fallback=technology_raw,
            limit=900,
        )
        research_technology_raw = clean_text(
            profile.get("researchTechnology", ""),
            900,
        )
        profile["researchTechnology"] = sanitize_narrative(
            research_technology_raw,
            fallback=research_technology_raw or profile["technology"],
            limit=900,
        )
''',
        "structural short-technology fallback",
    )
    replace_once(
        FINALIZER,
        '''            project["summary"] = sanitize_narrative(project.get("summary", ""), limit=900)
''',
        '''            project["summary"] = sanitize_narrative(
                project.get("summary", ""),
                fallback=profile["background"],
                limit=900,
            )
''',
        "structural project-summary fallback",
    )


if __name__ == "__main__":
    main()
