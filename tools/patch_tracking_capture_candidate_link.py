#!/usr/bin/env python3
"""One-time patch linking article capture records to the company candidate pool."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: patch target not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


builder = ROOT / "tools" / "build_company_candidates.py"
replace_once(
    builder,
    '''DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"\nOUTPUT_PATH = ROOT / "public" / "data" / "company_candidates.json"''',
    '''DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"\nCAPTURE_INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"\nOUTPUT_PATH = ROOT / "public" / "data" / "company_candidates.json"''',
)
replace_once(
    builder,
    '''    score = min(20, article_count * 5)\n    reasons: list[str] = []\n\n    if article_count >= 2:''',
    '''    score = min(20, article_count * 5)\n    reasons: list[str] = []\n    manual_capture_count = len(row.get("manualCaptureIds", []))\n\n    if manual_capture_count:\n        score += 35\n        reasons.append(f"{manual_capture_count} 条管理员文章采集")\n\n    if article_count >= 2:''',
)
replace_once(
    builder,
    '''def build_candidate_snapshot(\n    articles_payload: dict[str, Any],\n    registry: CompanyRegistry,\n    decisions_payload: dict[str, Any] | None = None,\n) -> dict[str, Any]:''',
    '''def build_candidate_snapshot(\n    articles_payload: dict[str, Any],\n    registry: CompanyRegistry,\n    decisions_payload: dict[str, Any] | None = None,\n    captures_payload: dict[str, Any] | None = None,\n) -> dict[str, Any]:''',
)
replace_once(
    builder,
    '''                    "publishedTimes": [],\n                    "primaryEvidence": False,\n                },''',
    '''                    "publishedTimes": [],\n                    "primaryEvidence": False,\n                    "manualCaptureIds": set(),\n                },''',
)
insert_marker = '''    candidates: list[dict[str, Any]] = []\n'''
insert_block = '''    for capture in (captures_payload or {}).get("records", []):\n        if not isinstance(capture, dict):\n            continue\n        if clean(capture.get("status"), 20) not in {"queued", "applied"}:\n            continue\n        if clean(capture.get("entityType"), 20) != "company":\n            continue\n        name = safe_candidate_name(capture.get("canonicalName"))\n        key = normalize_identity(name)\n        if not name or not key or (key in known and key not in decisions):\n            continue\n\n        source = capture.get("source") if isinstance(capture.get("source"), dict) else {}\n        source_url = clean(source.get("url"), 1200)\n        source_host = normalized_host(source_url) or clean(source.get("sourceName"), 200)\n        capture_id = clean(capture.get("id"), 200) or candidate_id(f"capture-{key}")\n        captured_at = clean(capture.get("capturedAt"), 60)\n        event_type = clean(source.get("eventType"), 80) or "人工关注"\n        track_names = capture.get("trackNames") if isinstance(capture.get("trackNames"), list) else []\n\n        row = groups.setdefault(\n            key,\n            {\n                "names": Counter(),\n                "articleIds": set(),\n                "sourceHosts": set(),\n                "sourceUrls": [],\n                "eventTypes": set(),\n                "sectors": Counter(),\n                "regions": Counter(),\n                "publishedTimes": [],\n                "primaryEvidence": False,\n                "manualCaptureIds": set(),\n            },\n        )\n        row["names"][name] += 1\n        row["articleIds"].add(capture_id)\n        row["manualCaptureIds"].add(capture_id)\n        if source_host:\n            row["sourceHosts"].add(source_host)\n        if source_url:\n            row["sourceUrls"].append(source_url)\n        if event_type:\n            row["eventTypes"].add(event_type)\n        for track_name in track_names:\n            sector = clean(track_name, 100)\n            if sector:\n                row["sectors"][sector] += 1\n        parsed_time = parse_time(captured_at)\n        if parsed_time:\n            row["publishedTimes"].append(parsed_time)\n\n    candidates: list[dict[str, Any]] = []\n'''
replace_once(builder, insert_marker, insert_block)
replace_once(
    builder,
    '''                "articleCount": len(raw["articleIds"]),\n                "sourceCount": len(raw["sourceHosts"]),''',
    '''                "articleCount": len(raw["articleIds"]),\n                "captureCount": len(raw["manualCaptureIds"]),\n                "captureIds": sorted(raw["manualCaptureIds"])[:20],\n                "sourceCount": len(raw["sourceHosts"]),''',
)
replace_once(
    builder,
    '''    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)\n    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)''',
    '''    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)\n    parser.add_argument("--captures", type=Path, default=CAPTURE_INBOX_PATH)\n    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)''',
)
replace_once(
    builder,
    '''    decisions = load_json(args.decisions, {"decisions": {}})\n    snapshot = build_candidate_snapshot(articles, load_registry(), decisions)''',
    '''    decisions = load_json(args.decisions, {"decisions": {}})\n    captures = load_json(args.captures, {"records": []})\n    snapshot = build_candidate_snapshot(articles, load_registry(), decisions, captures)''',
)


test_path = ROOT / "tests" / "test_company_candidates.py"
tests = test_path.read_text(encoding="utf-8")
method = '''    def test_manual_article_capture_enters_company_candidate_pool(self):\n        snapshot = build_candidate_snapshot(\n            {\n                "generatedAt": "2026-08-05T04:00:00Z",\n                "articles": [],\n            },\n            REGISTRY,\n            {"decisions": {}},\n            {\n                "records": [\n                    {\n                        "id": "capture-polymarket",\n                        "entityType": "company",\n                        "canonicalName": "Polymarket",\n                        "status": "applied",\n                        "capturedAt": "2026-08-05T03:30:00Z",\n                        "trackNames": ["预测市场"],\n                        "source": {\n                            "url": "https://finance.example/polymarket",\n                            "sourceName": "财经媒体",\n                            "eventType": "融资",\n                        },\n                    }\n                ]\n            },\n        )\n        self.assertEqual(snapshot["candidateCount"], 1)\n        candidate = snapshot["candidates"][0]\n        self.assertEqual(candidate["name"], "Polymarket")\n        self.assertEqual(candidate["captureCount"], 1)\n        self.assertEqual(candidate["captureIds"], ["capture-polymarket"])\n        self.assertGreaterEqual(candidate["score"], 35)\n        self.assertIn("1 条管理员文章采集", candidate["reasons"])\n        self.assertEqual(candidate["sector"], "预测市场")\n        self.assertEqual(candidate["sourceUrls"], ["https://finance.example/polymarket"])\n\n'''
marker = '\n\nif __name__ == "__main__":\n'
if marker not in tests:
    raise SystemExit("candidate test insertion point not found")
if "test_manual_article_capture_enters_company_candidate_pool" not in tests:
    test_path.write_text(
        tests.replace(marker, "\n\n" + method + 'if __name__ == "__main__":\n', 1),
        encoding="utf-8",
    )
