import unittest
from datetime import UTC, datetime

from tools import onboard_company_candidates as onboarding


class CompanyCandidateOnboardingTests(unittest.TestCase):
    def _candidate(self, *, name="Sample", event_types=None):
        return {
            "id": "candidate-sample",
            "decisionKey": name.casefold(),
            "name": name,
            "aliases": [name],
            "region": "美国",
            "sector": "AI / AGI",
            "score": 70,
            "status": "accepted",
            "articleCount": 3,
            "sourceCount": 2,
            "sourceArticleIds": ["a2", "a1"],
            "sourceUrls": ["https://example.com/news", "https://example.com/about"],
            "eventTypes": event_types or ["产品发布"],
        }

    def _profile(self):
        return {
            "slug": "sample",
            "name": "Sample",
            "englishName": "Sample",
            "region": "美国",
            "sector": "AI / AGI",
            "stage": "成长期",
            "status": "运营中",
            "founded": "2024",
            "headquarters": "California",
            "summary": "为企业客户提供可审计的人工智能软件和数据基础设施服务。",
            "product": "企业人工智能平台与数据工具。",
            "homepage": "https://example.com/",
            "newsUrls": ["https://example.com/news"],
            "aliases": ["Sample Inc."],
            "confidence": 0.93,
        }

    def test_requested_candidate_is_published_to_registry_and_sources(self):
        candidate = self._candidate()
        key = onboarding.decision_key(candidate["decisionKey"])
        decisions = {
            "schemaVersion": 1,
            "decisions": {
                key: {
                    "status": "accepted",
                    "note": "证据充分，建立正式档案。",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-05T00:00:00Z",
                    "reviewedBy": "VCIQ",
                    "onboarding": {
                        "status": "requested",
                        "mode": "create",
                        "profile": self._profile(),
                        "evidenceFingerprint": onboarding.evidence_fingerprint(candidate),
                        "requestedAt": "2026-08-05T00:10:00Z",
                        "requestedBy": "VCIQ",
                    },
                }
            },
        }
        next_decisions, registry, sources, report = onboarding.process_onboarding(
            {"candidates": [candidate]},
            decisions,
            {"schemaVersion": 1, "companies": []},
            {"schemaVersion": 1, "companies": []},
            now=datetime(2026, 8, 5, 1, tzinfo=UTC),
        )
        self.assertEqual(report["publishedSlugs"], ["sample"])
        self.assertEqual(registry["companies"][0]["slug"], "sample")
        self.assertEqual(sources["companies"][0]["homepage"], "https://example.com/")
        decision = next_decisions["decisions"][key]
        self.assertEqual(decision["status"], "published")
        self.assertEqual(decision["mergedSlug"], "sample")
        self.assertEqual(decision["onboarding"]["status"], "published")

    def test_stale_evidence_blocks_publication(self):
        candidate = self._candidate()
        key = onboarding.decision_key(candidate["decisionKey"])
        decisions = {
            "decisions": {
                key: {
                    "status": "accepted",
                    "note": "审核通过",
                    "reviewedBy": "VCIQ",
                    "onboarding": {
                        "status": "requested",
                        "profile": self._profile(),
                        "evidenceFingerprint": "stale",
                    },
                }
            }
        }
        next_decisions, registry, _, report = onboarding.process_onboarding(
            {"candidates": [candidate]},
            decisions,
            {"companies": []},
            {"companies": []},
        )
        self.assertEqual(registry["companies"], [])
        self.assertEqual(report["failedCount"], 1)
        self.assertEqual(next_decisions["decisions"][key]["onboarding"]["status"], "failed")

    def test_person_only_candidate_requires_company_identity(self):
        candidate = self._candidate(name="某位创始人", event_types=["人物观点"])
        profile = self._profile()
        profile["name"] = "某位创始人"
        errors = onboarding.validate_profile(profile, candidate)
        self.assertIn(
            "person-only candidate must be mapped to a canonical company entity",
            errors,
        )

    def test_merge_adds_candidate_alias_without_new_company(self):
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
        decisions = {
            "decisions": {
                key: {
                    "status": "merged",
                    "note": "这是现有公司的品牌别名。",
                    "mergedSlug": "sample",
                    "reviewedBy": "VCIQ",
                }
            }
        }
        _, next_registry, _, report = onboarding.process_onboarding(
            {"candidates": [candidate]},
            decisions,
            registry,
            {
                "companies": [
                    {
                        "slug": "sample",
                        "name": "Sample",
                        "homepage": "https://example.com/",
                        "aliases": ["Sample"],
                    }
                ]
            },
        )
        self.assertEqual(report["mergedSlugs"], ["sample"])
        self.assertIn("Sample Brand", next_registry["companies"][0]["aliases"])
        self.assertEqual(len(next_registry["companies"]), 1)

    def test_seed_shopify_only_targets_accepted_candidate(self):
        candidate = self._candidate(name="Shopify")
        key = onboarding.decision_key("shopify")
        decisions = {
            "schemaVersion": 1,
            "decisions": {
                key: {
                    "status": "accepted",
                    "note": "符合条件",
                    "reviewedBy": "VCIQ",
                }
            },
        }
        changed = onboarding.seed_shopify_request(
            decisions,
            {key: candidate},
            now="2026-08-05T00:00:00+00:00",
        )
        self.assertTrue(changed)
        request = decisions["decisions"][key]["onboarding"]
        self.assertEqual(request["status"], "requested")
        self.assertEqual(request["profile"]["slug"], "shopify")
        self.assertEqual(request["evidenceFingerprint"], onboarding.evidence_fingerprint(candidate))


if __name__ == "__main__":
    unittest.main()
