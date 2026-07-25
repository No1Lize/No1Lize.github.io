#!/usr/bin/env python3
"""Run specialized official-source crawling without duplicating generic media sources."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from . import crawl_official_with_tracking as official_tracking
except ImportError:
    import crawl_official_with_tracking as official_tracking


def _is_eastmoney(raw: dict[str, Any]) -> bool:
    url = str(raw.get("url") or "")
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    return host.endswith("eastmoney.com") or "东方财富" in str(raw.get("name") or "")


def _filtered_build_user_specs(
    tracking: dict[str, Any],
) -> list[official_tracking.official.CompanySpec]:
    """Keep only company sites and specialized Eastmoney media crawling."""

    filtered = copy.deepcopy(tracking)
    filtered["sources"] = [
        raw
        for raw in tracking.get("sources", [])
        if isinstance(raw, dict)
        and raw.get("enabled", True) is not False
        and (
            str(raw.get("sourceCategory") or "") == "company"
            or _is_eastmoney(raw)
        )
    ]
    return _ORIGINAL_BUILD(filtered)


_ORIGINAL_BUILD = official_tracking.build_user_specs


def main() -> int:
    official_tracking.build_user_specs = _filtered_build_user_specs
    return official_tracking.main()


if __name__ == "__main__":
    raise SystemExit(main())
