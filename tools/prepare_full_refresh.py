#!/usr/bin/env python3
"""Prepare an atomic full-source intelligence refresh.

The snapshot historically merged new source statuses into old ones. That made a
partial crawler run look like a complete run because stale success rows remained
visible. A full refresh must start with an empty status ledger; every configured
crawler then writes a fresh status row, including explicit errors and empty
results. The repository file is only committed after the whole workflow passes.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"


def main() -> int:
    if not ARTICLES_PATH.exists():
        raise SystemExit(f"missing snapshot: {ARTICLES_PATH}")

    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be a JSON object")

    previous_statuses = payload.get("sourceStatus", [])
    previous_count = len(previous_statuses) if isinstance(previous_statuses, list) else 0

    payload["sourceStatus"] = []
    payload["qualityGate"] = {}
    payload.pop("refreshAudit", None)
    payload.pop("trackingConfigHash", None)
    payload.pop("trackingEnrichedAt", None)
    payload.pop("trackCoverage", None)

    ARTICLES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"clearedSourceStatuses": previous_count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
