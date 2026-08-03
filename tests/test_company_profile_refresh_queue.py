from __future__ import annotations

import unittest
from datetime import UTC, datetime

from tools.company_profile_refresh_queue import (
    build_queue,
    mark_processed_events,
    validate_queue,
)


NOW = datetime(2026, 8, 3, 15, 0, tzinfo=UTC)
COMPANIES = {"openai": "OpenAI", "anthropic": "Anthropic", "spacex": "SpaceX"}


def article(
    article_id: str,
    slug: str,
    event_type: str,
    *,
    published_at: str = "2026-08-03",
    importance: int = 90,
    source_id: str = "source-a",
    level: str = "媒体报道",
):
    return {
        "id": article_id,
        "title": f"{slug} {event_type}",
        "summary": "公开事件摘要。",
        "type": event_type,
        "companySlug": slug,
        "companySlugs": [slug],
        "publishedAt": published_at,
        "importance": importance,
        "sourceId": source_id,
        "source": {
            "name": source_id,
            "url": f"https://{source_id}.example/{article_id}",
            "level": level,
        },
    }


class CompanyProfileRefreshQueueTests(unittest.TestCase):
    def test_high_signal_event_enters_bounded_selection(self):
        payload = {
            "generatedAt": NOW.isoformat(),
            "articles": [
                article("funding", "openai", "融资"),
                article("ordinary", "anthropic", "公司动态", importance=60),
            ],
        }
        queue = build_queue(
            payload,
            {"companies": {}},
            COMPANIES,
            now=NOW,
            select_limit=10,
        )
        self.assertEqual(queue["selectedSlugs"], ["openai"])
        self.assertEqual(queue["pendingCount"], 1)
        self.assertEqual(queue["entries"][0]["status"], "selected")

    def test_same_day_event_remains_due_after_morning_profile_refresh(self):
        queue = build_queue(
            {
                "generatedAt": NOW.isoformat(),
                "articles": [article("product", "anthropic", "产品发布")],
            },
            {"companies": {"anthropic": {"updatedAt": "2026-08-03T01:15:00Z"}}},
            COMPANIES,
            now=NOW,
        )
        self.assertEqual(queue["selectedSlugs"], ["anthropic"])

    def test_later_calendar_day_profile_covers_older_event(self):
        queue = build_queue(
            {
                "generatedAt": NOW.isoformat(),
                "articles": [
                    article(
                        "older",
                        "spacex",
                        "技术突破",
                        published_at="2026-08-02",
                    )
                ],
            },
            {"companies": {"spacex": {"updatedAt": "2026-08-03T01:15:00Z"}}},
            COMPANIES,
            now=NOW,
        )
        self.assertEqual(queue["pendingCount"], 0)

    def test_processed_event_cannot_trigger_again(self):
        first = build_queue(
            {
                "generatedAt": NOW.isoformat(),
                "articles": [article("ipo", "openai", "IPO")],
            },
            {"companies": {}},
            COMPANIES,
            now=NOW,
        )
        processed = mark_processed_events(first, ["openai"], now=NOW)
        second = build_queue(
            {
                "generatedAt": NOW.isoformat(),
                "articles": [article("ipo", "openai", "IPO")],
            },
            {"companies": {}},
            COMPANIES,
            first,
            now=NOW,
            processed_events=processed,
        )
        self.assertEqual(second["pendingCount"], 0)
        self.assertEqual(len(second["processedEvents"]), 1)

    def test_priority_and_selection_limit_are_deterministic(self):
        payload = {
            "generatedAt": NOW.isoformat(),
            "articles": [
                article("product", "anthropic", "产品发布", importance=70),
                article("merger", "spacex", "并购", importance=95),
                article("funding", "openai", "融资", importance=90),
            ],
        }
        queue = build_queue(
            payload,
            {"companies": {}},
            COMPANIES,
            now=NOW,
            select_limit=2,
        )
        self.assertEqual(queue["selectedSlugs"], ["spacex", "openai"])
        self.assertEqual(queue["entries"][2]["status"], "pending")
        self.assertEqual(validate_queue(queue, set(COMPANIES)), [])


if __name__ == "__main__":
    unittest.main()
