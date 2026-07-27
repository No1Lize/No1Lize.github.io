"""Recognize current public Sogou result redirects to original WeChat articles.

The base parser handles the historical ``url +=`` script. Current public result
pages can expose the same destination through escaped article HTML, location
assignments, JSON fields, or a meta refresh. This compatibility layer only accepts
original ``mp.weixin.qq.com/s`` URLs and never attempts to bypass CAPTCHA pages.
"""

from __future__ import annotations

import html
import re
from typing import Any, Iterable
from urllib.parse import unquote, urljoin, urlsplit

_DIRECT_PATTERN = re.compile(
    r"https?://mp\.weixin\.qq\.com/s(?:\?|/)[^'\"<>\s]+",
    flags=re.IGNORECASE,
)
_PATTERNS = (
    re.compile(
        r"(?:window\.|top\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:window\.|top\.)?location\.(?:replace|assign)\(\s*['\"]([^'\"]+)['\"]",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"<meta[^>]+http-equiv=['\"]?refresh['\"]?[^>]+content=['\"][^'\"]*url\s*=\s*([^'\";>]+)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"['\"](?:url|jump_url|redirect_url|target_url)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"href\s*=\s*['\"]([^'\"]*mp\.weixin\.qq\.com/s(?:\?|/)[^'\"]*)['\"]",
        flags=re.IGNORECASE,
    ),
)


def _decode(value: str) -> str:
    text = html.unescape(str(value or ""))
    replacements = {
        "\\/": "/",
        "\\x26": "&",
        "\\u0026": "&",
        "\\u003d": "=",
        "\\u003D": "=",
        "\\u002f": "/",
        "\\u002F": "/",
        "\\u003a": ":",
        "\\u003A": ":",
        "\\u0025": "%",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    for _ in range(2):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    return text.strip().strip("'\"")


def _is_original(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    path = parts.path.rstrip("/")
    return (
        (parts.hostname or "").casefold() == "mp.weixin.qq.com"
        and (path == "/s" or path.startswith("/s/"))
    )


def _candidates(body: str) -> Iterable[str]:
    decoded_body = _decode(body)
    for match in _DIRECT_PATTERN.finditer(decoded_body):
        yield match.group(0)
    for pattern in _PATTERNS:
        for match in pattern.finditer(decoded_body):
            yield match.group(1)


def resolve_current_redirect(body: str, base_url: str = "") -> str:
    for raw in _candidates(body or ""):
        candidate = _decode(raw)
        if candidate.startswith("//"):
            candidate = f"https:{candidate}"
        elif candidate.startswith("/") and base_url:
            candidate = urljoin(base_url, candidate)
        if _is_original(candidate):
            return candidate
    return ""


def install(index: Any) -> None:
    """Extend the narrow script resolver while preserving all existing guards."""

    original = index.resolve_script_url
    if getattr(original, "_current_sogou_redirects", False):
        return

    def resolve_script_url(body: str) -> str:
        return original(body) or resolve_current_redirect(body)

    setattr(resolve_script_url, "_current_sogou_redirects", True)
    index.resolve_script_url = resolve_script_url
