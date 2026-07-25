#!/usr/bin/env python3
"""Patch terminal venture semantics for editorial products and false team names."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"{label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source block, found {count}")
    print(f"{label}: applied")
    return text.replace(old, new, 1)


def patch_semantics() -> None:
    text = TARGET.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\\n]+|(?<=\\.)\\s+(?=[A-Z\\u3400-\\u9fff])")\n',
        '''CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\\n]+|(?<=\\.)\\s+(?=[A-Z\\u3400-\\u9fff])")
PRODUCT_EDITORIAL_RE = re.compile(
    r"\\b(?:press release|latest news|newsroom|things to know|crew undocks|"
    r"journey home|announces?|launches?|introduces?|partnership|collaboration)\\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|大会|峰会|访谈|观点|生态合作)",
    re.IGNORECASE,
)
PERSON_CJK_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
PERSON_LATIN_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’.-]*$")
PERSON_PARTICLES = {"de", "del", "da", "di", "van", "von", "la", "le"}
PERSON_NOISE_TOKENS = {
    "spotlight", "hear", "read", "view", "more", "team", "leadership",
    "newsroom", "profile", "people", "about", "featured", "general",
    "partner", "managing", "principal", "director", "founder", "cofounder",
    "chief", "officer", "president", "executive",
}
PERSON_ORG_SUFFIXES = (
    "团队", "部门", "研究院", "实验室", "资本", "基金", "公司", "集团",
    "委员会", "中心", "办公室", "业务部", "事业部",
)
''',
        "semantic label constants",
    )

    text = replace_once(
        text,
        '''def _valid_product(value: Any) -> bool:
    item = clean_text(value, 200).strip()
    if not item or YEAR_ONLY_RE.fullmatch(item) or NUMERIC_ONLY_RE.fullmatch(item):
        return False
    return len(_compact(item)) >= 2
''',
        '''def _valid_product(value: Any, aliases: Sequence[str] = ()) -> bool:
    item = clean_text(value, 200).strip()
    compact = _compact(item)
    if (
        not item
        or YEAR_ONLY_RE.fullmatch(item)
        or NUMERIC_ONLY_RE.fullmatch(item)
        or PRODUCT_EDITORIAL_RE.search(item)
        or len(compact) < 2
    ):
        return False
    alias_compacts = {_compact(alias) for alias in aliases if _compact(alias)}
    return compact not in alias_compacts


def _valid_person_name(value: Any) -> bool:
    name = clean_text(value, 120).strip(" ,，:：;；-|｜")
    if not name or any(name.endswith(suffix) for suffix in PERSON_ORG_SUFFIXES):
        return False
    if PERSON_CJK_RE.fullmatch(name):
        return True
    tokens = [token for token in name.split() if token]
    if not 2 <= len(tokens) <= 6:
        return False
    lowered = {token.casefold().strip(".,") for token in tokens}
    if lowered & PERSON_NOISE_TOKENS:
        return False
    if not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[0]) or not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[-1]):
        return False
    return all(
        PERSON_LATIN_TOKEN_RE.fullmatch(token) or token.casefold() in PERSON_PARTICLES
        for token in tokens[1:-1]
    )
''',
        "product and person validators",
    )

    text = replace_once(
        text,
        '''        name = clean_text(row.get("name"), 120)
        summary = clean_text(row.get("summary"), 420)
''',
        '''        name = clean_text(row.get("name"), 120)
        if not _valid_person_name(name):
            continue
        summary = clean_text(row.get("summary"), 420)
''',
        "team member validation",
    )

    text = replace_once(
        text,
        '''        "removedCapitalMarkets": 0,
        "clearedTeamSummaries": 0,
''',
        '''        "removedCapitalMarkets": 0,
        "removedTeamMembers": 0,
        "clearedTeamSummaries": 0,
''',
        "team removal diagnostics",
    )

    text = replace_once(
        text,
        '''            for item in original_products
            if _valid_product(item)
''',
        '''            for item in original_products
            if _valid_product(item, aliases)
''',
        "entity-aware product validation",
    )

    text = replace_once(
        text,
        '''        profile["team"] = _sanitize_team(profile.get("team", []))
        for old, new in zip(team_before, profile["team"]):
''',
        '''        profile["team"] = _sanitize_team(profile.get("team", []))
        diagnostics["removedTeamMembers"] += max(
            0,
            (len(team_before) if isinstance(team_before, list) else 0)
            - len(profile["team"]),
        )
        for old, new in zip(team_before, profile["team"]):
''',
        "company team removal count",
    )

    text = replace_once(
        text,
        '''        profile["team"] = _sanitize_team(profile.get("team", []))
        profile["evidenceScore"] = evidence_score(profile, "institution")
''',
        '''        institution_team = profile.get("team", [])
        profile["team"] = _sanitize_team(institution_team)
        diagnostics["removedTeamMembers"] += max(
            0,
            (len(institution_team) if isinstance(institution_team, list) else 0)
            - len(profile["team"]),
        )
        profile["evidenceScore"] = evidence_score(profile, "institution")
''',
        "institution team removal count",
    )
    TARGET.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = '''    def test_trims_investor_relations_page_chrome(self) -> None:
'''
    addition = '''    def test_rejects_editorial_products_and_navigation_team_names(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude Platform.",
                    "products": [
                        "Anthropic",
                        "英特尔深化智能生态合作",
                        "Claude Platform",
                    ],
                    "team": [
                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Megan Holston-Alexander", "role": "Partner"},
                    ],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {
                "fund": {
                    "slug": "fund",
                    "name": "Example Capital",
                    "overview": "Example Capital is a venture firm.",
                    "strategy": "Example Capital invests in AI.",
                    "team": [
                        {"name": "General Partner", "role": "Partner"},
                        {"name": "Jane Doe", "role": "Partner"},
                    ],
                    "sources": [],
                }
            },
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Claude Platform"],
        )
        self.assertEqual(
            [row["name"] for row in cleaned["companies"]["anthropic"]["team"]],
            ["Megan Holston-Alexander"],
        )
        self.assertEqual(
            [row["name"] for row in cleaned["institutions"]["fund"]["team"]],
            ["Jane Doe"],
        )
        self.assertEqual(diagnostics["removedProducts"], 2)
        self.assertEqual(diagnostics["removedTeamMembers"], 2)

'''
    if "def test_rejects_editorial_products_and_navigation_team_names" not in text:
        if marker not in text:
            raise SystemExit("entity semantic test insertion marker not found")
        text = text.replace(marker, addition + marker, 1)
    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_semantics()
    patch_tests()


if __name__ == "__main__":
    main()
