from __future__ import annotations

import unittest

from tools.resolved_company_captures import resolved_company_captures


class ResolvedCompanyCandidateTests(unittest.TestCase):
    def test_only_resolved_companies_reach_manual_candidate_scoring(self) -> None:
        captures = {
            "records": [
                {
                    "id": "capture-github",
                    "entityType": "company",
                    "canonicalName": "GitHub",
                    "rawSelection": "GitHub",
                    "status": "applied",
                    "capturedAt": "2026-08-06T00:00:00Z",
                    "trackNames": ["AI / AGI"],
                    "source": {
                        "title": "GitHub 平台发布新功能",
                        "url": "https://example.com/github",
                        "sourceName": "专业媒体",
                        "eventType": "公司动态",
                    },
                },
                {
                    "id": "capture-typescript",
                    "entityType": "company",
                    "canonicalName": "TypeScript",
                    "rawSelection": "TypeScript",
                    "status": "applied",
                    "capturedAt": "2026-08-06T00:00:00Z",
                    "trackNames": ["AI / AGI"],
                    "source": {
                        "title": "TypeScript 编程语言更新",
                        "url": "https://example.com/typescript",
                        "sourceName": "专业媒体",
                        "eventType": "技术突破",
                    },
                },
                {
                    "id": "capture-matt",
                    "entityType": "company",
                    "canonicalName": "Matt",
                    "rawSelection": "Matt",
                    "status": "applied",
                    "capturedAt": "2026-08-06T00:00:00Z",
                    "trackNames": ["AI / AGI"],
                    "source": {
                        "title": "AI 工程化先锋 Matt 分享经验",
                        "url": "https://example.com/matt",
                        "sourceName": "专业媒体",
                        "eventType": "人物观点",
                    },
                },
            ]
        }
        decisions = {
            "decisions": {
                "github": {
                    "status": "resolved",
                    "requestedType": "company",
                    "entityType": "company",
                    "canonicalName": "GitHub",
                    "targetId": "company:github",
                    "confidence": "verified",
                },
                "typescript": {
                    "status": "resolved",
                    "requestedType": "company",
                    "entityType": "topic",
                    "canonicalName": "TypeScript",
                    "targetId": "topic:typescript",
                    "confidence": "verified",
                },
                "matt": {
                    "status": "review",
                    "requestedType": "company",
                    "entityType": "person",
                    "canonicalName": "Matt",
                    "targetId": "",
                    "confidence": "low",
                },
            }
        }
        filtered, stats = resolved_company_captures(
            captures,
            entity_decisions_payload=decisions,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )
        self.assertEqual([row["canonicalName"] for row in filtered["records"]], ["GitHub"])
        self.assertEqual(stats["companyCount"], 1)
        self.assertEqual(stats["reviewCount"], 1)
        self.assertEqual(stats["reclassifiedCount"], 2)



if __name__ == "__main__":
    unittest.main()
