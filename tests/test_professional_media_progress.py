from __future__ import annotations

import contextlib
import io
import unittest

from tools import professional_media_progress as progress


class ProfessionalMediaProgressTest(unittest.TestCase):
    def test_media_sources_run_in_visible_batches(self) -> None:
        calls: list[list[str]] = []

        class FakeCrawler:
            @staticmethod
            def _crawl_config_group(specs, _user_agent):
                rows = list(specs)
                calls.append([str(row["id"]) for row in rows])
                articles = [
                    {"id": f"article-{row['id']}", "sourceId": row["id"]}
                    for row in rows
                ]
                statuses = [
                    {
                        "id": row["id"],
                        "status": "ok",
                        "accepted": 1,
                    }
                    for row in rows
                ]
                return articles, statuses, []

        crawler = FakeCrawler()
        progress.install(crawler, batch_size=10)
        specs = [
            {"id": "ordinary-a", "adapter": "rss"},
            {"id": "ordinary-b", "adapter": "generic_web"},
            *[
                {
                    "id": f"professional-media-{index:02d}",
                    "adapter": "professional_media",
                }
                for index in range(25)
            ],
        ]

        stream = io.StringIO()
        with contextlib.redirect_stderr(stream):
            articles, statuses, errors = crawler._crawl_config_group(specs, "agent")

        self.assertEqual([len(call) for call in calls], [2, 10, 10, 5])
        self.assertEqual(len(articles), 27)
        self.assertEqual(len(statuses), 27)
        self.assertEqual(errors, [])
        output = stream.getvalue()
        self.assertIn("progress=0/25", output)
        self.assertIn("progress=10/25", output)
        self.assertIn("progress=20/25", output)
        self.assertIn("progress=25/25", output)
        self.assertIn("accepted=25 successful=25", output)

    def test_install_is_idempotent(self) -> None:
        class FakeCrawler:
            @staticmethod
            def _crawl_config_group(specs, _user_agent):
                return list(specs), [], []

        crawler = FakeCrawler()
        progress.install(crawler)
        installed = crawler._crawl_config_group
        progress.install(crawler)
        self.assertIs(crawler._crawl_config_group, installed)


if __name__ == "__main__":
    unittest.main()
