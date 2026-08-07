from __future__ import annotations

import unittest

from tools.apply_manual_company_trust import (
    TRUST_NOTE,
    apply_manual_company_trust,
)


def candidate(
    name: str,
    *,
    capture_ids: list[str] | None = None,
    status: str = "pending",
) -> dict:
    key = "".join(character for character in name.casefold() if character.isalnum())
    return {
        "id": f"candidate-{key}",
        "decisionKey": key,
        "name": name,
        "status": status,
        "captureCount": len(capture_ids or []),
        "captureIds": capture_ids or [],
        "lastSeenAt": "2026-08-07T10:00:00+00:00",
    }


def tracking(
    companies: list[str] | None = None,
    *,
    keywords: list[str] | None = None,
) -> dict:
    return {
        "schemaVersion": 1,
        "tracks": [
            {
                "slug": "ai",
                "name": "AI / AGI",
                "sampleCompanies": companies or [],
                "people": [],
                "keywords": keywords or [],
            }
        ],
    }


def capture(
    capture_id: str,
    name: str,
    *,
    title: str | None = None,
    captured_by: str = "VCIQ",
) -> dict:
    return {
        "id": capture_id,
        "entityType": "company",
        "canonicalName": name,
        "rawSelection": name,
        "status": "applied",
        "capturedAt": "2026-08-07T09:30:00Z",
        "capturedBy": captured_by,
        "source": {
            "title": title or f"{name} 公司完成新一轮融资",
            "url": f"https://example.com/{capture_id}",
            "sourceName": "专业媒体",
            "eventType": "融资",
        },
    }


class ManualCompanyTrustTests(unittest.TestCase):
    def apply(
        self,
        candidates: list[dict],
        *,
        decisions: dict | None = None,
        tracking_payload: dict | None = None,
        captures: list[dict] | None = None,
        people: list[dict] | None = None,
        entity_decisions: dict | None = None,
    ):
        return apply_manual_company_trust(
            {
                "schemaVersion": 1,
                "generatedAt": "2026-08-07T10:00:00Z",
                "candidates": candidates,
            },
            decisions or {"schemaVersion": 1, "decisions": {}},
            tracking_payload or tracking(),
            {"schemaVersion": 1, "records": captures or []},
            entity_decisions_payload=entity_decisions or {"decisions": {}},
            company_registry_payload={"companies": []},
            people_payload={"people": people or []},
        )

    def test_resolved_manual_capture_is_auto_accepted(self) -> None:
        next_decisions, report = self.apply(
            [candidate("Firmus", capture_ids=["capture-firmus"])],
            tracking_payload=tracking(["Firmus"]),
            captures=[capture("capture-firmus", "Firmus")],
        )

        decision = next_decisions["decisions"]["firmus"]
        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(decision["reviewedBy"], "VCIQ")
        self.assertEqual(decision["decidedAt"], "2026-08-07T09:30:00Z")
        self.assertEqual(decision["note"], TRUST_NOTE)
        self.assertEqual(report["captureTrustedKeys"], ["firmus"])
        self.assertEqual(report["manualExceptionCount"], 0)

    def test_automated_capture_cannot_inherit_manual_trust_through_tracking(self) -> None:
        next_decisions, report = self.apply(
            [candidate("Crawler Labs", capture_ids=["capture-crawler"])],
            tracking_payload=tracking(["Crawler Labs"]),
            captures=[
                capture(
                    "capture-crawler",
                    "Crawler Labs",
                    captured_by="github-actions[bot]",
                )
            ],
        )

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["trustedCount"], 0)
        self.assertEqual(report["manualExceptionCount"], 1)
        self.assertIn("人工操作者", report["manualExceptions"][0]["reason"])

    def test_capture_without_actor_cannot_inherit_manual_trust(self) -> None:
        next_decisions, report = self.apply(
            [candidate("Anonymous Labs", capture_ids=["capture-anonymous"])],
            tracking_payload=tracking(["Anonymous Labs"]),
            captures=[capture("capture-anonymous", "Anonymous Labs", captured_by="")],
        )

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["trustedCount"], 0)
        self.assertEqual(report["manualExceptionCount"], 1)

    def test_sample_companies_without_audit_provenance_stays_pending(self) -> None:
        next_decisions, report = self.apply(
            [candidate("Taalas")],
            tracking_payload=tracking(["Taalas"]),
        )

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["trackingTrustedCount"], 0)
        self.assertEqual(report["provenancePendingKeys"], ["taalas"])

    def test_automatically_discovered_candidate_stays_pending(self) -> None:
        next_decisions, report = self.apply([candidate("Auto Discovery Labs")])

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["trustedCount"], 0)
        self.assertEqual(report["manualExceptionCount"], 0)
        self.assertEqual(report["provenancePendingKeys"], ["autodiscoverylabs"])

    def test_cross_type_topic_conflict_remains_review_gated(self) -> None:
        next_decisions, report = self.apply(
            [candidate("TypeScript", capture_ids=["capture-typescript"])],
            tracking_payload=tracking(["TypeScript"], keywords=["TypeScript"]),
            captures=[capture("capture-typescript", "TypeScript")],
        )

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["trustedCount"], 0)
        self.assertEqual(report["manualExceptionCount"], 1)
        self.assertEqual(report["manualExceptions"][0]["candidateKey"], "typescript")

    def test_cross_type_person_conflict_remains_review_gated(self) -> None:
        next_decisions, report = self.apply(
            [candidate("Matt", capture_ids=["capture-matt"])],
            tracking_payload=tracking(["Matt"]),
            captures=[capture("capture-matt", "Matt")],
            people=[{"slug": "matt", "name": "Matt"}],
        )

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["manualExceptionCount"], 1)

    def test_final_rejection_is_never_overwritten_by_manual_trust(self) -> None:
        original = {
            "schemaVersion": 1,
            "decisions": {
                "firmus": {
                    "status": "rejected",
                    "note": "已确认不是目标公司",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-06T00:00:00Z",
                    "reviewedBy": "VCIQ",
                }
            },
        }
        next_decisions, report = self.apply(
            [candidate("Firmus", capture_ids=["capture-firmus"])],
            decisions=original,
            tracking_payload=tracking(["Firmus"]),
            captures=[capture("capture-firmus", "Firmus")],
        )

        self.assertEqual(next_decisions, original)
        self.assertEqual(report["trustedCount"], 0)
        self.assertEqual(report["preservedFinalCount"], 1)

    def test_versioned_entity_reclassification_blocks_company_auto_accept(self) -> None:
        next_decisions, report = self.apply(
            [candidate("Kimi", capture_ids=["capture-kimi"])],
            tracking_payload=tracking(["Kimi"]),
            captures=[capture("capture-kimi", "Kimi")],
            entity_decisions={
                "decisions": {
                    "kimi": {
                        "status": "resolved",
                        "requestedType": "company",
                        "entityType": "topic",
                        "canonicalName": "Kimi",
                        "targetId": "topic:kimi",
                        "confidence": "verified",
                        "note": "按技术主题处理",
                    }
                }
            },
        )

        self.assertEqual(next_decisions["decisions"], {})
        self.assertEqual(report["manualExceptionCount"], 1)


if __name__ == "__main__":
    unittest.main()
