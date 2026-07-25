#!/usr/bin/env python3
"""Tighten venture article attribution to structured entity fields only."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENRICHER = ROOT / "tools" / "enrich_venture_profiles.py"
TESTS = ROOT / "tests" / "test_venture_profile_enrichment.py"


def replace_function(path: Path, name: str, next_name: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if block in text:
        print(f"{name}: already applied")
        return
    start = text.find(f"def {name}(")
    end = text.find(f"\n\ndef {next_name}(", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{name}: function boundary not found")
    path.write_text(text[:start] + block.rstrip() + text[end:], encoding="utf-8")
    print(f"{name}: replaced")


def patch_enricher() -> None:
    company_block = '''def _entity_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\\u3400-\\u9fff]+",
        "",
        clean_text(value, 160).casefold(),
    )


def _company_articles(
    slug: str,
    company: CatalogCompany,
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in company.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        article_slug = clean_text(article.get("companySlug"), 100)
        company_name = clean_text(article.get("company"), 120)

        # Structured attribution is authoritative. A reference to OpenAI,
        # Anthropic or an investor inside another company's article must not
        # reassign that article to the mentioned entity.
        if article_slug:
            if article_slug == slug:
                result.append(article)
            continue
        if company_name:
            if _entity_key(company_name) in alias_keys:
                result.append(article)
            continue

        # Precision is preferred over recall when legacy rows lack a primary
        # entity. Such rows remain in the news feed but do not alter profiles.
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )'''
    replace_function(ENRICHER, "_company_articles", "_institution_articles", company_block)

    institution_block = '''def _institution_articles(
    institution: CatalogInstitution,
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in institution.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        named_keys = {
            _entity_key(item)
            for item in _article_institutions(article)
            if _entity_key(item)
        }
        if alias_keys & named_keys:
            result.append(article)
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )'''
    replace_function(ENRICHER, "_institution_articles", "_capital_event_from_article", institution_block)


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = '''                {
                    "id": "openai-product",
'''
    false_article = '''                {
                    "id": "infinity-funding",
                    "company": "Infinity",
                    "companySlug": "infinity",
                    "title": "Infinity raises a new round",
                    "summary": "Infinity raised funding with researchers from OpenAI and Anthropic; a Sequoia Capital observer commented on the market.",
                    "type": "融资",
                    "sector": "AI / AGI",
                    "publishedAt": "2026-07-20",
                    "institutions": ["Touring Capital"],
                    "source": {"url": "https://example.com/infinity-funding"},
                },
'''
    if '"id": "infinity-funding"' not in text:
        index = text.find(marker)
        if index < 0:
            raise SystemExit("false-attribution fixture insertion marker not found")
        text = text[:index] + false_article + text[index:]

    assertion_marker = '''        self.assertEqual(company["capitalSummary"]["eventCount"], 1)
'''
    extra_assertion = '''        self.assertEqual(company["capitalSummary"]["eventCount"], 1)
        self.assertNotIn("Infinity", company["projectBackground"]["summary"])
        self.assertNotIn("Anthropic", company["technology"])
'''
    if 'self.assertNotIn("Infinity", company["projectBackground"]["summary"])' not in text:
        if assertion_marker not in text:
            raise SystemExit("company attribution assertion marker not found")
        text = text.replace(assertion_marker, extra_assertion, 1)

    institution_marker = '''        self.assertEqual(institution["recentYearSummary"]["investmentCount"], 1)
'''
    institution_assertion = '''        self.assertEqual(institution["recentYearSummary"]["investmentCount"], 1)
        self.assertEqual(institution["recentYearSummary"]["companies"], ["OpenAI"])
'''
    if text.count('self.assertEqual(institution["recentYearSummary"]["companies"], ["OpenAI"])') < 2:
        # The original test already has one companies assertion. Add a second
        # explicit check beside the count only when the fixture was expanded.
        if institution_marker not in text:
            raise SystemExit("institution attribution assertion marker not found")
        text = text.replace(institution_marker, institution_assertion, 1)

    TESTS.write_text(text, encoding="utf-8")
    print("strict attribution regressions: applied")


def main() -> int:
    patch_enricher()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
