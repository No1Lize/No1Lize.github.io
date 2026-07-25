#!/usr/bin/env python3
"""Run the standard crawler with verified WeChat account routing enabled."""

from __future__ import annotations

try:  # Imported by tests as tools.crawl_with_wechat_registry.
    from . import crawl_with_source_categories as base
    from . import wechat_index_context_guard
    from . import wechat_index_record_fallback
    from . import wechat_public_sources
    from . import wechat_registry_bridge
    from . import wechat_sogou_bridge
    from . import wechat_snapshot_quality
except ImportError:  # Executed directly with python tools/...
    import crawl_with_source_categories as base
    import wechat_index_context_guard
    import wechat_index_record_fallback
    import wechat_public_sources
    import wechat_registry_bridge
    import wechat_sogou_bridge
    import wechat_snapshot_quality


def _install_snapshot_quality() -> None:
    original = base.tracking.crawler.replace_source_batches
    if getattr(original, "_wechat_snapshot_quality", False):
        return

    def replace_source_batches(existing, incoming, statuses):
        wechat_rows = [
            article
            for article in incoming
            if article.get("source", {}).get("platform") == "微信"
        ]
        other_rows = [
            article
            for article in incoming
            if article.get("source", {}).get("platform") != "微信"
        ]
        resolved = wechat_snapshot_quality.resolve_cross_sector_articles(
            wechat_rows,
            base.tracking.load_tracking(),
        )
        return original(existing, [*other_rows, *resolved], statuses)

    setattr(replace_source_batches, "_wechat_snapshot_quality", True)
    base.tracking.crawler.replace_source_batches = replace_source_batches


def main() -> int:
    wechat_registry_bridge.install(wechat_public_sources)
    wechat_index_context_guard.install(wechat_registry_bridge)
    wechat_index_record_fallback.install(
        wechat_public_sources,
        wechat_registry_bridge,
    )
    wechat_sogou_bridge.install(wechat_public_sources)
    _install_snapshot_quality()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
