import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import get_settings


@lru_cache
def load_snapshot() -> dict[str, Any]:
    path = Path(get_settings().snapshot_path)
    if not path.exists():
        return {
            "updated_at": None,
            "events": [],
            "companies": [],
            "institutions": [],
            "sectors": [],
            "ipo": [],
            "people": [],
            "reports": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def paginated(items: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "page": page,
        "page_size": page_size,
        "total": len(items),
    }


def find_by_slug(items: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("slug") == slug), None)
