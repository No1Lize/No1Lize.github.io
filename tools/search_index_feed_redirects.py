"""Resolve search-index RSS wrappers before applying destination-host allowlists.

Google News RSS exposes article wrapper URLs on ``news.google.com``. Sources such
as the per-track Toutiao route intentionally require a final ``toutiao.com`` URL,
so filtering the wrapper host first drops every valid result. This adapter decodes
only Google News article wrappers, verifies the final host against the source
allowlist, and then delegates article construction to the standard crawler.
"""

from __future__ import annotations

import base64
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
MAX_RESOLUTIONS_PER_FEED = 32
MIN_REQUEST_INTERVAL_SECONDS = 0.12
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
        or hostname.endswith(
            f".{str(host).casefold().removeprefix('www.')}"
        )
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


def _batch_request(article_id: str, user_agent: str, timeout: int = 14) -> str:
    global _NEXT_REQUEST_AT
    request_payload = (
        '[[["Fbv4je","[\\"garturlreq\\",[[\\"en-US\\",\\"US\\",'
        '[\\"FINANCE_TOP_INDICES\\",\\"WEB_TEST_1_0_0\\"],null,null,1,1,'
        '\\"US:en\\",null,180,null,null,null,null,null,0,null,null,'
        '[1608992183,723341000]],\\"en-US\\",\\"US\\",1,[2,3,4,8],1,0,'
        '\\"655000234\\",0,0,null,0],\\"'
        + article_id
        + '\\"]",null,"generic"]]]'
    )
    with _LOCK:
        wait = _NEXT_REQUEST_AT - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _NEXT_REQUEST_AT = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS
    request = Request(
        GOOGLE_BATCH_ENDPOINT,
        data=urlencode({"f.req": request_payload}).encode("utf-8"),
        headers={
            "User-Agent": user_agent,
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Accept": "*/*",
            "Referer": "https://news.google.com/",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(_RESPONSE_LIMIT + 1)
        if len(body) > _RESPONSE_LIMIT:
            return ""
        text = body.decode("utf-8", errors="replace")
    marker = '[\\"garturlres\\",\\"'
    if marker not in text:
        return ""
    fragment = text.split(marker, 1)[1].split('\\",', 1)[0]
    try:
        return str(json.loads(f'"{fragment}"'))
    except json.JSONDecodeError:
        return fragment.replace("\\/", "/").replace("\\u0026", "&")


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
        max(4, int(spec.get("maxItems", 8)) * 4),
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
