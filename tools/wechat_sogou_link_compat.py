"""Compatibility for Sogou WeChat's public result-link signature.

Sogou result pages expose ``/link?url=...`` entries plus a small client-side
``k``/``h`` calculation. This module reproduces that public-page calculation
before following the result. CAPTCHA pages remain terminal failures.
"""

from __future__ import annotations

import random
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PAD_PATTERN = re.compile(
    r"href\.substr\(a\+(\d+)\+parseInt\(['\"](\d+)['\"]\)\+b,1\)",
    flags=re.IGNORECASE,
)


def guarded_result_url(
    result_url: str,
    search_body: str,
    *,
    nonce: int | None = None,
) -> str:
    """Append the public ``k`` and ``h`` values required by Sogou result links."""

    parts = urlsplit(str(result_url or ""))
    if not parts.path.startswith("/link") or "url=" not in parts.query:
        return result_url
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if any(key == "k" for key, _value in query_pairs):
        return result_url
    pads = PAD_PATTERN.findall(search_body or "")
    pair = pads[0] if pads else ()
    marker_position = result_url.find("url=")
    value = int(nonce if nonce is not None else random.randint(1, 100))
    offset = marker_position + value + sum(int(item) for item in pair)
    if marker_position < 0 or offset < 0 or offset >= len(result_url):
        return result_url
    query_pairs.extend([("k", str(value)), ("h", result_url[offset])])
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), "")
    )


def install(index: Any) -> None:
    """Patch Sogou discovery while retaining its session and CAPTCHA circuit breaker."""

    current = index.discover
    if getattr(current, "_sogou_link_signature_compat", False):
        return

    def discover(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        search_url = index.build_search_url(spec)
        search_body = index._request(search_url)
        rows = index.parse_search_results(search_body, search_url)
        resolved = 0
        failures = 0
        for row in rows:
            try:
                result_url = guarded_result_url(row["url"], search_body)
                body = index._request(
                    index._normalized_url(result_url),
                    referer=search_url,
                )
                direct = index.resolve_script_url(body)
            except Exception:
                direct = ""
                failures += 1
            if direct:
                row["directUrl"] = direct
                resolved += 1
        return rows, {
            "provider": "sogou-weixin",
            "query": index._query_term(spec),
            "scanned": len(rows),
            "resolved": resolved,
            "failed": failures,
        }

    setattr(discover, "_sogou_link_signature_compat", True)
    index.discover = discover
