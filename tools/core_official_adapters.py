"""Install dedicated first-party newsroom adapters for core research companies.

The generic official-company crawler remains the broad fallback.  This module
adds a small high-priority set to the crawler's native `NewsSource` path so core
companies receive predictable link scopes, date parsing and bounded direct
requests before the generic discovery layer runs.
"""

from __future__ import annotations

from typing import Any


CORE_OFFICIAL_SOURCES = (
    {
        "id": "google-deepmind",
        "name": "Google DeepMind",
        "index_url": "https://deepmind.google/discover/blog/",
        "company": "Google DeepMind",
        "company_slug": "google",
        "region": "美国",
        "sector": "AI / AGI",
        "path_prefixes": ("/discover/blog/",),
    },
    {
        "id": "bytedance",
        "name": "字节跳动",
        "index_url": "https://www.bytedance.com/zh/news",
        "company": "字节跳动",
        "company_slug": "bytedance",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/zh/news/",),
    },
    {
        "id": "doubao",
        "name": "豆包 Seed",
        "index_url": "https://seed.bytedance.com/zh/blog",
        "company": "豆包",
        "company_slug": "doubao",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/zh/blog/",),
    },
    {
        "id": "volcengine",
        "name": "火山引擎",
        "index_url": "https://www.volcengine.com/news",
        "company": "火山引擎",
        "company_slug": "volcengine",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/news/detail/",),
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "index_url": "https://api-docs.deepseek.com/news/",
        "company": "DeepSeek",
        "company_slug": "deepseek",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/news/",),
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "index_url": "https://www.minimaxi.com/news",
        "company": "MiniMax",
        "company_slug": "minimax",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/news/",),
    },
    {
        "id": "zhipu-ai",
        "name": "智谱AI",
        "index_url": "https://www.zhipuai.cn/zh/news",
        "company": "智谱AI",
        "company_slug": "zhipu-ai",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/zh/news/",),
    },
    {
        "id": "unitree",
        "name": "宇树科技",
        "index_url": "https://www.unitree.com/news/",
        "company": "宇树科技",
        "company_slug": "unitree",
        "region": "中国",
        "sector": "机器人",
        "path_prefixes": ("/news/",),
    },
    {
        "id": "spacex",
        "name": "SpaceX",
        "index_url": "https://www.spacex.com/updates/",
        "company": "SpaceX",
        "company_slug": "spacex",
        "region": "美国",
        "sector": "商业航天",
        "path_prefixes": ("/updates/",),
    },
    {
        "id": "cerebras",
        "name": "Cerebras Systems",
        "index_url": "https://www.cerebras.ai/blog",
        "company": "Cerebras Systems",
        "company_slug": "cerebras",
        "region": "美国",
        "sector": "半导体",
        "path_prefixes": ("/blog/",),
    },
    {
        "id": "scale-ai",
        "name": "Scale AI",
        "index_url": "https://scale.com/blog",
        "company": "Scale AI",
        "company_slug": "scale-ai",
        "region": "美国",
        "sector": "AI / AGI",
        "path_prefixes": ("/blog/",),
    },
)


def install(crawler: Any) -> None:
    existing = tuple(crawler.NEWS_SOURCES)
    existing_ids = {source.id for source in existing}
    additions = []
    for raw in CORE_OFFICIAL_SOURCES:
        if raw["id"] in existing_ids:
            continue
        additions.append(
            crawler.NewsSource(
                raw["id"],
                raw["name"],
                raw["index_url"],
                raw["company"],
                raw["company_slug"],
                raw["region"],
                raw["sector"],
                tuple(raw["path_prefixes"]),
            )
        )
        existing_ids.add(raw["id"])
    if additions:
        crawler.NEWS_SOURCES = (*existing, *additions)
