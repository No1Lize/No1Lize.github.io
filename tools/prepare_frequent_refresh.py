#!/usr/bin/env python3
"""Persist the current article identities before a frequent refresh."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
BASELINE_PATH = Path(os.environ.get("RUNNER_TEMP", str(ROOT))) / "vciq-frequent-refresh-baseline.json"


def article_identity(article: dict) -> str:
    article_id = str(article.get("id") or "").strip()
    if article_id:
        return article_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url") or "").strip()


def main() -> int:
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    articles = [item for item in payload.get("articles", []) if isinstance(item, dict)]
    identities = sorted(
        identity for identity in (article_identity(item) for item in articles) if identity
    )
    baseline = {
        "articleCount": len(articles),
        "articleIds": identities,
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(baseline, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
