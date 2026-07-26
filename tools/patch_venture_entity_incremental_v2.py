#!/usr/bin/env python3
"""Incrementally harden venture entity semantics against remaining page noise.

This patch targets the already-deployed first-generation entity validators. It
adds URL/CTA/file/editorial product rejection, navigation and organization-name
rejection for team members, and deterministic technology reconstruction when
prose still contains labels removed from the product list.
"""

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
        raise SystemExit(f"{label}: expected one source block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_semantics() -> None:
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
    r"read more|learn more|start chat|free chat|try now|new paper|explores?|"
    r"nominates?|applauded|positive topline|developed using|for the treatment|"
    r"enabling rapid|development with)\\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|大会|峰会|"
    r"访谈|观点|生态合作|开始对话|免费对话|立即体验|体验全新|交付速度|再提升)",
    re.IGNORECASE,
)
PRODUCT_URL_RE = re.compile(
    r"(?:https?://|^https?:$|^www\\.)|\\b(?:qnimgs?|imgs?|images?|cdn)\\b",
    re.IGNORECASE,
)
PRODUCT_FILE_RE = re.compile(
    r"\\.(?:png|jpe?g|webp|svg|gif|pdf)(?:[?#].*)?$",
    re.IGNORECASE,
)
PRODUCT_SENTENCE_RE = re.compile(
    r"^(?:the first\\b|new paper\\b|development with\\b)|"
    r"\\b(?:nominates?|applauded|positive topline|for the treatment|"
    r"developed using|enabling rapid)\\b",
    re.IGNORECASE,
)
PRODUCT_EXACT_NOISE = {
    "cost-effective drug discovery",
    "drug discovery",
    "nach01",
}
PERSON_CJK_RE = re.compile(r"^[\\u3400-\\u9fff·]{2,8}$")
''',
        "editorial URL file and sentence product guards",
    )
    replace_once(
        TARGET,
        '''PERSON_NOISE_TOKENS = {
    "spotlight", "hear", "read", "view", "more", "team", "leadership",
    "newsroom", "profile", "people", "about", "featured", "general",
    "partner", "managing", "principal", "director", "founder", "cofounder",
    "chief", "officer", "president", "executive",
    "the", "next", "black", "history",
}
PERSON_ORG_SUFFIXES = (
''',
        '''PERSON_NOISE_TOKENS = {
    "spotlight", "hear", "read", "view", "more", "team", "leadership",
    "newsroom", "profile", "people", "about", "featured", "general",
    "partner", "managing", "principal", "director", "founder", "cofounder",
    "chief", "officer", "president", "executive",
    "the", "next", "black", "history", "awards", "solutions", "platform",
    "overview", "providers", "program", "programs", "events", "resources",
}
PERSON_ORGANIZATION_NAMES = {
    "moses singer",
    "sun microsystems",
}
PERSON_ORG_SUFFIXES = (
''',
        "person navigation and organization guards",
    )
    replace_once(
        TARGET,
        '''        or PRODUCT_EDITORIAL_RE.search(item)
        or len(compact) < 2
''',
        '''        or PRODUCT_EDITORIAL_RE.search(item)
        or PRODUCT_URL_RE.search(item)
        or PRODUCT_FILE_RE.search(item)
        or PRODUCT_SENTENCE_RE.search(item)
        or item.casefold().strip(" .") in PRODUCT_EXACT_NOISE
        or len(compact) < 2
''',
        "URL file and sentence product validation",
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
        "organization-name validation",
    )
    replace_once(
        TARGET,
        '''        technology = _relevant_clauses(
            profile.get("technology", ""), aliases, products, limit=900
        )
        if not technology and products:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
''',
        '''        raw_technology = clean_text(profile.get("technology", ""), 1400)
        technology = _relevant_clauses(
            raw_technology, aliases, products, limit=900
        )
        if products and (
            not technology
            or PRODUCT_EDITORIAL_RE.search(raw_technology)
            or PRODUCT_URL_RE.search(raw_technology)
            or PRODUCT_FILE_RE.search(raw_technology)
            or PRODUCT_SENTENCE_RE.search(raw_technology)
        ):
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
''',
        "noisy technology reconstruction",
    )


def patch_tests() -> None:
    replace_once(
        TESTS,
        '''                    "technology": "Anthropic develops Claude Platform.",
                    "products": [
                        "Anthropic",
                        "英特尔深化智能生态合作",
                        "Claude Platform",
                    ],
''',
        '''                    "technology": "核心技术与产品包括Pharma.AI 平台、Claude Platform、https:、A15D1080.png、New paper explores a model。",
                    "products": [
                        "Anthropic",
                        "英特尔深化智能生态合作",
                        "开始对话",
                        "https:",
                        "www.example.com",
                        "A15D1080.png",
                        "New paper explores Insilico Medicine's generative AI platform Chemistry42",
                        "Cost-Effective Drug Discovery",
                        "Nach01",
                        "Pharma.AI 平台",
                        "Claude Platform",
                    ],
''',
        "editorial file product and technology fixtures",
    )
    replace_once(
        TESTS,
        '''                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Chris Lyons. The Next", "role": "Partner"},
                        {"name": "Chris Lyons. Black History", "role": "Partner"},
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
        "editorial person fixtures",
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
        "organization-name fixture",
    )
    replace_once(
        TESTS,
        '''        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Claude Platform"],
        )
''',
        '''        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Pharma.AI 平台", "Claude Platform"],
        )
        self.assertEqual(
            cleaned["companies"]["anthropic"]["technology"],
            "核心技术与产品包括Pharma.AI 平台、Claude Platform。",
        )
''',
        "clean product and technology assertion",
    )
    replace_once(
        TESTS,
        '''        self.assertEqual(diagnostics["removedProducts"], 2)
        self.assertEqual(diagnostics["removedTeamMembers"], 4)
''',
        '''        self.assertEqual(diagnostics["removedProducts"], 9)
        self.assertEqual(diagnostics["removedTeamMembers"], 8)
''',
        "entity removal counts",
    )


def main() -> None:
    patch_semantics()
    patch_tests()


if __name__ == "__main__":
    main()
