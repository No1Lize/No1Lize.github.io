from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.entity_resolution import resolve_entity
from tools.reconcile_entity_resolution import reconcile_payloads


DECISIONS = {
    "schemaVersion": 1,
    "decisions": {
        "github": {
            "status": "resolved",
            "requestedType": "company",
            "entityType": "company",
            "canonicalName": "GitHub",
            "targetId": "company:github",
            "confidence": "verified",
            "aliases": [],
            "note": "人工确认。",
        },
        "typescript": {
            "status": "resolved",
            "requestedType": "company",
            "entityType": "topic",
            "canonicalName": "TypeScript",
            "targetId": "topic:typescript",
            "confidence": "verified",
            "aliases": [],
            "note": "编程语言。",
        },
        "matt": {
            "status": "review",
            "requestedType": "company",
            "entityType": "person",
            "canonicalName": "Matt",
            "targetId": "",
            "confidence": "low",
            "aliases": [],
            "note": "需要补齐完整姓名。",
        },
    },
}

SOURCE = {
    "title": "20万星里程碑达成！GitHub 技能包走红",
    "summary": "TypeScript 圈大佬、AI 工程化先锋 Matt Pocock 发布开源项目。",
    "sourceName": "专业媒体",
    "channel": "technology",
    "channelLabel": "新兴科技",
    "eventType": "公司动态",
    "url": "https://example.com/article",
}


class EntityResolutionTests(unittest.TestCase):
    def test_human_decisions_reclassify_and_hold_ambiguous_names(self) -> None:
        topic = resolve_entity(
            "company",
            "TypeScript",
            SOURCE,
            decisions_payload=DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )
        self.assertEqual(topic.status, "resolved")
        self.assertEqual(topic.entityType, "topic")
        self.assertTrue(topic.reclassified)

        ambiguous = resolve_entity(
            "company",
            "Matt",
            SOURCE,
            decisions_payload=DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )
        self.assertEqual(ambiguous.status, "review")
        self.assertEqual(ambiguous.source, "human-decision")

    def test_formal_people_override_wrong_requested_type(self) -> None:
        resolution = resolve_entity(
            "company",
            "Sam Altman",
            {"title": "OpenAI CEO Sam Altman speaks"},
            decisions_payload={"decisions": {}},
            company_registry_payload={"companies": []},
            people_payload={
                "people": [
                    {
                        "slug": "sam-altman",
                        "name": "Sam Altman",
                        "englishName": "Sam Altman",
                    }
                ]
            },
            tracking_payload={"tracks": []},
        )
        self.assertEqual(resolution.status, "resolved")
        self.assertEqual(resolution.entityType, "person")
        self.assertEqual(resolution.targetId, "person:sam-altman")

    def test_unknown_company_requires_local_company_context(self) -> None:
        resolved = resolve_entity(
            "company",
            "Polymarket",
            {
                "title": "预测市场平台 Polymarket 洽谈融资",
                "summary": "Polymarket 是预测市场创业公司。",
            },
            decisions_payload={"decisions": {}},
            company_registry_payload={"companies": []},
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )
        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(resolved.entityType, "company")

        review = resolve_entity(
            "company",
            "UnclearName",
            {"title": "UnclearName appears in a list"},
            decisions_payload={"decisions": {}},
            company_registry_payload={"companies": []},
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )
        self.assertEqual(review.status, "review")

    def test_reconciliation_moves_topics_and_removes_review_items(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI / AGI",
                    "enabled": True,
                    "custom": False,
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": ["GitHub", "TypeScript", "Matt"],
                }
            ],
            "listedCompanies": [],
            "sources": [],
        }
        records = []
        for index, name in enumerate(("GitHub", "TypeScript", "Matt"), start=1):
            records.append(
                {
                    "id": f"capture-{index}",
                    "entityType": "company",
                    "canonicalName": name,
                    "rawSelection": name,
                    "aliases": [],
                    "trackSlugs": ["ai"],
                    "trackNames": ["AI / AGI"],
                    "source": SOURCE,
                    "capturedAt": "2026-08-06T00:50:19Z",
                    "capturedBy": "VCIQ",
                    "status": "applied",
                    "appliedTo": ["ai:sampleCompanies"],
                    "reasons": [],
                    "note": "",
                }
            )
        inbox = {"schemaVersion": 1, "generatedAt": "", "records": records}

        next_config, next_inbox, stats = reconcile_payloads(
            config,
            inbox,
            decisions_payload=DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
        )
        track = next_config["tracks"][0]
        self.assertEqual(track["sampleCompanies"], ["GitHub"])
        self.assertEqual(track["keywords"], ["TypeScript"])
        self.assertEqual(track["people"], [])
        self.assertEqual(stats["review"], 1)
        self.assertEqual(stats["reclassified"], 2)

        by_name = {record["rawSelection"]: record for record in next_inbox["records"]}
        self.assertEqual(by_name["GitHub"]["status"], "applied")
        self.assertEqual(by_name["TypeScript"]["entityType"], "topic")
        self.assertEqual(by_name["TypeScript"]["status"], "applied")
        self.assertEqual(by_name["Matt"]["status"], "queued")
        self.assertEqual(by_name["Matt"]["appliedTo"], [])

        fixed_config, fixed_inbox, _ = reconcile_payloads(
            next_config,
            next_inbox,
            decisions_payload=DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
        )
        self.assertEqual(fixed_config, next_config)
        self.assertEqual(fixed_inbox, next_inbox)


if __name__ == "__main__":
    unittest.main()
