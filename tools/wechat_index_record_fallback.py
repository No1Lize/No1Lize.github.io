"""Reject unresolved public-index records and require original WeChat pages.

This module remains as a compatibility installation point for the refresh
pipeline. Public indexes may discover candidates, but they are not publishable
article sources. Only records resolved to ``mp.weixin.qq.com`` and parsed from
the original page can enter ``articles.json``.
"""

from __future__ import annotations

from typing import Any

try:
    from . import wechat_original_redirect_bridge
except ImportError:
    import wechat_original_redirect_bridge


def _build_index_article(
    row: dict[str, str],
    spec: dict[str, Any],
    crawler: Any,
    wechat: Any,
) -> None:
    """Never construct homepage articles from an aggregation/index record."""

    del row, spec, crawler, wechat
    return None


def install(wechat: Any, bridge: Any) -> None:
    """Install original-link resolution; unresolved index rows stay diagnostic."""

    wechat_original_redirect_bridge.install(wechat, bridge)
