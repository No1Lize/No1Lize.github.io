from __future__ import annotations

import unittest

from tools.source_evidence import (
    article_source_grade_index,
    classify_source_evidence,
    classify_source_role,
    enrich_article_sources,
    enrich_source_evidence,
    validate_source_evidence,
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

    def test_first_party_sources_are_grade_b_and_primary(self) -> None:
        source = enrich_source_evidence(
            {
                "name": "Google DeepMind",
                "url": "https://deepmind.google/blog/sample",
                "level": "官方披露",
                "platform": "官方网站",
            },
            source_id="official-google",
        )
        self.assertEqual(source["evidenceGrade"], "B")
        self.assertEqual(source["sourceRole"], "primary")
        self.assertIn("主体官方", source["evidenceLabel"])

    def test_media_and_database_sources_are_grade_c_and_corroboration(self) -> None:
        source = enrich_source_evidence(
            {
                "name": "TechCrunch",
                "url": "https://techcrunch.com/story",
                "level": "媒体报道",
                "platform": "专业媒体",
            },
            source_id="techcrunch",
        )
        self.assertEqual(source["evidenceGrade"], "C")
        self.assertEqual(source["sourceRole"], "corroboration")
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

    def test_auto_media_and_search_sources_are_discovery_even_when_grade_c(self) -> None:
        self.assertEqual(
            classify_source_role(
                grade="C",
                source_id="user-source-source-auto-media-example-com",
                platform="Example Media",
                url="https://example.com/story",
            ),
            "discovery",
        )
        self.assertEqual(
            classify_source_role(
                grade="C",
                source_id="user-track-ai-google-us",
                platform="Google",
                url="https://example.com/story",
            ),
            "discovery",
        )

    def test_direct_wechat_is_corroboration_not_search_discovery(self) -> None:
        self.assertEqual(
            classify_source_role(
                grade="C",
                source_id="user-track-wechat-ai",
                platform="微信",
                url="https://mp.weixin.qq.com/s/example",
            ),
            "corroboration",
        )

    def test_explicit_portfolio_role_survives_article_enrichment(self) -> None:
        rows = enrich_article_sources(
            [
                {
                    "sourceId": "professional-media-tail",
                    "sourceRole": "discovery",
                    "source": {
                        "name": "Tail Media",
                        "url": "https://tail.example/story",
                        "level": "媒体报道",
                        "platform": "Tail Media",
                        "sourceRole": "discovery",
                    },
                }
            ]
        )
        self.assertEqual(rows[0]["source"]["evidenceGrade"], "C")
        self.assertEqual(rows[0]["source"]["sourceRole"], "discovery")
        self.assertEqual(rows[0]["sourceRole"], "discovery")
        self.assertEqual(validate_source_evidence(rows[0]["source"]), [])

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
