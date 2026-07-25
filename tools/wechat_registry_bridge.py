"""Runtime bridge between the WeChat parser and the account registry."""

from __future__ import annotations

from typing import Any

try:
    from . import wechat_source_registry
except ImportError:
    import wechat_source_registry


def install(wechat: Any) -> None:
    """Apply whitelist-first discovery and strict account verification."""

    wechat.generated_wechat_sources = wechat_source_registry.generated_wechat_sources

    original_parse = wechat.parse_wechat_article
    if getattr(original_parse, "_wechat_registry_verified", False):
        return

    def parse_wechat_article(
        spec: dict[str, Any],
        url: str,
        body: str,
        crawler: Any,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        if spec.get("expectedAccounts"):
            parser = wechat.WeChatPageParser()
            parser.feed(body or "")
            observed_account = parser.account or wechat._js_value(
                body or "",
                ("nickname", "profile_nickname", "account_name"),
            )
            if not wechat_source_registry.account_matches(spec, observed_account):
                return None

        article = original_parse(spec, url, body, crawler, **kwargs)
        if article and isinstance(article.get("source"), dict):
            article["source"]["level"] = spec.get("sourceLevel", "媒体报道")
            article["source"]["platform"] = "微信"
            if spec.get("accountConfigId"):
                article["wechatAccountConfigId"] = spec["accountConfigId"]
        return article

    setattr(parse_wechat_article, "_wechat_registry_verified", True)
    wechat.parse_wechat_article = parse_wechat_article
