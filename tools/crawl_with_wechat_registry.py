#!/usr/bin/env python3
"""Run the standard crawler with verified WeChat and professional media routing."""

from __future__ import annotations

try:  # Imported by tests as tools.crawl_with_wechat_registry.
    from . import crawl_with_source_categories as base
    from . import professional_media_progress
    from . import professional_media_sources
    from . import search_index_feed_redirects
    from . import wechat_fetch_compat
    from . import wechat_index_context_guard
    from . import wechat_index_record_fallback
    from . import wechat_original_redirect_bridge
    from . import wechat_public_sources
    from . import wechat_registry_bridge
    from . import wechat_sogou_bridge
    from . import wechat_sogou_index
    from . import wechat_sogou_link_compat
    from . import wechat_sogou_redirect_compat
    from . import wechat_snapshot_quality
except ImportError:  # Executed directly with python tools/...
    import crawl_with_source_categories as base
    import professional_media_progress
    import professional_media_sources
    import search_index_feed_redirects
    import wechat_fetch_compat
    import wechat_index_context_guard
    import wechat_index_record_fallback
    import wechat_original_redirect_bridge
    import wechat_public_sources
    import wechat_registry_bridge
    import wechat_sogou_bridge
    import wechat_sogou_index
    import wechat_sogou_link_compat
    import wechat_sogou_redirect_compat
    import wechat_snapshot_quality


def _publishable_article(article) -> bool:
    source = article.get("source") if isinstance(article, dict) else None
    source = source if isinstance(source, dict) else {}
    platform = str(source.get("platform", ""))
    source_id = str(article.get("sourceId", "")) if isinstance(article, dict) else ""
    is_wechat = (
        source_id.startswith("user-track-wechat-")
        or platform.startswith("微信")
        or bool(article.get("wechatAccount"))
    )
    if not is_wechat:
        return True
    return (
        platform == "微信"
        and article.get("wechatContentMode") != "index-only"
        and wechat_original_redirect_bridge.is_direct_wechat_url(
            str(source.get("url", ""))
        )
    )


def _install_snapshot_quality() -> None:
    original = base.tracking.crawler.replace_source_batches
    if getattr(original, "_wechat_snapshot_quality", False):
        return

    def replace_source_batches(existing, incoming, statuses):
        clean_existing = [article for article in existing if _publishable_article(article)]
        clean_incoming = [article for article in incoming if _publishable_article(article)]
        wechat_rows = [
            article
            for article in clean_incoming
            if article.get("source", {}).get("platform") == "微信"
        ]
        other_rows = [
            article
            for article in clean_incoming
            if article.get("source", {}).get("platform") != "微信"
        ]
        resolved = wechat_snapshot_quality.resolve_cross_sector_articles(
            wechat_rows,
            base.tracking.load_tracking(),
        )
        return original(clean_existing, [*other_rows, *resolved], statuses)

    setattr(replace_source_batches, "_wechat_snapshot_quality", True)
    base.tracking.crawler.replace_source_batches = replace_source_batches


def _install_professional_media() -> None:
    original = base._custom_sources
    if getattr(original, "_professional_media_catalog", False):
        return

    def custom_sources(tracking_config, tracks):
        runtime_specs, sec_specs = original(tracking_config, tracks)
        professional_specs = professional_media_sources.grouped_specs(
            tracks,
            base.tracking,
        )
        return [*runtime_specs, *professional_specs], sec_specs

    setattr(custom_sources, "_professional_media_catalog", True)
    base._custom_sources = custom_sources
    professional_media_sources.install(
        base.tracking.crawler,
        base.generic_web_sources,
    )
    professional_media_progress.install(base.tracking.crawler)
    prefixes = tuple(base.tracking.USER_SOURCE_PREFIXES)
    if "professional-media-" not in prefixes:
        base.tracking.USER_SOURCE_PREFIXES = (*prefixes, "professional-media-")


def main() -> int:
    search_index_feed_redirects.install(base.tracking.crawler)
    wechat_fetch_compat.install(wechat_public_sources)
    wechat_registry_bridge.install(wechat_public_sources)
    wechat_original_redirect_bridge.install(
        wechat_public_sources,
        wechat_registry_bridge,
    )
    wechat_index_context_guard.install(wechat_registry_bridge)
    wechat_index_record_fallback.install(
        wechat_public_sources,
        wechat_registry_bridge,
    )
    wechat_sogou_redirect_compat.install(wechat_sogou_index)
    wechat_sogou_link_compat.install(wechat_sogou_index)
    wechat_sogou_bridge.install(wechat_public_sources)
    _install_professional_media()
    _install_snapshot_quality()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
