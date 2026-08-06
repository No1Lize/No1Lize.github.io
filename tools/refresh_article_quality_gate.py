#!/usr/bin/env python3
"""Rebuild the persisted article quality gate without repeating network crawling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import crawl_articles
except ImportError:
    import crawl_articles  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"


def _load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing article snapshot: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid article snapshot JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be a JSON object")
    return payload


def evaluate_current_quality(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate quality for the supplied snapshot without mutating it."""

    config = crawl_articles.load_config()
    return crawl_articles.evaluate_quality(
        [row for row in payload.get("articles", []) if isinstance(row, dict)],
        [row for row in payload.get("sourceStatus", []) if isinstance(row, dict)],
        config.get("qualityGate", {}),
    )


def rebuild_quality_gate(path: Path = ARTICLES_PATH) -> tuple[dict[str, Any], bool]:
    """Recompute and persist the quality gate for the current snapshot state."""

    payload = _load_payload(path)
    quality = evaluate_current_quality(payload)
    if quality.get("passed") is not True:
        print(json.dumps(quality, ensure_ascii=False, sort_keys=True))
        raise SystemExit("article quality gate cannot be rebuilt because the snapshot fails")

    changed = payload.get("qualityGate") != quality
    if changed:
        payload["qualityGate"] = quality
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return quality, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    args = parser.parse_args()

    payload = _load_payload(args.articles)
    quality = evaluate_current_quality(payload)
    if quality.get("passed") is not True:
        print(json.dumps(quality, ensure_ascii=False, sort_keys=True))
        raise SystemExit("article snapshot fails the current quality gate")

    if args.check:
        changed = False
        if payload.get("qualityGate") != quality:
            raise SystemExit("article quality gate is not current")
    else:
        quality, changed = rebuild_quality_gate(args.articles)

    print(
        json.dumps(
            {
                "passed": True,
                "changed": changed,
                "articleCount": len(payload.get("articles", [])),
                "invalidArticles": len(quality.get("invalidArticles", [])),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
