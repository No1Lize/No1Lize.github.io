"""Rate-limit protection for public X timeline syndication requests."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError

MIN_REQUEST_INTERVAL_SECONDS = 2.0
FIRST_429_BACKOFF_SECONDS = 8.0
CIRCUIT_BREAKER_SECONDS = 180.0

_lock = threading.Lock()
_next_request_at = 0.0
_blocked_until = 0.0


def _is_rate_limit(error: BaseException) -> bool:
    return isinstance(error, HTTPError) and error.code == 429


def install(crawler: Any) -> None:
    """Install serialized X fetching with one delayed retry and a circuit breaker.

    The crawler's batch replacement logic already preserves the previous
    snapshot for sources whose status is ``error``. Raising an explicit error
    after the circuit opens therefore prevents request storms without deleting
    the last successful X articles.
    """

    original: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = (
        crawler.crawl_x_profile
    )
    if getattr(original, "_x_rate_limited", False):
        return

    def guarded_profile(
        spec: dict[str, Any], user_agent: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        global _next_request_at, _blocked_until

        with _lock:
            now = time.monotonic()
            if now < _blocked_until:
                remaining = max(1, int(_blocked_until - now))
                raise RuntimeError(
                    f"X rate-limit cooldown active ({remaining}s); previous snapshot retained"
                )

            wait = _next_request_at - now
            if wait > 0:
                time.sleep(wait)

            try:
                result = original(spec, user_agent)
            except Exception as exc:
                if not _is_rate_limit(exc):
                    _next_request_at = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS
                    raise

                time.sleep(FIRST_429_BACKOFF_SECONDS)
                try:
                    result = original(spec, user_agent)
                except Exception as retry_error:
                    if _is_rate_limit(retry_error):
                        _blocked_until = time.monotonic() + CIRCUIT_BREAKER_SECONDS
                        _next_request_at = _blocked_until
                        raise RuntimeError(
                            "X returned HTTP 429 after delayed retry; "
                            "circuit opened and previous snapshot retained"
                        ) from retry_error
                    _next_request_at = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS
                    raise

            _next_request_at = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS
            return result

    setattr(guarded_profile, "_x_rate_limited", True)
    crawler.crawl_x_profile = guarded_profile
