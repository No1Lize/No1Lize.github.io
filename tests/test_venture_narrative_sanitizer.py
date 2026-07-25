from __future__ import annotations

import copy
import unittest

from tools import sanitize_venture_narratives as sanitizer


class VentureNarrativeSanitizerTests(unittest.TestCase):
    def test_removes_anthropic_navigation_tail(self) -> None:
        value = (
            "Anthropic is an AI safety and research company with a mission of ensuring "
            "the world safely makes the transition through transformative AI. "
            "Anthropic builds reliable, interpretable, and steerable AI systems. "
            "Company \\ Anthropic Research Policy Commitments Learn News Making AI systems "
            "you can rely on Anthropic is an AI safety and research company."
        )
        cleaned = sanitizer.sanitize_narrative(value)
        self.assertIn("transformative AI", cleaned)
        self.assertIn("steerable AI systems", cleaned)
        self.assertNotIn("Policy Commitments Learn News", cleaned)

    def test_removes_long_product_navigation_run(self) -> None:
        value = (
            "采用镁合金、钛合金与TPU柔性材料，打造55KG轻量化机身；"
            "双电池冗余设计支持快速热插拔换电，综合续航可达10小时；"
            "产品资料与下载 数据服务 解决方案 新闻资讯 加入我们 联系我们 "
            "智元远征 远征A3 远征A2旗舰版 灵犀X2 精灵G1。"
        )
        cleaned = sanitizer.sanitize_narrative(value)
        self.assertIn("55KG轻量化机身", cleaned)
        self.assertIn("综合续航可达10小时", cleaned)
        self.assertNotIn("产品资料与下载", cleaned)
        self.assertNotIn("新闻资讯", cleaned)

    def test_trims_contact_address_and_date_tail(self) -> None:
        value = (
            "We work with urgency and focus on the work that will accelerate our "
            "progress towards our mission and strengthen our company. "
            "1654 Smallman Street Pittsburgh, PA 15222 Toll-Free: (888) 583-9506 "
            "Investor Relations Email Transfer Agent Equiniti Trust Company, LLC. "
            "Featured July 22, 2026 August 7, 2025 May 1, 2025 Locations Our Company."
        )
        cleaned = sanitizer.sanitize_narrative(value)
        self.assertIn("accelerate our progress towards our mission", cleaned)
        self.assertNotIn("1654 Smallman Street", cleaned)
        self.assertNotIn("Investor Relations", cleaned)
        self.assertNotIn("July 22, 2026", cleaned)

    def test_removes_headline_fragment_but_keeps_technology_claims(self) -> None:
        value = (
            "Consumers’ Pockets Annually by 2035 :: Aurora Innovation, Inc. "
            "We are building a technology and a company to serve all people and all communities. "
            "We are committed to safely developing and deploying transformational self-driving technology."
        )
        cleaned = sanitizer.sanitize_narrative(value)
        self.assertNotIn("Consumers’ Pockets", cleaned)
        self.assertIn("serve all people and all communities", cleaned)
        self.assertIn("transformational self-driving technology", cleaned)

    def test_snapshot_sanitation_is_idempotent(self) -> None:
        payload = {
            "companies": {
                "example": {
                    "background": "Example builds reliable systems. Company Products News Careers Contact.",
                    "technology": "A verified technical platform supports deployment.",
                }
            },
            "institutions": {
                "fund": {
                    "overview": "Example Capital is an early-stage investment firm.",
                    "strategy": "Portfolio Companies Investments News Insights More.",
                }
            },
            "qualityGate": {
                "passed": True,
                "checks": {
                    "companyCoverage": {"actual": 1, "required": 1, "passed": True}
                },
            },
        }
        cleaned, changed = sanitizer.sanitize_snapshot_payload(copy.deepcopy(payload))
        self.assertGreaterEqual(changed, 2)
        self.assertEqual(cleaned["institutions"]["fund"]["strategy"], "")
        self.assertTrue(cleaned["qualityGate"]["checks"]["narrativeNoise"]["passed"])
        second, changed_again = sanitizer.sanitize_snapshot_payload(cleaned)
        self.assertEqual(second, cleaned)
        self.assertEqual(changed_again, 0)


if __name__ == "__main__":
    unittest.main()
