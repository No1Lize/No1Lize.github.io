#!/usr/bin/env python3
"""Shared source-aware request throttling and retry policy.

The crawler runs from GitHub-hosted runners against many unrelated public
sources.  This module keeps the implementation dependency-free while avoiding
bursty requests to sensitive hosts, respecting ``Retry-After`` and retaining a
transparent project identity in every User-Agent.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit

PROJECT_IDENTITY = "LizeRoadOne/3.0 (+https://github.com/VCIQ/VCIQ.github.io)"
DESKTOP_COMPAT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 "
    f"{PROJECT_IDENTITY}"
)
MOBILE_COMPAT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36 "
    f"{PROJECT_IDENTITY}"
)
RETRYABLE_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RequestPolicy:
    user_agent: str
    min_interval: float = 0.0
    jitter: float = 0.08
    base_backoff: float = 0.6
    max_backoff: float = 30.0
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.7"


_HOST_LOCKS: dict[str, threading.Lock] = {}
_HOST_LOCKS_GUARD = threading.Lock()
_LAST_REQUEST_AT: dict[str, float] = {}


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)


def policy_for_url(url: str, default_user_agent: str) -> RequestPolicy:
    """Return a conservative policy tailored to the destination host."""

    host = (urlsplit(url).hostname or "").casefold()
    if _host_matches(host, ("sec.gov",)):
        # SEC requires an identifying User-Agent supplied by the caller.
        return RequestPolicy(default_user_agent, min_interval=0.12, jitter=0.03)
    if _host_matches(host, ("weixin.sogou.com", "mp.weixin.qq.com", "sogou.com")):
        return RequestPolicy(MOBILE_COMPAT_USER_AGENT, min_interval=0.45, jitter=0.18)
    if _host_matches(host, ("x.com", "twitter.com", "syndication.twitter.com")):
        return RequestPolicy(DESKTOP_COMPAT_USER_AGENT, min_interval=0.55, jitter=0.20)
    if _host_matches(host, ("eastmoney.com", "dfcfw.com")):
        return RequestPolicy(DESKTOP_COMPAT_USER_AGENT, min_interval=0.12, jitter=0.06)
    if _host_matches(host, ("sina.com.cn", "sina.cn")):
        return RequestPolicy(DESKTOP_COMPAT_USER_AGENT, min_interval=0.10, jitter=0.05)
    return RequestPolicy(default_user_agent)


def request_headers(
    url: str,
    default_user_agent: str,
    *,
    accept: str,
    extra: dict[str, str] | None = None,
) -> tuple[RequestPolicy, dict[str, str]]:
    policy = policy_for_url(url, default_user_agent)
    headers = {
        "User-Agent": policy.user_agent,
        "Accept": accept,
        "Accept-Language": policy.accept_language,
        "Accept-Encoding": "identity",
    }
    if extra:
        headers.update({key: value for key, value in extra.items() if value})
    return policy, headers


def _host_lock(host: str) -> threading.Lock:
    with _HOST_LOCKS_GUARD:
        return _HOST_LOCKS.setdefault(host, threading.Lock())


def wait_for_request_slot(
    url: str,
    policy: RequestPolicy,
    *,
    sleep: callable = time.sleep,
    monotonic: callable = time.monotonic,
    uniform: callable = random.uniform,
) -> None:
    """Space request starts per host without serializing response downloads."""

    host = (urlsplit(url).hostname or "").casefold()
    if not host:
        return
    with _host_lock(host):
        now = monotonic()
        remaining = policy.min_interval - (now - _LAST_REQUEST_AT.get(host, 0.0))
        if remaining > 0:
            sleep(remaining)
        if policy.jitter > 0:
            sleep(uniform(0.0, policy.jitter))
        _LAST_REQUEST_AT[host] = monotonic()


def should_retry(error: BaseException) -> bool:
    return not isinstance(error, HTTPError) or error.code in RETRYABLE_HTTP_STATUSES


def _retry_after_seconds(error: BaseException, now: datetime | None = None) -> float | None:
    if not isinstance(error, HTTPError) or not error.headers:
        return None
    raw = str(error.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(raw)
        if target.tzinfo is None:
            target = target.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        return max(0.0, (target - current).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def retry_delay(
    error: BaseException,
    attempt: int,
    policy: RequestPolicy,
    *,
    now: datetime | None = None,
) -> float:
    """Return a bounded exponential delay, honoring Retry-After when present."""

    retry_after = _retry_after_seconds(error, now=now)
    exponential = policy.base_backoff * (2**max(0, attempt))
    delay = max(exponential, retry_after or 0.0)
    return min(policy.max_backoff, delay)
