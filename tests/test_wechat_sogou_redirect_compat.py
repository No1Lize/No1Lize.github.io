from __future__ import annotations

import unittest
from types import SimpleNamespace

from tools import wechat_sogou_redirect_compat as compat


class WeChatSogouRedirectCompatTests(unittest.TestCase):
    def test_escaped_original_url_is_resolved(self) -> None:
        body = (
            r'<script>window.location.href="https:\/\/mp.weixin.qq.com\/s?'
            r'__biz=MzA1&amp;mid=123&amp;idx=1&amp;sn=abc";</script>'
        )
        resolved = compat.resolve_current_redirect(body)
        self.assertTrue(resolved.startswith("https://mp.weixin.qq.com/s?"))
        self.assertIn("&mid=123", resolved)

    def test_location_replace_is_resolved(self) -> None:
        body = (
            '<script>location.replace("https://mp.weixin.qq.com/s/'
            'AbCdEfGhIjKlMn");</script>'
        )
        self.assertEqual(
            compat.resolve_current_redirect(body),
            "https://mp.weixin.qq.com/s/AbCdEfGhIjKlMn",
        )

    def test_meta_refresh_is_resolved(self) -> None:
        body = (
            '<meta http-equiv="refresh" content="0; url='
            'https://mp.weixin.qq.com/s?__biz=abc&amp;mid=1">'
        )
        self.assertEqual(
            compat.resolve_current_redirect(body),
            "https://mp.weixin.qq.com/s?__biz=abc&mid=1",
        )

    def test_non_article_wechat_url_is_rejected(self) -> None:
        body = '<script>location.href="https://mp.weixin.qq.com/mp/profile_ext?action=home"</script>'
        self.assertEqual(compat.resolve_current_redirect(body), "")

    def test_install_preserves_legacy_parser_first(self) -> None:
        index = SimpleNamespace(resolve_script_url=lambda _body: "https://mp.weixin.qq.com/s/legacy")
        compat.install(index)
        self.assertEqual(index.resolve_script_url("ignored"), "https://mp.weixin.qq.com/s/legacy")


if __name__ == "__main__":
    unittest.main()
