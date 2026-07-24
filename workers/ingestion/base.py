import hashlib
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


TRACKING_PARAMETERS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        sorted((key, value) for key, value in parse_qsl(parts.query) if key not in TRACKING_PARAMETERS)
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def fingerprint(title: str, published_at: str, entity: str) -> str:
    value = "|".join((title.strip().casefold(), published_at, entity.strip().casefold()))
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Candidate:
    title: str
    summary: str
    canonical_url: str
    source_name: str
    published_at: datetime
    event_type: str
    region: str
    sector: str
    entity_name: str

    @property
    def content_fingerprint(self) -> str:
        return fingerprint(self.title, self.published_at.date().isoformat(), self.entity_name)


class SourceAdapter:
    name = "base"
    allowed_hosts: frozenset[str] = frozenset()

    def validate_url(self, url: str) -> None:
        host = urlsplit(url).hostname
        if host not in self.allowed_hosts:
            raise ValueError(f"Host is not allowlisted for {self.name}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def fetch(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        self.validate_url(url)
        response = await client.get(url, follow_redirects=True, timeout=20)
        response.raise_for_status()
        return response

    async def collect(self, client: httpx.AsyncClient) -> list[Candidate]:
        raise NotImplementedError
