#!/usr/bin/env python3
"""Align venture evidence stability and WeChat source tests with current contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
WECHAT = ROOT / "tools" / "wechat_public_sources.py"
WECHAT_TEST = ROOT / "tests" / "test_wechat_public_sources.py"
BRIDGE_TEST = ROOT / "tests" / "test_wechat_registry_bridge.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_venture_stability() -> None:
    replace_once(
        REFINER,
        '''    evidence = [
        profile.get("background", ""),
        profile.get("technology", ""),
        profile.get("researchTechnology", ""),
        *non_capital_articles,
    ]
    problem = _select_required_sentence(
        evidence,
        required_terms=PROBLEM_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    market = _select_required_sentence(
        evidence,
        required_terms=MARKET_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
''',
        '''    stable_evidence = [
        profile.get("background", ""),
        profile.get("technology", ""),
        profile.get("researchTechnology", ""),
        *non_capital_articles,
    ]
    project = (
        profile.get("projectBackground")
        if isinstance(profile.get("projectBackground"), dict)
        else {}
    )
    problem = _select_required_sentence(
        [project.get("problemSolved", ""), *stable_evidence],
        required_aliases=company.aliases,
        required_terms=PROBLEM_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    market = _select_required_sentence(
        [project.get("marketOpportunity", ""), *stable_evidence],
        required_aliases=company.aliases,
        required_terms=MARKET_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
''',
        "field-specific stable project evidence",
    )


def patch_wechat_contracts() -> None:
    replace_once(
        WECHAT,
        '''    return sources


class WeChatPageParser(HTMLParser):
''',
        '''    return sources


# Stable reference used by unit tests and callers that need the account-agnostic
# generator even after the optional registry bridge installs its runtime wrapper.
base_generated_wechat_sources = generated_wechat_sources


class WeChatPageParser(HTMLParser):
''',
        "stable base WeChat generator alias",
    )
    replace_once(
        WECHAT_TEST,
        '''        sources = wechat.generated_wechat_sources(tracks, object())
''',
        '''        sources = wechat.base_generated_wechat_sources(tracks, object())
''',
        "base WeChat generator test isolation",
    )
    replace_once(
        BRIDGE_TEST,
        '''        self.assertTrue(all(item.get("expectedAccounts") for item in sources))
''',
        '''        configured = [item for item in sources if not item.get("genericDiscovery")]
        generic = [item for item in sources if item.get("genericDiscovery")]
        self.assertTrue(configured)
        self.assertTrue(all(item.get("expectedAccounts") for item in configured))
        self.assertEqual(len(generic), 1)
        self.assertFalse(generic[0].get("expectedAccounts"))
''',
        "generic and configured WeChat source contract",
    )


def main() -> None:
    patch_venture_stability()
    patch_wechat_contracts()


if __name__ == "__main__":
    main()
