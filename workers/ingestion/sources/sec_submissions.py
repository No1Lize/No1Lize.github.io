from datetime import UTC, datetime

import httpx

from backend.app.config import get_settings
from ..base import Candidate, SourceAdapter, normalize_url


class SecSubmissionsAdapter(SourceAdapter):
    name = "sec"
    allowed_hosts = frozenset({"data.sec.gov"})
    companies = {
        "0001824920": ("IonQ", "量子计算"),
        "0001819994": ("Rocket Lab", "商业航天"),
        "0001838359": ("Rigetti Computing", "量子计算"),
    }

    async def collect(self, client: httpx.AsyncClient) -> list[Candidate]:
        candidates: list[Candidate] = []
        headers = {"User-Agent": get_settings().sec_user_agent, "Accept-Encoding": "gzip"}
        for cik, (company, sector) in self.companies.items():
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            self.validate_url(url)
            response = await client.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            recent = response.json().get("filings", {}).get("recent", {})
            for index, form in enumerate(recent.get("form", [])[:10]):
                if form not in {"10-K", "10-Q", "8-K", "S-1", "424B4"}:
                    continue
                accession = recent["accessionNumber"][index].replace("-", "")
                primary = recent["primaryDocument"][index]
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary}"
                )
                candidates.append(
                    Candidate(
                        title=f"{company} 提交 {form}",
                        summary="SEC EDGAR 监管文件增量记录。",
                        canonical_url=normalize_url(filing_url),
                        source_name="SEC EDGAR",
                        published_at=datetime.fromisoformat(
                            recent["filingDate"][index]
                        ).replace(tzinfo=UTC),
                        event_type="监管文件",
                        region="美国",
                        sector=sector,
                        entity_name=company,
                    )
                )
        return candidates
