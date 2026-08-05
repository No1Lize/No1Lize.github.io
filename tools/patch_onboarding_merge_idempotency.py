#!/usr/bin/env python3
"""One-time patch making reviewed-company merge processing idempotent."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

onboarding_path = ROOT / "tools" / "onboard_company_candidates.py"
text = onboarding_path.read_text(encoding="utf-8")
old = '''        if status == "merged":
            if not candidate:
                continue
            slug = clean(decision.get("mergedSlug"), 120)
            try:
                add_aliases_to_existing(registry, official_sources, slug, candidate)
            except ValueError as error:
                failed.append({"candidateKey": key, "error": str(error)})
                continue
            decision["onboarding"] = {
                "status": "merged",
                "mode": "merge",
                "profile": normalize_profile({}),
                "evidenceFingerprint": evidence_fingerprint(candidate),
                "requestedAt": decision.get("decidedAt", ""),
                "requestedBy": decision.get("reviewedBy", ""),
                "publishedAt": timestamp,
                "publishedSlug": slug,
                "error": "",
            }
            merged_slugs.append(slug)
            continue
'''
new = '''        if status == "merged":
            if not candidate:
                continue
            slug = clean(decision.get("mergedSlug"), 120)
            existing_onboarding = (
                decision.get("onboarding")
                if isinstance(decision.get("onboarding"), dict)
                else {}
            )
            already_merged = (
                existing_onboarding.get("status") == "merged"
                and clean(existing_onboarding.get("publishedSlug"), 120) == slug
            )
            try:
                aliases_changed = add_aliases_to_existing(
                    registry, official_sources, slug, candidate
                )
            except ValueError as error:
                failed.append({"candidateKey": key, "error": str(error)})
                continue
            if already_merged and not aliases_changed:
                continue
            decision["onboarding"] = {
                "status": "merged",
                "mode": "merge",
                "profile": normalize_profile({}),
                "evidenceFingerprint": evidence_fingerprint(candidate),
                "requestedAt": (
                    clean(existing_onboarding.get("requestedAt"), 80)
                    or decision.get("decidedAt", "")
                ),
                "requestedBy": (
                    clean(existing_onboarding.get("requestedBy"), 120)
                    or decision.get("reviewedBy", "")
                ),
                "publishedAt": (
                    clean(existing_onboarding.get("publishedAt"), 80)
                    or timestamp
                ),
                "publishedSlug": slug,
                "error": "",
            }
            merged_slugs.append(slug)
            continue
'''
if new not in text:
    if old not in text:
        raise SystemExit("merge processing patch target not found")
    onboarding_path.write_text(text.replace(old, new, 1), encoding="utf-8")


test_path = ROOT / "tests" / "test_onboard_company_candidates.py"
tests = test_path.read_text(encoding="utf-8")
method = '''    def test_repeated_merge_processing_is_idempotent(self):
        candidate = self._candidate(name="Sample Brand")
        key = onboarding.decision_key(candidate["decisionKey"])
        registry = {
            "companies": [
                {
                    **self._profile(),
                    "source": {"name": "Sample", "url": "https://example.com/"},
                    "aliases": ["Sample"],
                }
            ]
        }
        sources = {
            "companies": [
                {
                    "slug": "sample",
                    "name": "Sample",
                    "homepage": "https://example.com/",
                    "aliases": ["Sample"],
                }
            ]
        }
        decisions = {
            "decisions": {
                key: {
                    "status": "merged",
                    "note": "这是现有公司的品牌别名。",
                    "mergedSlug": "sample",
                    "decidedAt": "2026-08-05T00:00:00Z",
                    "reviewedBy": "VCIQ",
                }
            }
        }
        first_decisions, first_registry, first_sources, first_report = (
            onboarding.process_onboarding(
                {"candidates": [candidate]},
                decisions,
                registry,
                sources,
                now=datetime(2026, 8, 5, 1, tzinfo=UTC),
            )
        )
        second_decisions, second_registry, second_sources, second_report = (
            onboarding.process_onboarding(
                {"candidates": [candidate]},
                first_decisions,
                first_registry,
                first_sources,
                now=datetime(2026, 8, 5, 2, tzinfo=UTC),
            )
        )
        self.assertEqual(first_report["mergedCount"], 1)
        self.assertEqual(second_report["mergedCount"], 0)
        self.assertEqual(second_decisions, first_decisions)
        self.assertEqual(second_registry, first_registry)
        self.assertEqual(second_sources, first_sources)

'''
marker = '\n\nif __name__ == "__main__":\n'
if marker not in tests:
    raise SystemExit("test insertion point not found")
if "test_repeated_merge_processing_is_idempotent" not in tests:
    test_path.write_text(
        tests.replace(marker, "\n\n" + method + 'if __name__ == "__main__":\n', 1),
        encoding="utf-8",
    )
