"""Resolve search-index RSS wrappers before applying destination-host allowlists.

Google News RSS exposes article wrapper URLs on ``news.google.com``. Sources such
as the per-track Toutiao route intentionally require a final ``toutiao.com`` URL,
so filtering the wrapper host first drops every valid result. This adapter decodes
only Google News article wrappers, verifies the final host against the source
allowlist, and then delegates article construction to the standard crawler.
"""

from __future__ import annotations

import base64
import html
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Sequence
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

GOOGLE_NEWS_HOST = "news.google.com"
GOOGLE_BATCH_ENDPOINT = (
    "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je"
)
MAX_RESOLUTIONS_PER_FEED = 16
MIN_REQUEST_INTERVAL_SECONDS = 0.18
_RESPONSE_LIMIT = 1_000_000
_CACHE: dict[str, str] = {}
_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0


def _host_allowed(url: str, allowed_hosts: Sequence[str]) -> bool:
    hostname = (urlsplit(str(url or "")).hostname or "").casefold().removeprefix(
        "www."
    )
    return bool(hostname) and any(
        hostname == str(host).casefold().removeprefix("www.")
        or hostname.endswith(f".{str(host).casefold().removeprefix('www.')}")
        for host in allowed_hosts
        if str(host).strip()
    )


def _google_article_id(url: str) -> str:
    parts = urlsplit(str(url or ""))
    if (parts.hostname or "").casefold() != GOOGLE_NEWS_HOST:
        return ""
    path = [part for part in parts.path.split("/") if part]
    if len(path) < 2 or path[-2] not in {"articles", "read"}:
        return ""
    value = path[-1]
    return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else ""


def _legacy_decoded_url(article_id: str) -> str:
    """Recover old Google News IDs that embedded the destination URL directly."""

    try:
        raw = base64.urlsafe_b64decode(article_id + "=" * (-len(article_id) % 4))
    except (ValueError, TypeError):
        return ""
    match = re.search(rb"https?://[^\x00-\x20\x7f]+", raw)
    if not match:
        return ""
    return match.group(0).decode("utf-8", errors="ignore")


def _rate_wait() -> None:
    global _NEXT_REQUEST_AT
    with _LOCK:
        wait = _NEXT_REQUEST_AT - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _NEXT_REQUEST_AT = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS


def _request_text(
    url: str,
    user_agent: str,
    *,
    data: bytes | None = None,
    timeout: int = 14,
) -> str:
    _rate_wait()
    request = Request(
        url,
        data=data,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Referer": "https://news.google.com/",
        },
        method="POST" if data is not None else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(_RESPONSE_LIMIT + 1)
        if len(payload) > _RESPONSE_LIMIT:
            return ""
        charset = response.headers.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")


def _decoding_parameters(
    article_id: str,
    user_agent: str,
) -> tuple[str, str]:
    """Read Google's current public signature and timestamp parameters."""

    page = _request_text(
        f"https://news.google.com/articles/{article_id}",
        user_agent,
    )
    signature = re.search(r'data-n-a-sg=["\']([^"\']+)', page)
    timestamp = re.search(r'data-n-a-ts=["\']([^"\']+)', page)
    if not signature or not timestamp:
        return "", ""
    return html.unescape(signature.group(1)), html.unescape(timestamp.group(1))


def _unsigned_request_payload(article_id: str) -> str:
    return (
        '[[["Fbv4je","[\\"garturlreq\\",[[\\"en-US\\",\\"US\\",'
        '[\\"FINANCE_TOP_INDICES\\",\\"WEB_TEST_1_0_0\\"],null,null,1,1,'
        '\\"US:en\\",null,180,null,null,null,null,null,0,null,null,'
        '[1608992183,723341000]],\\"en-US\\",\\"US\\",1,[2,3,4,8],1,0,'
        '\\"655000234\\",0,0,null,0],\\"'
        + article_id
        + '\\"]",null,"generic"]]]'
    )


def _signed_request_payload(article_id: str, timestamp: str, signature: str) -> str:
    request_body = [
        "garturlreq",
        [
            [
                "X",
                "X",
                ["X", "X"],
                None,
                None,
                1,
                1,
                "US:en",
                None,
                1,
                None,
                None,
                None,
                None,
                None,
                0,
                1,
            ],
            "X",
            "X",
            1,
            [1, 1, 1],
            1,
            1,
            None,
            0,
            0,
            None,
            0,
        ],
        article_id,
        int(timestamp),
        signature,
    ]
    return json.dumps(
        [[["Fbv4je", json.dumps(request_body, separators=(",", ":")), None, "generic"]]],
        separators=(",", ":"),
    )


def _parse_batch_response(text: str) -> str:
    marker = '[\\"garturlres\\",\\"'
    if marker in text:
        fragment = text.split(marker, 1)[1].split('\\",', 1)[0]
        try:
            return str(json.loads(f'"{fragment}"'))
        except json.JSONDecodeError:
            return fragment.replace("\\/", "/").replace("\\u0026", "&")

    # Some responses expose the inner payload as a JSON string without the same
    # escape depth. Parse each non-preamble line conservatively.
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            rows = json.loads(line)
        except json.JSONDecodeError:
            continue
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 3 or row[1] != "Fbv4je":
                continue
            try:
                inner = json.loads(row[2])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(inner, list) and len(inner) > 1 and inner[0] == "garturlres":
                return str(inner[1])
    return ""


def _post_batch(payload: str, user_agent: str, timeout: int = 14) -> str:
    text = _request_text(
        GOOGLE_BATCH_ENDPOINT,
        user_agent,
        data=urlencode({"f.req": payload}).encode("utf-8"),
        timeout=timeout,
    )
    return _parse_batch_response(text)


def _batch_request(article_id: str, user_agent: str, timeout: int = 14) -> str:
    """Decode with current signed parameters, then retain the legacy fallback."""

    try:
        signature, timestamp = _decoding_parameters(article_id, user_agent)
    except Exception:  # noqa: BLE001 - unsigned compatibility remains available.
        signature, timestamp = "", ""
    if signature and timestamp.isdigit():
        try:
            resolved = _post_batch(
                _signed_request_payload(article_id, timestamp, signature),
                user_agent,
                timeout,
            )
            if resolved:
                return resolved
        except Exception:  # noqa: BLE001 - try the older public request shape.
            pass
    return _post_batch(_unsigned_request_payload(article_id), user_agent, timeout)


def resolve_google_news_url(
    url: str,
    allowed_hosts: Sequence[str],
    user_agent: str,
) -> str:
    """Return a verified publisher URL or an empty string."""

    if _host_allowed(url, allowed_hosts):
        return url
    article_id = _google_article_id(url)
    if not article_id:
        return ""
    cache_key = f"{article_id}|{'|'.join(sorted(str(v) for v in allowed_hosts))}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    candidates = [_legacy_decoded_url(article_id)]
    try:
        candidates.append(_batch_request(article_id, user_agent))
    except Exception:  # noqa: BLE001 - unresolved wrappers are skipped, not trusted.
        pass
    resolved = next(
        (candidate for candidate in candidates if _host_allowed(candidate, allowed_hosts)),
        "",
    )
    _CACHE[cache_key] = resolved
    return resolved


def _resolved_feed_body(
    body: str,
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
) -> str:
    allowed_hosts = tuple(str(value) for value in spec.get("allowedHosts", []))
    if not allowed_hosts or GOOGLE_NEWS_HOST not in str(spec.get("url", "")):
        return body
    root = ET.fromstring(body)
    resolutions = 0
    max_candidates = min(
        MAX_RESOLUTIONS_PER_FEED,
        max(4, int(spec.get("maxItems", 8)) * 2),
    )
    for node in root.iter():
        if crawler._xml_local(node.tag) not in {"item", "entry"}:
            continue
        link_node = next(
            (
                child
                for child in node.iter()
                if crawler._xml_local(child.tag) == "link"
                and (
                    str(child.attrib.get("href", "")).strip()
                    or str(child.text or "").strip()
                )
            ),
            None,
        )
        if link_node is None:
            continue
        raw_url = str(link_node.attrib.get("href") or link_node.text or "").strip()
        if _host_allowed(raw_url, allowed_hosts):
            continue
        title = crawler.clean_title(crawler._xml_text(node, ("title",)))
        summary = crawler.strip_html(
            crawler._xml_text(node, ("description", "summary", "content"))
        )
        if not crawler._matches_keywords(
            title,
            summary,
            spec.get("keywords", []),
            title_only=bool(spec.get("strictTitleKeywords")),
        ):
            continue
        if resolutions >= max_candidates:
            break
        resolutions += 1
        resolved = resolve_google_news_url(raw_url, allowed_hosts, user_agent)
        if not resolved:
            continue
        if link_node.attrib.get("href") is not None:
            link_node.attrib["href"] = resolved
        else:
            link_node.text = resolved
    return ET.tostring(root, encoding="unicode")


def install(crawler: Any) -> None:
    """Patch RSS parsing without changing ordinary feeds or unrestricted searches."""

    original = crawler.parse_feed_items
    if getattr(original, "_search_index_redirects", False):
        return

    def parse_feed_items(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
        rewritten = _resolved_feed_body(
            body,
            spec,
            crawler.DEFAULT_USER_AGENT,
            crawler,
        )
        return original(rewritten, spec)

    setattr(parse_feed_items, "_search_index_redirects", True)
    crawler.parse_feed_items = parse_feed_items
