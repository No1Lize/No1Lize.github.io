from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tools import research_agent as agent


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def seed_data(root: Path, *, product: str = "A", disclosure: bool = False) -> None:
    data = root / "public" / "data"
    write_json(
        data / "venture_profiles.json",
        {
            "generatedAt": "2026-01-01T00:00:00Z",
            "companies": {
                "demo": {
                    "slug": "demo",
                    "name": "示例公司",
                    "updatedAt": "2026-01-01T00:00:00Z",
                    "products": [product],
                    "sources": [
                        {
                            "name": "公司官网",
                            "url": "https://example.com/product",
                            "level": "官方披露",
                        }
                    ],
                }
            },
        },
    )
    write_json(
        data / "institution_entities.json",
        {"entities": [{"id": "inst:1", "name": "示例资本", "sectors": ["AI"]}]},
    )
    write_json(
        data / "market_profiles.json",
        {
            "profiles": {
                "listed": {
                    "slug": "listed",
                    "company": {"name": "示例上市公司"},
                    "updatedAt": "2026-01-01T00:00:00Z",
                    "priceHistory": [
                        {"date": "2026-01-01", "close": 10},
                        {"date": "2026-01-02", "close": 11},
                    ],
                }
            }
        },
    )
    write_json(
        data / "people.json",
        {"people": [{"slug": "person", "name": "研究者", "role": "CEO"}]},
    )
    write_json(data / "institution_events.json", {"events": []})
    events = []
    if disclosure:
        events.append(
            {
                "id": "disclosure-1",
                "companyName": "示例上市公司",
                "publishedAt": "2026-01-03",
                "documentType": "并购与资产交易",
                "title": "重大资产交易公告",
                "source": {
                    "name": "交易所",
                    "url": "https://example.com/disclosure.pdf",
                    "level": "监管文件",
                },
            }
        )
    write_json(
        data / "listed_company_disclosures.json",
        {
            "companies": {
                "listed": {"slug": "listed", "name": "示例上市公司", "events": events}
            }
        },
    )


class ResearchAgentTest(unittest.TestCase):
    def test_canonicalize_ignores_volatile_timestamps(self) -> None:
        left = {"name": "A", "updatedAt": "one", "items": ["b", "a"]}
        right = {"name": "A", "updatedAt": "two", "items": ["a", "b"]}
        self.assertEqual(agent.stable_hash(left), agent.stable_hash(right))

    def test_detects_product_update_and_new_regulatory_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_data(root, product="A", disclosure=False)
            before = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-02T00:00:00+00:00"
            )
            seed_data(root, product="B", disclosure=True)
            after = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-03T00:00:00+00:00"
            )
            changes = agent.diff_snapshots(before, after)
            self.assertTrue(
                any(
                    row["dataset"] == "ventureCompany"
                    and "products" in row["changedFields"]
                    for row in changes
                )
            )
            disclosure = next(row for row in changes if row["dataset"] == "listedDisclosure")
            self.assertEqual(disclosure["action"], "added")
            self.assertGreaterEqual(disclosure["importance"], 96)

    def test_evidence_ids_are_attached_and_validated(self) -> None:
        change = {
            "id": "chg-1",
            "dataset": "listedDisclosure",
            "entityType": "上市公司公告",
            "entityId": "d1",
            "entityName": "示例公司",
            "action": "added",
            "changedFields": ["title"],
            "summary": "新增公告",
            "importance": 96,
            "before": None,
            "after": {"title": "公告"},
            "record": {
                "title": "公告",
                "source": {"name": "交易所", "url": "https://example.com/a.pdf"},
            },
        }
        changes, evidence = agent.build_evidence_package([change])
        self.assertEqual(changes[0]["evidenceIds"], ["E001"])
        self.assertEqual(evidence[0]["url"], "https://example.com/a.pdf")

    def test_model_analysis_drops_unknown_evidence_references(self) -> None:
        raw = {
            "executiveSummary": "摘要",
            "keyDevelopments": [
                {"title": "有效", "assessment": "A", "evidenceIds": ["E001"]},
                {"title": "无效", "assessment": "B", "evidenceIds": ["E999"]},
            ],
        }
        cleaned = agent.sanitize_analysis(raw, {"E001"})
        self.assertEqual(len(cleaned["keyDevelopments"]), 1)
        self.assertEqual(cleaned["keyDevelopments"][0]["title"], "有效")

    def test_offline_generation_writes_valid_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_data(root, product="A", disclosure=False)
            previous_snapshot = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-02T00:00:00+00:00"
            )
            seed_data(root, product="B", disclosure=True)
            snapshot_path = root / "public/data/research_agent_snapshot.json"
            output_path = root / "public/data/research_agent_daily.json"
            write_json(snapshot_path, previous_snapshot)
            report, snapshot = agent.generate_report(
                root=root,
                output_path=output_path,
                snapshot_path=snapshot_path,
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
                bootstrap_git_ref="HEAD^",
                offline=True,
                max_changes=36,
            )
            self.assertEqual(report["runStatus"], "offline-fallback")
            self.assertGreater(report["changeSummary"]["total"], 0)
            self.assertFalse(agent.validate_report(report))
            self.assertIn("contentHash", snapshot)


if __name__ == "__main__":
    unittest.main()
