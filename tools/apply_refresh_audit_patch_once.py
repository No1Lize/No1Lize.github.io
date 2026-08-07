from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"missing replacement anchor in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


# 1. Preserve source-crawl audit and tracking metadata whenever the core crawler
# rewrites articles.json. Derived retention metadata is intentionally rebuilt by
# snapshot_retention.py instead of being copied blindly.
replace_once(
    "tools/crawl_articles.py",
    '''    payload = {
        "schemaVersion": 3,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "articleCount": len(articles),
        "articles": articles,
        "companyFacts": next_company_facts,
        "sourceStatus": next_source_status,
        "qualityGate": next_quality_gate,
    }
''',
    '''    preserved_metadata = {
        key: previous_payload[key]
        for key in (
            "refreshAudit",
            "trackingConfigHash",
            "trackingEnrichedAt",
            "trackCoverage",
        )
        if key in previous_payload
    }
    payload = {
        **preserved_metadata,
        "schemaVersion": 3,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "articleCount": len(articles),
        "articles": articles,
        "companyFacts": next_company_facts,
        "sourceStatus": next_source_status,
        "qualityGate": next_quality_gate,
    }
''',
)

# 2. Make due scheduling depend on the last real news crawl, never on a generic
# generatedAt that can be advanced by tracking-only or other derived rewrites.
write(
    "tools/frequent_refresh_due.py",
    r'''
    #!/usr/bin/env python3
    """Decide whether the lightweight public-intelligence crawl is actually due."""

    from __future__ import annotations

    import json
    import os
    from datetime import UTC, datetime
    from pathlib import Path
    from typing import Any

    ROOT = Path(__file__).resolve().parents[1]
    ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
    MIN_CRAWL_AGE_MINUTES = 90


    def _parse_timestamp(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)


    def last_news_crawl_at(payload: dict[str, Any]) -> str:
        audit = payload.get("refreshAudit")
        if not isinstance(audit, dict):
            return ""
        explicit = str(audit.get("lastNewsCrawlAt") or "").strip()
        if explicit:
            return explicit

        # Backward-compatible fallback for snapshots produced before the
        # dedicated source-crawl clock existed. Only a completed full/frequent
        # pipeline can establish freshness; generic generatedAt is deliberately
        # ignored because derived-data jobs also change it.
        if audit.get("pipelineCompleted") is not True:
            return ""
        if str(audit.get("mode") or "") not in {"full", "frequent"}:
            return ""
        stages = audit.get("stages")
        if isinstance(stages, list) and stages and "core-and-tracking-sources" not in stages:
            return ""
        return str(audit.get("completedAt") or "").strip()


    def evaluate_due(
        payload: dict[str, Any],
        *,
        event_name: str,
        now: datetime | None = None,
        min_age_minutes: int = MIN_CRAWL_AGE_MINUTES,
    ) -> dict[str, Any]:
        raw = last_news_crawl_at(payload)
        if event_name == "workflow_dispatch":
            return {
                "due": True,
                "ageMinutes": 0,
                "lastNewsCrawlAt": raw,
                "reason": "manual-dispatch",
            }

        last = _parse_timestamp(raw)
        if last is None:
            return {
                "due": True,
                "ageMinutes": -1,
                "lastNewsCrawlAt": raw,
                "reason": "missing-news-crawl-audit",
            }

        current = (now or datetime.now(UTC)).astimezone(UTC)
        age_minutes = max(0, int((current - last).total_seconds() // 60))
        return {
            "due": age_minutes >= min_age_minutes,
            "ageMinutes": age_minutes,
            "lastNewsCrawlAt": raw,
            "reason": "age-threshold",
        }


    def main() -> int:
        payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit("article snapshot must be an object")
        result = evaluate_due(payload, event_name=os.environ.get("EVENT_NAME", ""))
        print(json.dumps(result, ensure_ascii=False))
        output_path = os.environ.get("GITHUB_OUTPUT")
        if output_path:
            with open(output_path, "a", encoding="utf-8") as output:
                output.write(f"due={str(result['due']).lower()}\n")
                output.write(f"age_minutes={result['ageMinutes']}\n")
                output.write(f"last_news_crawl_at={result['lastNewsCrawlAt']}\n")
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ''',
)

# 3. Every successful source crawl stamps an explicit news-crawl clock.
for path in ("tools/finalize_frequent_refresh.py", "tools/finalize_full_refresh.py"):
    replace_once(
        path,
        '        "completedAt": completed_at,\n        "localDate": local_date,\n',
        '        "completedAt": completed_at,\n        "lastNewsCrawlAt": completed_at,\n        "localDate": local_date,\n',
    )

replace_once(
    "lib/snapshot-freshness.ts",
    '  completedAt?: string;\n  localDate?: string;\n',
    '  completedAt?: string;\n  lastNewsCrawlAt?: string;\n  localDate?: string;\n',
)

# 4. Frequent workflow: use the dedicated due helper, persist audit-only crawls,
# and explicitly dispatch Pages after bot-authored data commits.
workflow = ROOT / ".github" / "workflows" / "frequent-intelligence-refresh.yml"
text = workflow.read_text(encoding="utf-8")
start = text.index("      - name: Skip refresh when the current snapshot is still recent")
end = text.index("      - name: Validate lightweight crawler entry points", start)
text = text[:start] + '''      - name: Check whether a real news crawl is due
        id: due
        env:
          EVENT_NAME: ${{ github.event_name }}
        run: python tools/frequent_refresh_due.py
''' + text[end:]
text = text.replace(
    '            tools/finalize_frequent_refresh.py \\\n',
    '            tools/finalize_frequent_refresh.py \\\n            tools/frequent_refresh_due.py \\\n',
    1,
)
text = text.replace(
    '''          if [ "$SEMANTIC_CHANGED" != "true" ]; then
            echo "No semantic intelligence changes; skipping Git commit and Pages build."
            git restore "${DATA_PATHS[@]}"
            echo "changed=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          python tools/run_pipeline.py finalize \\
''',
    '''          if [ "$SEMANTIC_CHANGED" != "true" ]; then
            echo "No semantic article changes; publishing the completed source-crawl audit."
          fi

          python tools/run_pipeline.py finalize \\
''',
    1,
)
text = text.replace(
    '''          git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}"
          git commit -m "data: refresh public intelligence (two-hour check)"
''',
    '''          git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}"
          if git diff --cached --quiet; then
            echo "No crawl-audit or intelligence changes to publish."
            echo "changed=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          git commit -m "data: refresh public intelligence (two-hour check)"
''',
    1,
)
if "Deploy refreshed snapshot" not in text:
    text = text.rstrip() + '''
      - name: Deploy refreshed snapshot
        if: steps.data-update.outputs.changed == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          echo "A real news crawl was published; deploy the refreshed public snapshot."
          gh workflow run pages.yml --ref main
'''
workflow.write_text(text, encoding="utf-8")

# 5. Full refresh: persist audit-only successful crawls and explicitly hand off
# to entity reconciliation before Pages. This supersedes the stale #197 logic.
scheduled = ROOT / ".github" / "workflows" / "scheduled-sync.yml"
text = scheduled.read_text(encoding="utf-8")
text = text.replace(
    '''          if [ "$SEMANTIC_CHANGED" != "true" ]; then
            echo "No semantic public data changes; skipping Git commit and Pages build."
            echo "changed=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          python tools/run_pipeline.py finalize \\
''',
    '''          if [ "$SEMANTIC_CHANGED" != "true" ]; then
            echo "No semantic public-data changes; publishing the completed full-crawl audit."
          fi

          python tools/run_pipeline.py finalize \\
''',
    1,
)
text = text.replace(
    '''          git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}"
          git commit -m "data: refresh public intelligence with source health"
''',
    '''          git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}"
          if git diff --cached --quiet; then
            echo "No crawl-audit or public-data changes to publish."
            echo "changed=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          git commit -m "data: refresh public intelligence with source health"
''',
    1,
)
if "Continue through entity reconciliation before publication" not in text:
    text = text.rstrip() + '''
      - name: Continue through entity reconciliation before publication
        if: always() && steps.data-update.outcome == 'success'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          echo "Full refresh passed its publication gate; reconcile committed entity state before Pages."
          gh workflow run company-candidate-discovery.yml --ref main
'''
scheduled.write_text(text, encoding="utf-8")

# 6. Candidate reconciliation no longer relies on recursive workflow_run events.
candidate = ROOT / ".github" / "workflows" / "company-candidate-discovery.yml"
text = candidate.read_text(encoding="utf-8")
text = text.replace(
    '''  workflow_run:
    workflows: ["Refresh public intelligence"]
    types: [completed]
''',
    "",
    1,
)
text = text.replace(
    '''concurrency:
  # Failed or cancelled refresh completions skip outside the repository-writer queue.
  group: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.conclusion != 'success' && format('vciq-company-candidate-skip-{0}', github.run_id) || format('vciq-repository-writer-{0}', github.ref) }}
  queue: max

jobs:
  discover:
    if: github.event_name != 'workflow_run' || (github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main')
''',
    '''concurrency:
  group: vciq-repository-writer-${{ github.ref }}
  queue: max

jobs:
  discover:
''',
    1,
)
anchor = "      - name: Reconcile entity types and build candidate review snapshot\n"
if "Detect pushed tracking inputs" not in text:
    text = text.replace(
        anchor,
        '''      - name: Detect pushed tracking inputs
        id: push-inputs
        if: github.event_name == 'push'
        env:
          BEFORE_SHA: ${{ github.event.before }}
          AFTER_SHA: ${{ github.sha }}
        shell: bash
        run: |
          set -euo pipefail
          tracking_inputs_changed=false
          if git diff --name-only "$BEFORE_SHA" "$AFTER_SHA" -- \\
            config/user_tracking.json \\
            config/tracking_capture_inbox.json \\
            config/official_company_sources.json \\
            | grep -q .; then
            tracking_inputs_changed=true
          fi
          echo "changed=$tracking_inputs_changed" >> "$GITHUB_OUTPUT"
''' + anchor,
        1,
    )
text = text.replace(
    '''      - name: Continue refresh or deploy after reconciliation
        if: steps.publish.outputs.changed == 'true' || github.event_name == 'workflow_run' || github.event_name == 'push'
        env:
          GH_TOKEN: ${{ github.token }}
          EVENT_NAME: ${{ github.event_name }}
          TRACKING_CHANGED: ${{ steps.publish.outputs.tracking_changed }}
        shell: bash
        run: |
          set -euo pipefail
          if [ "${TRACKING_CHANGED:-false}" = "true" ] || [ "$EVENT_NAME" = "push" ]; then
            echo "Tracking inputs may have changed; rebuild the article snapshot before Pages."
            gh workflow run scheduled-sync.yml --ref main
          else
            echo "Tracking scope is stable after a successful refresh; deploy the fixed-point snapshot."
            gh workflow run pages.yml --ref main
          fi
''',
    '''      - name: Continue refresh or deploy after reconciliation
        if: steps.publish.outputs.changed == 'true' || github.event_name == 'workflow_dispatch' || github.event_name == 'push'
        env:
          GH_TOKEN: ${{ github.token }}
          TRACKING_CHANGED: ${{ steps.publish.outputs.tracking_changed }}
          PUSH_TRACKING_INPUTS_CHANGED: ${{ steps.push-inputs.outputs.changed }}
        shell: bash
        run: |
          set -euo pipefail
          if [ "${TRACKING_CHANGED:-false}" = "true" ] || [ "${PUSH_TRACKING_INPUTS_CHANGED:-false}" = "true" ]; then
            echo "Tracking inputs changed; rebuild the article snapshot before Pages."
            gh workflow run scheduled-sync.yml --ref main
          else
            echo "Tracking scope is fixed after reconciliation; deploy the committed snapshot."
            gh workflow run pages.yml --ref main
          fi
''',
    1,
)
candidate.write_text(text, encoding="utf-8")

# 7. Bring in the already-tested Eastmoney retention/accounting fix from the
# superseded orchestration PR so the full refresh can survive a rebase tail drop.
replace_once(
    "tools/snapshot_retention.py",
    '''The retention pass also removes duplicate source URLs. This is intentionally
run again after a workflow rebase so a concurrent data commit cannot introduce
one duplicate URL and block publication of an otherwise valid refresh.
"""
''',
    '''The retention pass also removes duplicate source URLs. This is intentionally
run again after a workflow rebase so a concurrent data commit cannot introduce
one duplicate URL and block publication of an otherwise valid refresh.

Retention is also the final authority on Eastmoney detail-row accounting. If
an old Eastmoney detail article falls off the tail during a rebase, the public
source-status counters are reduced to the actually retained rows so the strict
source accounting gate remains closed and deterministic.
"""
''',
)
replace_once(
    "tools/snapshot_retention.py",
    'OVERFLOW_ACTION = "discard-oldest"\n',
    'OVERFLOW_ACTION = "discard-oldest"\nEASTMONEY_DETAIL_STATUS_PREFIX = "official-user-东方财富"\n',
)
replace_once(
    "tools/snapshot_retention.py",
    '''def article_sort_key(article: dict[str, Any]) -> tuple[int, int, str]:
''',
    '''def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def article_sort_key(article: dict[str, Any]) -> tuple[int, int, str]:
''',
)
replace_once(
    "tools/snapshot_retention.py",
    '''def retention_metadata(capacity: int) -> dict[str, Any]:
''',
    '''def _reconcile_eastmoney_retention_accounting(
    payload: dict[str, Any], retained: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Close Eastmoney status counters over the rows that survived retention."""

    raw_statuses = payload.get("sourceStatus")
    if not isinstance(raw_statuses, list):
        return None

    retained_by_source: dict[str, int] = {}
    for article in retained:
        source_id = str(article.get("sourceId") or "").strip()
        if source_id.startswith(EASTMONEY_DETAIL_STATUS_PREFIX):
            retained_by_source[source_id] = retained_by_source.get(source_id, 0) + 1

    statuses: list[dict[str, Any]] = []
    for raw in raw_statuses:
        if not isinstance(raw, dict):
            continue
        status = dict(raw)
        status_id = str(status.get("id") or "").strip()
        if not status_id.startswith(EASTMONEY_DETAIL_STATUS_PREFIX):
            statuses.append(status)
            continue

        kept = retained_by_source.get(status_id, 0)
        status["accepted"] = kept
        has_history_accounting = (
            "newAccepted" in status
            or "retainedPreviousCount" in status
            or bool(status.get("retainedPrevious"))
        )
        if has_history_accounting:
            current_new = min(_nonnegative_int(status.get("newAccepted")), kept)
            current_retained = kept - current_new
            status["newAccepted"] = current_new
            status["retainedPreviousCount"] = current_retained
            if current_retained:
                status["retainedPrevious"] = True
            else:
                status.pop("retainedPrevious", None)
        if kept == 0 and status.get("status") in {"ok", "partial"}:
            status["status"] = "empty"
        statuses.append(status)
    return statuses


def retention_metadata(capacity: int) -> dict[str, Any]:
''',
)
replace_once(
    "tools/snapshot_retention.py",
    '''    next_payload["snapshotRetention"] = retention_metadata(capacity)
    return next_payload, removed
''',
    '''    next_payload["snapshotRetention"] = retention_metadata(capacity)
    reconciled_statuses = _reconcile_eastmoney_retention_accounting(payload, retained)
    if reconciled_statuses is not None:
        next_payload["sourceStatus"] = reconciled_statuses
    return next_payload, removed
''',
)

# 8. Homepage semantics: trusted-by-default key events, truthful fallback stats,
# and rolling headlines renamed to "最新头条" rather than pretending all 200 are today.
replace_once(
    "app/page.tsx",
    'import { trackedSectors } from "@/lib/tracked-sectors";\n',
    'import { formatTaipeiDate } from "@/lib/snapshot-freshness";\nimport { trackedSectors } from "@/lib/tracked-sectors";\n',
)
replace_once(
    "app/page.tsx",
    '''const initialArticles: LiveIntelligenceEvent[] = [...activeArticles]
  .sort(
''',
    '''const initialArticles: LiveIntelligenceEvent[] = activeArticles
  .filter((item) => item.qualityStatus !== "低可信")
  .sort(
''',
)
replace_once(
    "app/page.tsx",
    '''const bootstrap: DashboardBootstrap = {
  trackedSectorAliases,
''',
    '''const taipeiToday = formatTaipeiDate(new Date());
const bootstrap: DashboardBootstrap = {
  trackedSectorAliases,
  todayArticleCount: activeArticles.filter((item) => item.publishedAt === taipeiToday).length,
''',
)

replace_once(
    "components/dashboard-client.tsx",
    '''  trackedSectorAliases: string[];
  sectorCount: number;
''',
    '''  trackedSectorAliases: string[];
  todayArticleCount: number;
  sectorCount: number;
''',
)
replace_once(
    "components/dashboard-client.tsx",
    '''  const [eventSort, setEventSort] = useState<HomepageSortMode>("importance");
  const [query, setQuery] = useState("");
''',
    '''  const [eventSort, setEventSort] = useState<HomepageSortMode>("importance");
  const [qualityScope, setQualityScope] = useState<"trusted" | "all">("trusted");
  const [query, setQuery] = useState("");
''',
)
replace_once(
    "components/dashboard-client.tsx",
    '''      activeArticles
        .filter((item) => region === "全部" || item.region === region)
''',
    '''      activeArticles
        .filter((item) => qualityScope === "all" || item.qualityStatus !== "低可信")
        .filter((item) => region === "全部" || item.region === region)
''',
)
replace_once(
    "components/dashboard-client.tsx",
    '''    [activeArticles, eventSort, eventType, normalizedQuery, region],
''',
    '''    [activeArticles, eventSort, eventType, normalizedQuery, qualityScope, region],
''',
)
replace_once(
    "components/dashboard-client.tsx",
    '''  const todayArticleCount = refreshAudit?.todayArticleCount ?? 0;
  const newArticleCount = refreshAudit?.newArticleCount ?? 0;
''',
    '''  const todayArticleCount = refreshAudit?.todayArticleCount ?? bootstrap.todayArticleCount;
  const newArticleCountLabel = refreshAudit?.newArticleCount ?? "待刷新";
''',
)
replace_once(
    "components/dashboard-client.tsx",
    '当前展示 {displayedEvents.length} 条；滚动总库 {activeArticleCount} 条；今日新增 {todayArticleCount} 条',
    '当前展示 {displayedEvents.length} 条；滚动总库 {activeArticleCount} 条；今日事件 {todayArticleCount} 条',
)
replace_once(
    "components/dashboard-client.tsx",
    '''            <HomepageSortToggle
              value={eventSort}
''',
    '''            <select
              value={qualityScope}
              onChange={(event) => setQualityScope(event.target.value as "trusted" | "all")}
              aria-label="线索质量"
            >
              <option value="trusted">可信优先</option>
              <option value="all">全部线索</option>
            </select>
            <HomepageSortToggle
              value={eventSort}
''',
)
replace_once(
    "components/dashboard-client.tsx",
    '<div><dt>本轮新增</dt><dd>{newArticleCount}</dd></div>',
    '<div><dt>本轮新收录</dt><dd>{newArticleCountLabel}</dd></div>',
)

replace_once(
    "components/daily-headlines.tsx",
    '<aside className={`headlines-column ${styles.column}`} aria-label="今日头条">',
    '<aside className={`headlines-column ${styles.column}`} aria-label="最新头条">',
)
replace_once(
    "components/daily-headlines.tsx",
    '<p className="section-index">02 / TODAY HEADLINES</p>\n          <h2>今日头条</h2>',
    '<p className="section-index">02 / LATEST HEADLINES</p>\n          <h2>最新头条</h2>',
)
replace_once(
    "components/daily-headlines.tsx",
    'ariaLabel="每日头条列表"',
    'ariaLabel="最新头条列表"',
)
replace_once(
    "components/daily-headlines.tsx",
    'description={`汇总本站信息源（微信公众号、今日头条、新浪财经、专业媒体、公司官网等）的每日头条，每个来源每天最多 ${DAILY_HEADLINES_PER_SOURCE_PER_DAY} 条，滚动保留最新 ${DAILY_HEADLINES_LIMIT} 条；可切换按最新时间或重要性排序。`}',
    'description={`汇总本站信息源（微信公众号、今日头条、新浪财经、专业媒体、公司官网等）的滚动最新头条，每个来源每天最多 ${DAILY_HEADLINES_PER_SOURCE_PER_DAY} 条，保留最新 ${DAILY_HEADLINES_LIMIT} 条；可切换按最新时间或重要性排序。`}',
)

replace_once(
    "lib/daily-headlines.ts",
    '''  importance?: number;
  source?: { name?: string; url?: string; platform?: string };
''',
    '''  importance?: number;
  qualityStatus?: string;
  source?: { name?: string; url?: string; platform?: string };
''',
)
replace_once(
    "lib/daily-headlines.ts",
    '''        article.title &&
          source.url &&
''',
    '''        article.title &&
          article.qualityStatus !== "低可信" &&
          source.url &&
''',
)

# 9. Regression tests.
write(
    "tests/test_refresh_audit_contract.py",
    r'''
    from __future__ import annotations

    import json
    import tempfile
    import unittest
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    from tools import crawl_articles
    from tools import frequent_refresh_due


    class RefreshAuditContractTests(unittest.TestCase):
        def test_core_crawler_preserves_refresh_and_tracking_metadata(self) -> None:
            previous = {
                "schemaVersion": 3,
                "generatedAt": "2026-08-07T01:00:00+00:00",
                "articleCount": 0,
                "articles": [],
                "companyFacts": {},
                "sourceStatus": [],
                "qualityGate": {},
                "refreshAudit": {
                    "mode": "full",
                    "pipelineCompleted": True,
                    "completedAt": "2026-08-07T01:00:00+00:00",
                    "lastNewsCrawlAt": "2026-08-07T01:00:00+00:00",
                },
                "trackingConfigHash": "abc",
                "trackingEnrichedAt": "2026-08-07T01:00:01+00:00",
                "trackCoverage": {"ai": {"status": "ready"}},
            }
            with tempfile.TemporaryDirectory(dir=crawl_articles.ROOT) as directory:
                output = Path(directory) / "articles.json"
                changed = crawl_articles.write_if_changed(
                    [{"id": "new"}],
                    previous,
                    output_path=output,
                )
                self.assertTrue(changed)
                result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["refreshAudit"], previous["refreshAudit"])
            self.assertEqual(result["trackingConfigHash"], "abc")
            self.assertEqual(result["trackCoverage"], previous["trackCoverage"])

        def test_missing_audit_is_due_even_when_generated_at_is_recent(self) -> None:
            now = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
            result = frequent_refresh_due.evaluate_due(
                {"generatedAt": (now - timedelta(minutes=5)).isoformat()},
                event_name="schedule",
                now=now,
            )
            self.assertTrue(result["due"])
            self.assertEqual(result["reason"], "missing-news-crawl-audit")

        def test_due_check_uses_last_real_news_crawl(self) -> None:
            now = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
            payload = {
                "generatedAt": (now - timedelta(minutes=5)).isoformat(),
                "refreshAudit": {
                    "mode": "frequent",
                    "pipelineCompleted": True,
                    "completedAt": (now - timedelta(minutes=120)).isoformat(),
                    "lastNewsCrawlAt": (now - timedelta(minutes=120)).isoformat(),
                    "stages": ["core-and-tracking-sources"],
                },
            }
            result = frequent_refresh_due.evaluate_due(
                payload,
                event_name="schedule",
                now=now,
            )
            self.assertTrue(result["due"])
            self.assertEqual(result["ageMinutes"], 120)

        def test_old_completed_full_audit_is_backward_compatible(self) -> None:
            now = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
            payload = {
                "refreshAudit": {
                    "mode": "full",
                    "pipelineCompleted": True,
                    "completedAt": (now - timedelta(minutes=30)).isoformat(),
                    "stages": ["core-and-tracking-sources"],
                }
            }
            result = frequent_refresh_due.evaluate_due(
                payload,
                event_name="schedule",
                now=now,
            )
            self.assertFalse(result["due"])
            self.assertEqual(result["ageMinutes"], 30)


    if __name__ == "__main__":
        unittest.main()
    ''',
)

# Rewrite the workflow tests to describe the fixed production chain.
write(
    "tests/test_frequent_refresh_workflow.py",
    r'''
    from __future__ import annotations

    import unittest
    from pathlib import Path


    ROOT = Path(__file__).resolve().parents[1]
    WORKFLOW = ROOT / ".github" / "workflows" / "frequent-intelligence-refresh.yml"


    class FrequentRefreshWorkflowTests(unittest.TestCase):
        def test_lightweight_schedule_reserves_the_full_refresh_window(self) -> None:
            text = WORKFLOW.read_text(encoding="utf-8")
            self.assertIn('cron: "17 0,2,4,8,10,12,14,16,18,20,22 * * *"', text)
            self.assertIn('timezone: "Asia/Taipei"', text)

        def test_lightweight_refresh_uses_the_repository_writer_queue(self) -> None:
            text = WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("group: vciq-repository-writer-", text)
            self.assertIn("queue: max", text)
            self.assertNotIn("cancel-in-progress:", text)

        def test_due_check_uses_the_real_news_crawl_clock(self) -> None:
            text = WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("python tools/frequent_refresh_due.py", text)
            self.assertNotIn('audit.get("completedAt") or payload.get("generatedAt")', text)
            self.assertIn("ref: main", text)

        def test_lightweight_refresh_only_crawls_news_families(self) -> None:
            text = WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("python tools/crawl_with_wechat_registry.py --source news", text)
            self.assertIn("python tools/finalize_frequent_refresh.py", text)
            self.assertNotIn("python -m tools.us_ir_baseline_disclosures", text)
            self.assertNotIn("python tools/refresh_market_profiles_enriched.py", text)

        def test_successful_crawl_persists_audit_even_without_new_articles(self) -> None:
            text = WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("No semantic article changes; publishing the completed source-crawl audit.", text)
            self.assertNotIn("git restore \"${DATA_PATHS[@]}\"", text)

        def test_bot_authored_refresh_explicitly_dispatches_pages(self) -> None:
            text = WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("Deploy refreshed snapshot", text)
            self.assertIn("steps.data-update.outputs.changed == 'true'", text)
            self.assertIn("gh workflow run pages.yml --ref main", text)
            self.assertIn("actions: write", text)


    if __name__ == "__main__":
        unittest.main()
    ''',
)

# Existing audit test now asserts the dedicated source-crawl clock.
replace_once(
    "tests/test_frequent_refresh_audit.py",
    '                self.assertTrue(audit["pipelineCompleted"])\n',
    '                self.assertTrue(audit["pipelineCompleted"])\n                self.assertEqual(audit["lastNewsCrawlAt"], audit["completedAt"])\n',
)

# Reuse the already-reviewed orchestration assertions from the stale #197 PR.
write(
    "tests/test_entity_resolution_workflow.py",
    r'''
    from __future__ import annotations

    import unittest
    from pathlib import Path


    ROOT = Path(__file__).resolve().parents[1]
    CANDIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "company-candidate-discovery.yml"
    REFRESH_WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"
    PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


    class EntityResolutionWorkflowTests(unittest.TestCase):
        def test_candidate_workflow_reconciles_before_candidate_generation(self) -> None:
            text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
            reconcile = text.index("python tools/reconcile_entity_resolution.py")
            build = text.index("python tools/build_resolved_company_candidates.py")
            self.assertLess(reconcile, build)
            self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
            self.assertIn("python tools/build_resolved_company_candidates.py --check", text)

        def test_candidate_workflow_commits_reconciled_inputs_and_tracks_scope_changes(self) -> None:
            text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("config/user_tracking.json", text)
            self.assertIn("config/tracking_capture_inbox.json", text)
            self.assertIn("public/data/company_candidates.json", text)
            self.assertIn("actions: write", text)
            self.assertIn("git diff-tree --no-commit-id --name-only -r HEAD -- config/user_tracking.json", text)

        def test_tracking_changes_refresh_snapshot_before_pages_deploy(self) -> None:
            text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
            refresh = text.index("gh workflow run scheduled-sync.yml --ref main")
            deploy = text.index("gh workflow run pages.yml --ref main")
            self.assertLess(refresh, deploy)
            self.assertIn("TRACKING_CHANGED: ${{ steps.publish.outputs.tracking_changed }}", text)
            self.assertIn("PUSH_TRACKING_INPUTS_CHANGED: ${{ steps.push-inputs.outputs.changed }}", text)
            self.assertIn("Detect pushed tracking inputs", text)
            self.assertIn("github.event_name == 'workflow_dispatch'", text)
            self.assertIn("github.event_name == 'push'", text)

        def test_full_refresh_explicitly_hands_off_to_reconciliation(self) -> None:
            refresh = REFRESH_WORKFLOW.read_text(encoding="utf-8")
            candidate = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("Continue through entity reconciliation before publication", refresh)
            self.assertIn("steps.data-update.outcome == 'success'", refresh)
            self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", refresh)
            self.assertIn("workflow_dispatch:", candidate)
            self.assertNotIn("workflow_run:", candidate)
            self.assertIn("gh workflow run pages.yml --ref main", candidate)

        def test_candidate_writer_is_serialized_without_recursive_workflow_run_logic(self) -> None:
            text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
            self.assertIn("group: vciq-repository-writer-", text)
            self.assertIn("github.ref", text)
            self.assertIn("queue: max", text)
            self.assertNotIn("workflow_run:", text)
            self.assertNotIn("cancel-in-progress:", text)

        def test_pages_build_uses_the_same_resolution_gate(self) -> None:
            text = PAGES_WORKFLOW.read_text(encoding="utf-8")
            reconcile = text.index("python tools/reconcile_entity_resolution.py")
            build = text.index("python tools/build_resolved_company_candidates.py")
            self.assertLess(reconcile, build)
            self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
            self.assertIn("python tools/build_resolved_company_candidates.py --check", text)


    if __name__ == "__main__":
        unittest.main()
    ''',
)

# Add scheduled-sync explicit handoff + audit persistence assertions.
replace_once(
    "tests/test_scheduled_sync_workflow.py",
    '''    def test_rebase_rebuilds_quality_gate_before_full_refresh_validation(self) -> None:
''',
    '''    def test_successful_publication_gate_explicitly_dispatches_entity_reconciliation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Continue through entity reconciliation before publication", text)
        self.assertIn("steps.data-update.outcome == 'success'", text)
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", text)
        self.assertIn("actions: write", text)

    def test_full_crawl_persists_audit_without_semantic_article_changes(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("No semantic public-data changes; publishing the completed full-crawl audit.", text)
        self.assertNotIn("No semantic public data changes; skipping Git commit and Pages build.", text)

    def test_rebase_rebuilds_quality_gate_before_full_refresh_validation(self) -> None:
''',
)

# Add Eastmoney retention regression test.
replace_once(
    "tests/test_snapshot_retention.py",
    '''class SnapshotRetentionTest(unittest.TestCase):
''',
    '''def eastmoney_article(
    article_id: str,
    published_at: str,
    source_id: str,
    importance: int = 70,
) -> dict:
    row = article(article_id, published_at, importance)
    row["sourceId"] = source_id
    row["source"] = {
        "name": "东方财富",
        "url": f"https://finance.eastmoney.com/a/{article_id}.html",
        "level": "媒体报道",
        "platform": "东方财富",
    }
    return row


class SnapshotRetentionTest(unittest.TestCase):
''',
)
replace_once(
    "tests/test_snapshot_retention.py",
    '''    def test_core_merge_already_applies_the_same_replacement_rule(self) -> None:
''',
    '''    def test_retention_closes_eastmoney_source_accounting_after_tail_drop(self) -> None:
        eastmoney_a = "official-user-东方财富"
        eastmoney_b = "official-user-东方财富-半导体信源"
        payload = {
            "schemaVersion": 3,
            "articleCount": 3,
            "articles": [
                eastmoney_article("old-retained", "2026-07-01", eastmoney_a),
                eastmoney_article("mid-retained", "2026-07-02", eastmoney_b),
                eastmoney_article("new-current", "2026-07-03", eastmoney_a),
            ],
            "sourceStatus": [
                {"id": eastmoney_a, "status": "ok", "accepted": 2, "newAccepted": 1, "retainedPrevious": True, "retainedPreviousCount": 1},
                {"id": eastmoney_b, "status": "ok", "accepted": 1, "newAccepted": 0, "retainedPrevious": True, "retainedPreviousCount": 1},
            ],
        }
        next_payload, removed = snapshot_retention.apply_retention(payload, capacity=2)
        self.assertEqual(removed, 1)
        statuses = {row["id"]: row for row in next_payload["sourceStatus"]}
        self.assertEqual(statuses[eastmoney_a]["accepted"], 1)
        self.assertEqual(statuses[eastmoney_a]["newAccepted"], 1)
        self.assertEqual(statuses[eastmoney_a]["retainedPreviousCount"], 0)
        self.assertNotIn("retainedPrevious", statuses[eastmoney_a])
        self.assertEqual(statuses[eastmoney_b]["accepted"], 1)
        self.assertEqual(statuses[eastmoney_b]["retainedPreviousCount"], 1)

    def test_core_merge_already_applies_the_same_replacement_rule(self) -> None:
''',
)

# TS source-contract test for the user-visible semantics and trusted defaults.
write(
    "tests/homepage-refresh-quality.test.ts",
    r'''
    import assert from "node:assert/strict";
    import { readFileSync } from "node:fs";
    import test from "node:test";

    const dashboard = readFileSync("components/dashboard-client.tsx", "utf8");
    const page = readFileSync("app/page.tsx", "utf8");
    const headlines = readFileSync("components/daily-headlines.tsx", "utf8");

    test("homepage defaults key events to trusted evidence", () => {
      assert.match(dashboard, /qualityScope === "all" \|\| item\.qualityStatus !== "低可信"/);
      assert.match(dashboard, /<option value="trusted">可信优先<\/option>/);
      assert.match(page, /\.filter\(\(item\) => item\.qualityStatus !== "低可信"\)/);
    });

    test("homepage distinguishes today's events from current-crawl additions", () => {
      assert.match(dashboard, /今日事件 \{todayArticleCount\} 条/);
      assert.match(dashboard, /本轮新收录/);
      assert.match(dashboard, /refreshAudit\?\.todayArticleCount \?\? bootstrap\.todayArticleCount/);
      assert.match(dashboard, /refreshAudit\?\.newArticleCount \?\? "待刷新"/);
    });

    test("rolling 200-item column is labeled as latest headlines", () => {
      assert.match(headlines, /02 \/ LATEST HEADLINES/);
      assert.match(headlines, /<h2>最新头条<\/h2>/);
      assert.doesNotMatch(headlines, /<h2>今日头条<\/h2>/);
    });
    ''',
)

# Existing daily-headline selector should not promote low-confidence noise.
replace_once(
    "tests/daily-headlines.test.ts",
    '''test("search proxies and regulators are excluded from headlines", () => {
''',
    '''test("low-confidence records are excluded from headlines", () => {
  const headlines = selectDailyHeadlines([
    article({ qualityStatus: "低可信", title: "无关低可信线索" }),
    article({ qualityStatus: "可用", title: "可信行业事件" }),
  ]);
  assert.deepEqual(headlines.map((item) => item.title), ["可信行业事件"]);
});

test("search proxies and regulators are excluded from headlines", () => {
''',
)

print("refresh audit / publication / homepage quality patch applied")
