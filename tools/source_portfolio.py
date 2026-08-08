"""Source Portfolio v2 routing for professional media.

The catalog keeps all registered outlets for recall and source-health accounting,
but only a bounded healthy core receives the expensive direct-site fallback and
normal publication privilege. The long tail remains a cheap discovery surface.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_HEALTH_PATH = ROOT / "public" / "data" / "source_health.json"
CORE_MEDIA_LIMIT = 36
VALID_SOURCE_ROLES = {"primary", "corroboration", "discovery"}


def _load_health(path: Path = SOURCE_HEALTH_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _downgrade_ids(path: Path = SOURCE_HEALTH_PATH) -> set[str]:
    payload = _load_health(path)
    result: set[str] = set()
    for field in ("downgradeCandidates", "quarantinedSources", "retirementCandidates"):
        values = payload.get(field)
        if isinstance(values, list):
            result.update(str(value) for value in values if str(value))
    return result


def classify_professional_media_specs(
    specs: list[dict[str, Any]],
    *,
    health_path: Path = SOURCE_HEALTH_PATH,
    core_limit: int = CORE_MEDIA_LIMIT,
) -> list[dict[str, Any]]:
    """Assign publication roles while preserving one execution row per outlet.

    Health-downgraded outlets do not consume a core slot: the next eligible
    outlet is promoted until `core_limit` healthy corroboration sources are
    selected (or the catalog is exhausted). This keeps the active core near the
    intended 30–40 sources instead of shrinking after every quarantine cycle.
    """

    downgraded = _downgrade_ids(health_path)
    result: list[dict[str, Any]] = []
    core_limit = max(1, min(int(core_limit), len(specs) or 1))
    core_used = 0

    for raw in specs:
        spec = copy.deepcopy(raw)
        rows = spec.get("professionalMedia")
        rows = rows if isinstance(rows, list) else []
        explicit = str(spec.get("sourceRole") or "").strip().casefold()
        if explicit not in VALID_SOURCE_ROLES and rows:
            explicit = str(rows[0].get("sourceRole") or "").strip().casefold()
        source_id = str(spec.get("id") or "")

        if source_id in downgraded:
            role = "discovery"
        elif explicit in VALID_SOURCE_ROLES:
            role = explicit
        elif core_used < core_limit:
            role = "corroboration"
        else:
            role = "discovery"

        if role == "corroboration":
            core_used += 1

        spec["sourceRole"] = role
        spec["sourcePortfolioTier"] = "core" if role == "corroboration" else "discovery"
        if role == "discovery":
            spec["discoveryOnly"] = True
            spec["maxItems"] = 1
            budget = dict(spec.get("directRequestBudget") or {})
            budget["feedLimit"] = 0
            budget["candidateLimit"] = 1
            spec["directRequestBudget"] = budget
        else:
            spec.pop("discoveryOnly", None)
        for row in rows:
            if isinstance(row, dict):
                row["sourceRole"] = role
                row["sourcePortfolioTier"] = spec["sourcePortfolioTier"]
        spec["professionalMedia"] = rows
        result.append(spec)
    return result


def install_professional_media(module: Any) -> None:
    """Patch role attribution and make discovery-tier media search-only."""

    original_attribute = module.attribute_article
    if not getattr(original_attribute, "_source_portfolio_role", False):
        def attribute_article(article: dict[str, Any], rows: list[dict[str, Any]]):
            attributed = original_attribute(article, rows)
            if not attributed:
                return attributed
            matched = module.match_media(
                str(attributed.get("source", {}).get("url", "")), rows
            )
            if not matched:
                return attributed
            role = str(matched.get("sourceRole") or "").strip().casefold()
            if role not in VALID_SOURCE_ROLES:
                return attributed
            result = copy.deepcopy(attributed)
            source = dict(result.get("source") or {})
            source["sourceRole"] = role
            result["source"] = source
            result["sourceRole"] = role
            result["sourcePortfolioTier"] = str(
                matched.get("sourcePortfolioTier") or ""
            )
            return result

        setattr(attribute_article, "_source_portfolio_role", True)
        module.attribute_article = attribute_article

    original_crawl = module.crawl_professional_source
    if getattr(original_crawl, "_source_portfolio_budget", False):
        return

    def crawl_professional_source(
        spec: dict[str, Any],
        user_agent: str,
        crawler: Any,
        generic: Any,
        primary_crawl: Any,
    ):
        if not spec.get("discoveryOnly"):
            return original_crawl(spec, user_agent, crawler, generic, primary_crawl)

        rows = spec.get("professionalMedia")
        if not isinstance(rows, list) or not rows:
            raise ValueError("professional media source is missing registry metadata")
        max_items = 1
        discovery_spec = {**spec, "adapter": "rss", "url": spec["url"]}
        scanned = 0
        failures = 0
        errors: list[str] = []
        collected: list[dict[str, Any]] = []
        try:
            incoming, status = primary_crawl(discovery_spec, user_agent)
            collected.extend(incoming)
            scanned += max(1, int(status.get("scanned", 0) or 0))
            failures += int(status.get("failed", 0) or 0)
            if status.get("error"):
                errors.append(f"search {status['error']}")
        except Exception as exc:
            scanned = 1
            failures = 1
            errors.append(f"search {type(exc).__name__}: {exc}")

        attributed = module._dedupe_attributed(collected, rows, crawler, max_items)
        if attributed and failures == 0:
            status_name = "ok"
        elif attributed:
            status_name = "partial"
        elif failures:
            status_name = "error"
        else:
            status_name = "empty"
        status = crawler._status(
            spec["id"],
            spec["name"],
            status_name,
            scanned,
            len(attributed),
            failed=failures,
            platform=spec["name"],
            error="; ".join(errors[:2]) if errors and not attributed else None,
        )
        status.update(
            {
                "attempted": True,
                "adapter": "professional-media-v2-discovery",
                "canonicalSourceUrl": str(spec.get("sourceUrl") or ""),
                "discoveryUrl": str(spec.get("url") or ""),
                "sourceRole": "discovery",
                "sourcePortfolioTier": "discovery",
                "strategies": ["public-search-rss"],
                "candidateArticles": len(collected),
                "rejectedOutsideRegistry": max(0, len(collected) - len(attributed)),
                "requestBudget": {
                    "timeoutSeconds": 0,
                    "attempts": 1,
                    "feedLimit": 0,
                    "candidateLimit": 1,
                    "stopAfterAccepted": 1,
                },
            }
        )
        return attributed, status

    setattr(crawl_professional_source, "_source_portfolio_budget", True)
    module.crawl_professional_source = crawl_professional_source
