from __future__ import annotations

import unittest

from tools.source_evidence import (
    article_source_grade_index,
    classify_source_evidence,
    enrich_source_evidence,
)


class SourceEvidenceTests(unittest.TestCase):
    def test_regulatory_sources_are_grade_a(self) -> None:
        self.assertEqual(
            classify_source_evidence(
                level="监管文件",
                platform="SEC",
                url="https://www.sec.gov/Archives/sample",
            ),
            "A",
        )
        self.assertEqual(
            classify_source_evidence(
                level="官方披露",
                platform="公告",
                url="https://static.cninfo.com.cn/sample.pdf",
            ),
            "A",
        )

    def test_first_party_sources_are_grade_b(self) -> None:
        source = enrich_source_evidence(
            {
                "name": "Google DeepMind",
                "url": "https://deepmind.google/blog/sample",
                "level": "官方披露",
                "platform": "官方网站",
            }
        )
        self.assertEqual(source["evidenceGrade"], "B")
        self.assertIn("主体官方", source["evidenceLabel"])

    def test_media_and_database_sources_are_grade_c(self) -> None:
        self.assertEqual(
            classify_source_evidence(
                level="媒体报道",
                platform="专业媒体",
                source_name="TechCrunch",
            ),
            "C",
        )
        self.assertEqual(
            classify_source_evidence(
                level="数据库记录",
                platform="OpenAlex",
            ),
            "C",
        )

    def test_discovery_indexes_are_grade_d_even_when_named_like_media(self) -> None:
        self.assertEqual(
            classify_source_evidence(
                level="待交叉验证",
                platform="用户追踪",
                source_name="媒体线索",
            ),
            "D",
        )

    def test_article_index_keeps_strongest_observed_grade(self) -> None:
        payload = {
            "articles": [
                {
                    "sourceId": "source-a",
                    "source": {"evidenceGrade": "D"},
                },
                {
                    "sourceId": "source-a",
                    "source": {"evidenceGrade": "C"},
                },
            ]
        }
        self.assertEqual(article_source_grade_index(payload), {"source-a": "C"})


if __name__ == "__main__":
    unittest.main()
