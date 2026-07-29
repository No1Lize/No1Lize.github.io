#!/usr/bin/env python3
"""Install the shared request policy into the legacy standard-library crawler."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from . import http_request_policy
except ImportError:
    import http_request_policy


def install(crawler) -> None:
    original = crawler.fetch_text
    if getattr(original, "_source_aware_http_policy", False):
        return

    def fetch_text(
        url: str,
        user_agent: str,
        timeout: int = crawler.REQUEST_TIMEOUT,
        attempts: int = crawler.REQUEST_ATTEMPTS,
    ) -> str:
        policy, headers = http_request_policy.request_headers(
            url,
            user_agent,
            accept="text/html,application/json,application/xml,text/xml;q=0.9,*/*;q=0.8",
        )
        last_error: Exception | None = None
        for attempt in range(max(1, attempts)):
            http_request_policy.wait_for_request_slot(url, policy)
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=timeout) as response:
                    return response.read().decode(
                        response.headers.get_content_charset() or "utf-8",
                        errors="replace",
                    )
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if not http_request_policy.should_retry(exc) or attempt + 1 >= attempts:
                    break
                time.sleep(http_request_policy.retry_delay(exc, attempt, policy))
        assert last_error is not None
        raise last_error

    setattr(fetch_text, "_source_aware_http_policy", True)
    crawler.fetch_text = fetch_text
