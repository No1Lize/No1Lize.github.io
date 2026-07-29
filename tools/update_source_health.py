#!/usr/bin/env python3
"""Persist cross-run source health and prepare one GitHub Issue alert summary."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
DEFAULT_STATE_PATH = ROOT / "public" / "data" / "source_health.json"
DEFAULT_POLICY_PATH = ROOT / "config" / "source_health_policy.json"
DEFAULT_SUMMARY_PATH = Path("/tmp/source-health-issue.md")

DEFAULT_POLICY = {
    "schemaVersion": 1,
    "failureThreshold": 3,
    "criticalPlatforms": ["微信"],
    "criticalSourceIds": [],
    "countEmptyForCriticalSources": True,
    "alertOnRetainedPrevious": True,
    "alertOnExplicitError": True,
}


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _source_id(status: dict[str, Any]) -> str:
    return str(status.get("id") or status.get("sourceId") or status.get("name") or "").strip()


def _classification(
    status: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[bool, str]:
    state = str(status.get("status") or "unknown").casefold()
    source_id = _source_id(status)
    platform = str(status.get("platform") or "").strip()
    accepted = _integer(status.get("accepted"))
    retained_previous = bool(status.get("retainedPrevious"))
    critical = source_id in set(policy.get("criticalSourceIds", [])) or platform in set(
        policy.get("criticalPlatforms", [])
    )

    if policy.get("alertOnRetainedPrevious", True) and retained_previous:
        return True, "本轮抓取失败，继续保留上一版快照"
    if policy.get("alertOnExplicitError", True) and state in {"error", "failed"}:
        error = str(status.get("error") or "来源返回显式错误").strip()
        return True, error[:240]
    if (
        critical
        and policy.get("countEmptyForCriticalSources", True)
        and accepted <= 0
        and state in {"empty", "ok", "partial", "unknown"}
    ):
        return True, "关键来源本轮没有合格结果"
    return False, ""


def update_health(
    previous_payload: dict[str, Any],
    article_payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_time = (now or datetime.now(UTC)).replace(microsecond=0)
    timestamp = current_time.isoformat()
    threshold = max(1, _integer(policy.get("failureThreshold")) or 3)
    previous_sources = previous_payload.get("sources", {})
    previous_sources = previous_sources if isinstance(previous_sources, dict) else {}
    statuses = article_payload.get("sourceStatus", [])
    statuses = statuses if isinstance(statuses, list) else []

    next_sources: dict[str, dict[str, Any]] = {}
    new_alerts: list[str] = []
    recoveries: list[str] = []

    for raw_status in statuses:
        if not isinstance(raw_status, dict):
            continue
        source_id = _source_id(raw_status)
        if not source_id:
            continue
        previous = previous_sources.get(source_id, {})
        previous = previous if isinstance(previous, dict) else {}
        unhealthy, reason = _classification(raw_status, policy)
        previous_streak = _integer(previous.get("consecutiveFailures"))
        previous_active = bool(previous.get("alertActive"))
        accepted = _integer(raw_status.get("accepted"))
        state = str(raw_status.get("status") or "unknown")

        if unhealthy:
            streak = previous_streak + 1
            last_success_at = previous.get("lastSuccessAt")
            last_failure_at = timestamp
        else:
            streak = 0
            last_success_at = (
                timestamp
                if accepted > 0 or state.casefold() in {"ok", "partial"}
                else previous.get("lastSuccessAt")
            )
            last_failure_at = previous.get("lastFailureAt")

        alert_active = unhealthy and streak >= threshold
        if alert_active and not previous_active:
            new_alerts.append(source_id)
        if previous_active and not alert_active:
            recoveries.append(source_id)

        next_sources[source_id] = {
            "id": source_id,
            "name": str(raw_status.get("name") or previous.get("name") or source_id),
            "platform": str(raw_status.get("platform") or previous.get("platform") or ""),
            "lastStatus": state,
            "accepted": accepted,
            "failed": _integer(raw_status.get("failed")),
            "consecutiveFailures": streak,
            "failureThreshold": threshold,
            "alertActive": alert_active,
            "reason": reason if unhealthy else "",
            "lastSeenAt": timestamp,
            "lastSuccessAt": last_success_at,
            "lastFailureAt": last_failure_at,
        }

    active_alerts = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if bool(entry.get("alertActive"))
    )
    previous_active_alerts = sorted(
        source_id
        for source_id, entry in previous_sources.items()
        if isinstance(entry, dict) and bool(entry.get("alertActive"))
    )
    result = {
        "schemaVersion": 1,
        "generatedAt": timestamp,
        "failureThreshold": threshold,
        "sourceCount": len(next_sources),
        "activeAlertCount": len(active_alerts),
        "activeAlerts": active_alerts,
        "sources": dict(sorted(next_sources.items())),
    }
    summary = {
        "activeAlerts": active_alerts,
        "newAlerts": sorted(new_alerts),
        "recoveries": sorted(recoveries),
        "alertChanged": active_alerts != previous_active_alerts,
        "generatedAt": timestamp,
    }
    return result, summary


def render_issue_markdown(state: dict[str, Any], summary: dict[str, Any]) -> str:
    active_ids = summary.get("activeAlerts", [])
    lines = [
        "# 关键情报源连续异常",
        "",
        "该 Issue 由定时刷新工作流维护。来源连续达到阈值后进入告警，恢复后自动关闭。",
        "",
    ]
    if not active_ids:
        lines.extend(["当前没有持续异常的关键来源。", ""])
    else:
        lines.extend(
            [
                f"当前共有 **{len(active_ids)}** 个来源处于持续异常状态。",
                "",
                "| 来源 | 平台 | 连续异常 | 当前状态 | 原因 | 最后成功 |",
                "|---|---|---:|---|---|---|",
            ]
        )
        sources = state.get("sources", {})
        for source_id in active_ids:
            item = sources.get(source_id, {})
            reason = str(item.get("reason") or "未知").replace("|", "\\|")
            lines.append(
                "| {name} | {platform} | {streak} | {status} | {reason} | {success} |".format(
                    name=str(item.get("name") or source_id).replace("|", "\\|"),
                    platform=str(item.get("platform") or "—").replace("|", "\\|"),
                    streak=item.get("consecutiveFailures", 0),
                    status=str(item.get("lastStatus") or "unknown").replace("|", "\\|"),
                    reason=reason,
                    success=item.get("lastSuccessAt") or "尚无成功记录",
                )
            )
        lines.append("")
    lines.extend(
        [
            f"最后检查：`{summary.get('generatedAt', '')}`",
            "",
            "处理原则：不绕过验证码或访问限制；失败时保留上一版已验证快照。",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_github_output(path: str | None, summary: dict[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"active_count={len(summary.get('activeAlerts', []))}\n")
        handle.write(f"new_alert_count={len(summary.get('newAlerts', []))}\n")
        handle.write(f"recovery_count={len(summary.get('recoveries', []))}\n")
        handle.write(f"alert_changed={str(bool(summary.get('alertChanged'))).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=Path, default=DEFAULT_ARTICLES_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    article_payload = _read_json(args.articles, {})
    previous_payload = _read_json(args.state, {})
    policy = dict(DEFAULT_POLICY)
    configured = _read_json(args.policy, {})
    if isinstance(configured, dict):
        policy.update(configured)

    state, summary = update_health(previous_payload, article_payload, policy)
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(render_issue_markdown(state, summary), encoding="utf-8")
    _write_github_output(args.github_output, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
