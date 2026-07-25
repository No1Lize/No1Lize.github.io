#!/usr/bin/env python3
"""Run the standard crawler with verified WeChat account routing enabled."""

from __future__ import annotations

try:  # Imported by tests as tools.crawl_with_wechat_registry.
    from . import crawl_with_source_categories as base
    from . import wechat_public_sources
    from . import wechat_registry_bridge
    from . import wechat_sogou_bridge
except ImportError:  # Executed directly with python tools/...
    import crawl_with_source_categories as base
    import wechat_public_sources
    import wechat_registry_bridge
    import wechat_sogou_bridge


def main() -> int:
    wechat_registry_bridge.install(wechat_public_sources)
    wechat_sogou_bridge.install(wechat_public_sources)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
