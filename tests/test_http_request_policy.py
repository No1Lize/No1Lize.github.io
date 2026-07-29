from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from email.message import Message
from urllib.error import HTTPError

from tools import http_request_policy


class HttpRequestPolicyTest(unittest.TestCase):
    def test_sec_preserves_identifying_user_agent(self) -> None:
        policy = http_request_policy.policy_for_url(
            "https://www.sec.gov/submissions/CIK0000320193.json",
            "VCIQ contact@example.com",
        )
        self.assertEqual(policy.user_agent, "VCIQ contact@example.com")
        self.assertGreaterEqual(policy.min_interval, 0.1)

    def test_wechat_uses_transparent_mobile_compatible_identity(self) -> None:
        policy = http_request_policy.policy_for_url(
            "https://mp.weixin.qq.com/s/example",
            "default",
        )
        self.assertIn("Mobile", policy.user_agent)
        self.assertIn("LizeRoadOne/3.0", policy.user_agent)
        self.assertGreaterEqual(policy.min_interval, 0.4)

    def test_retry_after_seconds_takes_precedence(self) -> None:
        headers = Message()
        headers["Retry-After"] = "12"
        error = HTTPError("https://example.com", 429, "rate limited", headers, None)
        policy = http_request_policy.RequestPolicy("test", base_backoff=0.5)
        self.assertEqual(http_request_policy.retry_delay(error, 0, policy), 12.0)

    def test_retry_after_http_date_is_bounded(self) -> None:
        now = datetime(2026, 7, 29, 0, 0, tzinfo=UTC)
        headers = Message()
        headers["Retry-After"] = (now + timedelta(seconds=90)).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        error = HTTPError("https://example.com", 503, "busy", headers, None)
        policy = http_request_policy.RequestPolicy("test", max_backoff=30)
        self.assertEqual(http_request_policy.retry_delay(error, 0, policy, now=now), 30)

    def test_non_retryable_http_status_stops_immediately(self) -> None:
        error = HTTPError("https://example.com", 404, "missing", Message(), None)
        self.assertFalse(http_request_policy.should_retry(error))


if __name__ == "__main__":
    unittest.main()
