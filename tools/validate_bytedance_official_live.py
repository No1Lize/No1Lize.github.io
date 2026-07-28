#!/usr/bin/env python3
"""Live acceptance test for ByteDance, Doubao Seed and Volcengine sources."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

try:
    from . import bytedance_official_sources as structured
    from . import crawl_official_companies as official
except ImportError:
    import bytedance_official_sources as structured
    import crawl_official_companies as official


EXPECTED = {
    "bytedance": ("bytedance.com", "/zh/news/"),
    "doubao": ("seed.bytedance.com", "/zh/blog/"),
    "volcengine": ("volcengine.com", "/news/detail/"),
}


def _matches_original(url: str, host_suffix: str, path_prefix: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    return (
        parts.scheme == "https"
        and (host == host_suffix or host.endswith(f".{host_suffix}"))
        and parts.path.startswith(path_prefix)
        and len(parts.path) > len(path_prefix)
    )


def validate() -> dict:
    registry = {spec.slug: spec for spec in official.load_registry()}
    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "ok": True,
        "sources": {},
    }
    for slug, (host_suffix, path_prefix) in EXPECTED.items():
        spec = registry.get(slug)
        if spec is None:
            report["ok"] = False
            report["sources"][slug] = {
                "ok": False,
                "error": "missing official registry entry",
            }
            continue
        articles, status = structured.crawl_structured_company(
            spec,
            official.DEFAULT_USER_AGENT,
            official,
        )
        originals = [
            article
            for article in articles
            if _matches_original(
                str(article.get("source", {}).get("url", "")),
                host_suffix,
                path_prefix,
            )
        ]
        source_ok = bool(articles) and len(originals) == len(articles)
        report["sources"][slug] = {
            "ok": source_ok,
            "accepted": len(articles),
            "originals": len(originals),
            "status": status,
            "articles": [
                {
                    "title": article.get("title"),
                    "publishedAt": article.get("publishedAt"),
                    "url": article.get("source", {}).get("url"),
                }
                for article in articles
            ],
        }
        if not source_ok:
            report["ok"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
