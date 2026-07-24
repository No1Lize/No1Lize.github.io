from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from ..base import Candidate, SourceAdapter, normalize_url


class OpenAINewsAdapter(SourceAdapter):
    name = "openai"
    allowed_hosts = frozenset({"openai.com", "www.openai.com"})
    urls = (
        "https://openai.com/index/accelerating-the-next-phase-ai/",
        "https://openai.com/index/announcing-the-stargate-project/",
    )

    async def collect(self, client: httpx.AsyncClient) -> list[Candidate]:
        candidates: list[Candidate] = []
        for url in self.urls:
            response = await self.fetch(client, url)
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.find("h1")
            published = soup.find("time")
            description = soup.find("meta", attrs={"name": "description"})
            if not title:
                continue
            date_value = (
                published.get("datetime")
                if published and published.get("datetime")
                else "2026-03-31" if "accelerating" in url else "2025-01-21"
            )
            candidates.append(
                Candidate(
                    title=title.get_text(" ", strip=True),
                    summary=description.get("content", "") if description else "",
                    canonical_url=normalize_url(url),
                    source_name="OpenAI",
                    published_at=datetime.fromisoformat(str(date_value).replace("Z", "+00:00")),
                    event_type="融资" if "accelerating" in url else "产业投资",
                    region="美国",
                    sector="AI / AGI",
                    entity_name="OpenAI",
                )
            )
        return candidates
