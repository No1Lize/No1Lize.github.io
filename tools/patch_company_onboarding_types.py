#!/usr/bin/env python3
"""One-time widening of region metadata for registry-defined global companies."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: patch target not found")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "lib/favorites.ts",
    '  region?: "中国" | "美国" | "全球";',
    "  region?: string;",
)
replace_once(
    "lib/favorites.ts",
    '''  const region =
    raw.region === "中国" || raw.region === "美国" || raw.region === "全球"
      ? raw.region
      : undefined;''',
    '''  const region = cleanText(raw.region, 80) || undefined;''',
)
replace_once(
    "lib/tracking-recommendations.ts",
    '    region: "中国" | "美国" | "全球";',
    "    region: string;",
)

component = ROOT / "components" / "tracking-company-onboarding.tsx"
text = component.read_text(encoding="utf-8")
text = "\n".join(
    line for line in text.splitlines() if "setUsername(" not in line
) + "\n"
component.write_text(text, encoding="utf-8")
