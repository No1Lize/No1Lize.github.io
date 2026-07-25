#!/usr/bin/env python3
"""Run the tracking-aware crawler with repository-backed SEC coverage.

``crawl_with_tracking.py`` already merges technology tracks, people, RSS feeds,
company sources and manually configured SEC sources. This wrapper adds the one
missing policy boundary: the enabled US-listed companies in
``config/user_tracking.json`` replace the main crawler's static SEC watchlist.
Consequently, adding, disabling or deleting a listed company in the gear admin
also changes the next EDGAR crawl.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import crawl_with_tracking as tracking_crawler  # noqa: E402

crawler = tracking_crawler.crawler
TRACKING_CONFIG_PATH = ROOT / "config" / "user_tracking.json"
_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:64]
    return slug or "listed-company"


def _infer_region(name: str) -> str:
    return "中国" if re.search(r"[\u3400-\u9fff]", name) else "美国"


def load_sec_tracking(
    path: Path = TRACKING_CONFIG_PATH,
) -> dict[str, tuple[str, str, str, str]]:
    """Return enabled US-listed companies in the crawler's SEC tuple format.

    A missing or malformed configuration keeps the crawler's built-in defaults.
    A valid empty ``listedCompanies`` array is intentional and disables the base
    SEC watchlist; manually configured SEC sources can still be merged later by
    ``crawl_with_tracking.py``.
    """

    fallback = dict(crawler.SEC_TRACKED)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(
            f"Tracking configuration warning: {type(exc).__name__}: {exc}; "
            "using built-in SEC defaults.",
            file=sys.stderr,
        )
        return fallback

    listed = payload.get("listedCompanies") if isinstance(payload, dict) else None
    if not isinstance(listed, list):
        return fallback

    dynamic: dict[str, tuple[str, str, str, str]] = {}
    for raw in listed:
        if not isinstance(raw, dict):
            continue
        if raw.get("enabled") is False or raw.get("market") != "美股":
            continue

        ticker = str(raw.get("ticker") or "").strip().upper().replace(" ", "")
        name = str(raw.get("name") or "").strip()
        if not ticker or not name or not _TICKER_PATTERN.fullmatch(ticker):
            continue

        previous = fallback.get(ticker)
        slug = str(raw.get("catalogSlug") or "").strip()
        if not slug:
            slug = previous[1] if previous else _slugify(name or ticker)
        sector = str(raw.get("sector") or "").strip()
        if not sector:
            sector = previous[2] if previous else "未分类"
        region = previous[3] if previous else _infer_region(name)
        dynamic[ticker] = (name, slug, sector, region)

    return dynamic


def configure_crawler(path: Path = TRACKING_CONFIG_PATH) -> int:
    tracked = load_sec_tracking(path)
    crawler.SEC_TRACKED = tracked
    print(
        f"Loaded {len(tracked)} enabled US-listed companies from "
        f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}.",
        file=sys.stderr,
    )
    return len(tracked)


def _install_empty_sec_guard() -> None:
    original_crawl_sec = crawler.crawl_sec

    def crawl_sec(user_agent: str):
        if crawler.SEC_TRACKED:
            return original_crawl_sec(user_agent)
        return (
            [],
            {},
            crawler._status(
                "sec",
                "SEC EDGAR",
                "disabled",
                0,
                0,
                platform="SEC",
            ),
        )

    crawler.crawl_sec = crawl_sec


def main() -> int:
    configure_crawler()
    _install_empty_sec_guard()
    return tracking_crawler.main()


if __name__ == "__main__":
    raise SystemExit(main())
