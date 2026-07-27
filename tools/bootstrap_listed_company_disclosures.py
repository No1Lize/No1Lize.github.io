#!/usr/bin/env python3
"""Bootstrap verified exchange documents before the first network refresh."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"

VERIFIED_EVENTS: dict[str, dict[str, Any]] = {
    "cambricon": {
        "slug": "cambricon",
        "name": "寒武纪",
        "listing": {
            "market": "A股",
            "ticker": "688256",
            "exchange": "上海证券交易所",
            "listingRole": "primary",
        },
        "event": {
            "id": "disclosure-cambricon-sse-listing-20200717",
            "companySlug": "cambricon",
            "companyName": "寒武纪",
            "market": "A股",
            "ticker": "688256",
            "exchange": "上海证券交易所",
            "listingRole": "primary",
            "publishedAt": "2020-07-17",
            "documentType": "招股与上市",
            "title": "关于中科寒武纪科技股份有限公司人民币普通股股票科创板上市交易的公告",
            "summary": "上海证券交易所上市公告确认寒武纪证券代码为688256，并于2020年7月20日起在科创板上市交易。",
            "source": {
                "name": "上海证券交易所",
                "url": "https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20200717_78749873.shtml",
                "level": "监管文件",
            },
            "discoveredVia": "verified-official-bootstrap",
            "fallback": False,
        },
    },
    "horizon-robotics": {
        "slug": "horizon-robotics",
        "name": "地平线机器人",
        "listing": {
            "market": "港股",
            "ticker": "09660",
            "exchange": "香港交易所",
            "listingRole": "primary",
        },
        "event": {
            "id": "disclosure-horizon-hkex-global-offering-20241016",
            "companySlug": "horizon-robotics",
            "companyName": "地平线机器人",
            "market": "港股",
            "ticker": "09660",
            "exchange": "香港交易所",
            "listingRole": "primary",
            "publishedAt": "2024-10-16",
            "documentType": "招股与上市",
            "title": "全球發售",
            "summary": "香港交易所披露易发布地平线机器人全球发售招股章程，文件包含公司业务、管理层、基石投资者、财务资料及募集资金用途。",
            "source": {
                "name": "香港交易所披露易",
                "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/1016/2024101600023_c.htm",
                "level": "监管文件",
            },
            "discoveredVia": "verified-official-bootstrap",
            "fallback": False,
        },
    },
}


def main() -> int:
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"schemaVersion": 1, "companies": {}, "sourceStatus": []}
    companies = payload.get("companies")
    if not isinstance(companies, dict):
        companies = {}
    changed = False
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    for slug, seed in VERIFIED_EVENTS.items():
        company = companies.get(slug)
        if not isinstance(company, dict):
            company = {
                "slug": slug,
                "name": seed["name"],
                "updatedAt": now,
                "status": "ok",
                "listings": [seed["listing"]],
                "events": [],
                "officialEventCount": 0,
                "fallbackEventCount": 0,
            }
        events = [event for event in company.get("events", []) if isinstance(event, dict)]
        urls = {
            str(event.get("source", {}).get("url", ""))
            for event in events
            if isinstance(event.get("source"), dict)
        }
        seed_url = seed["event"]["source"]["url"]
        if seed_url not in urls:
            events.append(seed["event"])
            changed = True
        company["events"] = sorted(
            events,
            key=lambda event: (str(event.get("publishedAt", "")), str(event.get("id", ""))),
            reverse=True,
        )
        company["officialEventCount"] = sum(
            not bool(event.get("fallback")) for event in company["events"]
        )
        company["fallbackEventCount"] = sum(
            bool(event.get("fallback")) for event in company["events"]
        )
        company["updatedAt"] = now
        companies[slug] = company
    payload.update(
        {
            "schemaVersion": 1,
            "generatedAt": now,
            "companyCount": len(companies),
            "eventCount": sum(
                len(company.get("events", []))
                for company in companies.values()
                if isinstance(company, dict)
            ),
            "companies": companies,
            "sourceStatus": payload.get("sourceStatus", []),
        }
    )
    if changed or not OUTPUT_PATH.exists():
        OUTPUT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Bootstrapped {len(VERIFIED_EVENTS)} verified exchange documents.")
    else:
        print("Verified exchange bootstrap already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
