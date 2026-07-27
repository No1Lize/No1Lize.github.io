from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from tools import wechat_sogou_link_compat as compat


class WeChatSogouLinkCompatTest(unittest.TestCase):
    def test_adds_public_k_h_link_signature(self) -> None:
        url = "https://weixin.sogou.com/link?url=abcdefghijklmnopqrstuvwxyz"
        body = 'href.substr(a+1+parseInt("2")+b,1)'
        signed = compat.guarded_result_url(url, body, nonce=3)
        query = parse_qs(urlsplit(signed).query)
        expected_offset = url.find("url=") + 1 + 2 + 3
        self.assertEqual(query["k"], ["3"])
        self.assertEqual(query["h"], [url[expected_offset]])

    def test_leaves_non_result_url_unchanged(self) -> None:
        url = "https://mp.weixin.qq.com/s?__biz=test"
        self.assertEqual(compat.guarded_result_url(url, "", nonce=3), url)


if __name__ == "__main__":
    unittest.main()
