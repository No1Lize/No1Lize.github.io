from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "frequent-intelligence-refresh.yml"


class FrequentRefreshWorkflowTests(unittest.TestCase):
    def test_primary_and_recovery_schedules_are_staggered(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "17 */2 * * *"', text)
        self.assertIn('cron: "47 */2 * * *"', text)
        self.assertNotIn("timezone:", text)

    def test_lightweight_refresh_shares_article_concurrency(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: public-article-refresh", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_lightweight_refresh_only_crawls_news_families(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/crawl_with_wechat_registry.py --source news", text)
        self.assertIn("python tools/finalize_frequent_refresh.py", text)
        self.assertNotIn("python -m tools.us_ir_baseline_disclosures", text)
        self.assertNotIn("python tools/refresh_market_profiles_enriched.py", text)
        self.assertNotIn("python tools/refresh_people_profiles_with_video.py", text)

    def test_successful_check_is_always_published(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('git commit -m "data: refresh public intelligence (two-hour check)"', text)
        self.assertIn("gh workflow run pages.yml --ref main", text)


if __name__ == "__main__":
    unittest.main()
