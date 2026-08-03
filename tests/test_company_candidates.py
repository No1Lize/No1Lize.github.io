from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_company_candidates import (
    build_candidate_snapshot,
    semantic_payload,
    write_snapshot,
)
from tools.resolve_company_entities import build_registry


REGISTRY = build_registry(
    {
        "companies": [
            {
                "slug": "openai",
                "name": "OpenAI",
                "homepage": "https://openai.com/",
                "aliases": ["ChatGPT"],
            }
        ]
    }
)


def article(
    article_id: str,
    *,
    company: str = "",
    mentioned=None,
    source_url: str = "https://example.com/story",
    event_type: str = "公司动态",
    source_level: str = "媒体报道",
    published_at: str = "2026-08-03",
):
    return {
        "id": article_id,
        "title": "行业公开动态",
        "summary": "结构化公司字段用于候选发现。",
        "company": company,
        "mentionedCompanies": mentioned or [],
        "type": event_type,
        "sector": "AI / AGI",
        "region": "美国",
        "publishedAt": published_at,
        "source": {
            "name": "公开来源",
            "url": source_url,
            "level": source_level,
        },
    }


class CompanyCandidateTests(unittest.TestCase):
    def test_known_companies_and_free_text_are_not_candidates(self):
        snapshot = build_candidate_snapshot(
            {
                "generatedAt": "2026-08-03T12:00:00Z",
                "articles": [
                    article("known", company="OpenAI"),
                    {
                        **article("text-only"),
                        "title": "Nova Robotics 完成新产品发布",
                        "summary": "标题文本本身不得创建候选公司。",
                    },
                ],
            },
            REGISTRY,
        )
        self.assertEqual(snapshot["candidates"], [])

    def test_two_independent_structured_sources_create_pending_candidate(self):
        snapshot = build_candidate_snapshot(
            {
                "generatedAt": "2026-08-03T12:00:00Z",
                "articles": [
                    article(
                        "nova-1",
                        mentioned=["Nova Robotics"],
                        source_url="https://source-a.example/nova",
                        event_type="融资",
                    ),
                    article(
                        "nova-2",
                        company="nova robotics",
                        source_url="https://source-b.example/nova",
                        event_type="产品发布",
                    ),
                ],
            },
            REGISTRY,
        )
        self.assertEqual(snapshot["candidateCount"], 1)
        candidate = snapshot["candidates"][0]
        self.assertEqual(candidate["name"], "Nova Robotics")
        self.assertEqual(candidate["status"], "pending")
        self.assertEqual(candidate["articleCount"], 2)
        self.assertEqual(candidate["sourceCount"], 2)
        self.assertGreaterEqual(candidate["score"], 35)

    def test_single_high_signal_primary_source_can_enter_review_pool(self):
        snapshot = build_candidate_snapshot(
            {
                "generatedAt": "2026-08-03T12:00:00Z",
                "articles": [
                    article(
                        "quantum-1",
                        company="Quantum Works",
                        source_url="https://quantum.example/news",
                        event_type="技术突破",
                        source_level="官方披露",
                    )
                ],
            },
            REGISTRY,
        )
        self.assertEqual(snapshot["candidateCount"], 1)
        self.assertIn("存在官方、原始或监管来源", snapshot["candidates"][0]["reasons"])

    def test_rejected_decision_is_retained_as_a_tombstone(self):
        snapshot = build_candidate_snapshot(
            {
                "generatedAt": "2026-08-03T12:00:00Z",
                "articles": [
                    article(
                        "nova-1",
                        company="Nova Robotics",
                        event_type="融资",
                        source_level="官方披露",
                    )
                ],
            },
            REGISTRY,
            {
                "decisions": {
                    "novarobotics": {
                        "status": "rejected",
                        "note": "名称不是独立公司",
                    }
                }
            },
        )
        self.assertEqual(snapshot["rejectedCount"], 1)
        self.assertEqual(snapshot["candidates"][0]["status"], "rejected")
        self.assertEqual(snapshot["candidates"][0]["note"], "名称不是独立公司")

    def test_snapshot_write_ignores_timestamp_only_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            first = {
                "schemaVersion": 1,
                "generatedAt": "2026-08-03T00:00:00Z",
                "candidateCount": 0,
                "pendingCount": 0,
                "acceptedCount": 0,
                "rejectedCount": 0,
                "candidates": [],
            }
            second = {**first, "generatedAt": "2026-08-04T00:00:00Z"}
            self.assertTrue(write_snapshot(first, path))
            self.assertFalse(write_snapshot(second, path))
            current = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(semantic_payload(current), semantic_payload(second))
            self.assertEqual(current["generatedAt"], first["generatedAt"])


if __name__ == "__main__":
    unittest.main()
