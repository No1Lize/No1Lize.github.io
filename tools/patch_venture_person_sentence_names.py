#!/usr/bin/env python3
"""Reject editorial product labels and sentence-like person names."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


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
        TARGET,
        '''PRODUCT_EDITORIAL_RE = re.compile(
    r"\\b(?:press release|latest news|newsroom|things to know|crew undocks|"
    r"journey home|announces?|launches?|introduces?|partnership|collaboration)\\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|大会|峰会|访谈|观点|生态合作)",
    re.IGNORECASE,
)
PERSON_CJK_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
''',
        '''PRODUCT_EDITORIAL_RE = re.compile(
    r"\\b(?:press release|latest news|newsroom|things to know|crew undocks|"
    r"journey home|announces?|launches?|introduces?|partnership|collaboration|"
    r"read more|learn more|start chat|free chat|try now)\\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|大会|峰会|"
    r"访谈|观点|生态合作|开始对话|免费对话|立即体验|体验全新|交付速度|再提升)",
    re.IGNORECASE,
)
PRODUCT_URL_RE = re.compile(
    r"^(?:https?:?|www\\.)|(?:\\.(?:com|cn|ai|io|org|net)(?:/|$))|"
    r"^(?:qnimgs?|imgs?|images?|cdn)$",
    re.IGNORECASE,
)
PERSON_CJK_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
''',
        "editorial product and URL guards",
    )
    replace_once(
        TARGET,
        '''    "chief", "officer", "president", "executive",
''',
        '''    "chief", "officer", "president", "executive",
    "the", "next", "black", "history", "awards", "solutions", "platform",
    "overview", "providers", "program", "programs", "events", "resources",
}
PERSON_ORGANIZATION_NAMES = {
    "moses singer",
    "sun microsystems",
''',
        "person navigation and organization tokens",
    )
    replace_once(
        TARGET,
        '''        or PRODUCT_EDITORIAL_RE.search(item)
        or len(compact) < 2
''',
        '''        or PRODUCT_EDITORIAL_RE.search(item)
        or PRODUCT_URL_RE.search(item)
        or len(compact) < 2
''',
        "product URL validation",
    )
    replace_once(
        TARGET,
        '''    if not name or any(name.endswith(suffix) for suffix in PERSON_ORG_SUFFIXES):
        return False
''',
        '''    if (
        not name
        or name.casefold().strip(" .") in PERSON_ORGANIZATION_NAMES
        or any(name.endswith(suffix) for suffix in PERSON_ORG_SUFFIXES)
    ):
        return False
''',
        "known organization-name rejection",
    )
    replace_once(
        TARGET,
        '''    if lowered & PERSON_NOISE_TOKENS:
        return False
    if not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[0]) or not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[-1]):
''',
        '''    if lowered & PERSON_NOISE_TOKENS:
        return False
    if any("." in token and len(token.strip(".")) > 1 for token in tokens):
        return False
    if not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[0]) or not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[-1]):
''',
        "sentence-fragment punctuation guard",
    )
    replace_once(
        TESTS,
        '''                    "products": [
                        "Anthropic",
                        "英特尔深化智能生态合作",
                        "Claude Platform",
                    ],
''',
        '''                    "products": [
                        "Anthropic",
                        "英特尔深化智能生态合作",
                        "开始对话",
                        "https:",
                        "www.example.com",
                        "Claude Platform",
                    ],
''',
        "editorial product regression fixtures",
    )
    replace_once(
        TESTS,
        '''                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Megan Holston-Alexander", "role": "Partner"},
''',
        '''                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Chris Lyons. The Next", "role": "Partner"},
                        {"name": "Chris Lyons. Black History", "role": "Partner"},
                        {"name": "ML Angela Yeung Awards", "role": "CTO"},
                        {"name": "Solutions Platform Overview AI", "role": "Partner"},
                        {"name": "Sun Microsystems", "role": "Founder"},
                        {"name": "Megan Holston-Alexander", "role": "Partner"},
''',
        "sentence-like person regression fixtures",
    )
    replace_once(
        TESTS,
        '''                        {"name": "General Partner", "role": "Partner"},
                        {"name": "Jane Doe", "role": "Partner"},
''',
        '''                        {"name": "General Partner", "role": "Partner"},
                        {"name": "Moses Singer", "role": "CEO"},
                        {"name": "Jane Doe", "role": "Partner"},
''',
        "organization-name regression fixture",
    )
    replace_once(
        TESTS,
        '''        self.assertEqual(diagnostics["removedProducts"], 2)
        self.assertEqual(diagnostics["removedTeamMembers"], 2)
''',
        '''        self.assertEqual(diagnostics["removedProducts"], 5)
        self.assertEqual(diagnostics["removedTeamMembers"], 8)
''',
        "entity removal regression counts",
    )


if __name__ == "__main__":
    main()
