#!/usr/bin/env python3
"""Generate a bounded monthly source-performance review queue."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .source_quality_reviews import load_review_manifest, review_index
except ImportError:
    from source_quality_reviews import load_review_manifest, review_index

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "public" / "data" / "source_health.json"
DEFAULT_REVIEW_PATH = ROOT / "config" / "source_quality_reviews.json"
DEFAULT_JSON_PATH = ROOT / "public" / "data" / "source_performance_review.json"
DEFAULT_MARKDOWN_PATH = ROOT / "docs" / "source-performance-review.md"

STATE_PRIORITY = {
    "retire-candidate": 0,
    "downgrade-candidate": 1,
    "monitor": 2,
    "insufficient-data": 3,
    "retain": 4,
}
STATE_LABELS = {
    "retire-candidate": "建议停用候选",
    "downgrade-candidate": "建议降级候选",
    "monitor": "继续观察",
    "insufficient-data": "样本不足",
    "retain": "保留",
}


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _percent(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def build_review(
    state: dict[str, Any],
    manual_reviews: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    generated_at = str(state.get("generatedAt") or "")
    period = generated_at[:7] if len(generated_at) >= 7 else "unknown"
    sources = state.get("sources", {})
    sources = sources if isinstance(sources, dict) else {}
    rows: list[dict[str, Any]] = []

    for source_id, raw in sources.items():
        if not isinstance(raw, dict):
            continue
        performance = raw.get("performance")
        performance = performance if isinstance(performance, dict) else {}
        review_state = str(performance.get("reviewState") or "insufficient-data")
        manual = manual_reviews.get(source_id, {})
        row = {
            "sourceId": source_id,
            "name": str(raw.get("name") or source_id),
            "platform": str(raw.get("platform") or ""),
            "evidenceGrade": str(raw.get("evidenceGrade") or "D"),
            "collectionState": str(raw.get("collectionState") or "active"),
            "priority": str(raw.get("priority") or "normal"),
            "reviewState": review_state,
            "reviewStateLabel": STATE_LABELS.get(review_state, review_state),
            "reviewReasons": list(performance.get("reviewReasons") or []),
            "reviewReasonLabels": list(performance.get("reviewReasonLabels") or []),
            "runs": int(performance.get("runs", 0) or 0),
            "availabilityRate": performance.get("availabilityRate"),
            "productiveRate": performance.get("productiveRate"),
            "validYieldRate": performance.get("validYieldRate"),
            "publicationRate": performance.get("publicationRate"),
            "duplicateRate": performance.get("duplicateRate"),
            "dropRate": performance.get("dropRate"),
            "averageDiscoveryLagDays": performance.get("averageDiscoveryLagDays"),
            "newArticles": int(performance.get("newArticles", 0) or 0),
            "lastProductiveAt": raw.get("lastProductiveAt"),
            "reviewedRecords": int(manual.get("reviewedRecords", 0) or 0),
            "misattributedRecords": int(manual.get("misattributedRecords", 0) or 0),
            "misattributionRate": manual.get("misattributionRate"),
            "confirmedDuplicateRecords": int(
                manual.get("confirmedDuplicateRecords", 0) or 0
            ),
            "lastReviewedAt": manual.get("lastReviewedAt"),
            "reviewer": manual.get("reviewer"),
        }
        rows.append(row)

    rows.sort(
        key=lambda row: (
            STATE_PRIORITY.get(row["reviewState"], 9),
            0 if row["collectionState"] in {"quarantined", "probation"} else 1,
            row["evidenceGrade"],
            row["name"].casefold(),
        )
    )
    state_counts = Counter(row["reviewState"] for row in rows)
    review_required = [
        row
        for row in rows
        if row["reviewState"] in {"monitor", "downgrade-candidate", "retire-candidate"}
    ]
    return {
        "schemaVersion": 1,
        "period": period,
        "generatedAt": generated_at,
        "sourceCount": len(rows),
        "reviewRequiredSourceCount": len(review_required),
        "stateCounts": dict(sorted(state_counts.items())),
        "manualReviewCoverage": {
            "reviewedSources": sum(row["reviewedRecords"] > 0 for row in rows),
            "reviewedRecords": sum(row["reviewedRecords"] for row in rows),
        },
        "sources": rows,
    }


def render_markdown(report: dict[str, Any], *, limit: int = 100) -> str:
    rows = report.get("sources", [])
    review_rows = [
        row
        for row in rows
        if row.get("reviewState")
        in {"retire-candidate", "downgrade-candidate", "monitor"}
    ]
    lines = [
        "# 信源效能月度审查",
        "",
        f"审查周期：`{report.get('period', '')}`；数据快照：`{report.get('generatedAt', '')}`。",
        "",
        f"共评估 **{report.get('sourceCount', 0)}** 个来源，**{report.get('reviewRequiredSourceCount', 0)}** 个进入人工审查队列。",
        "",
        "口径：成功率表示来源可访问且可解析；有效产出率表示该轮产生至少一条合格记录；扫描转化为 accepted/scanned；重复率只统计 URL 或事件指纹重复；未发布但非重复的候选单列为丢弃率；隔离候选单列为 withheld，不混入重复率。系统只提出建议，不自动删除来源。",
        "",
    ]
    if not review_rows:
        lines.extend(["当前没有达到人工审查阈值的来源。", ""])
    else:
        lines.extend(
            [
                "| 来源 | 等级 | 建议 | 成功率 | 有效轮次 | 扫描转化 | 重复率 | 丢弃率 | 平均发现延迟 | 人工误归属 | 原因 |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in review_rows[:limit]:
            reasons = "；".join(row.get("reviewReasonLabels") or []) or "—"
            delay = row.get("averageDiscoveryLagDays")
            delay_text = f"{float(delay):.1f} 天" if delay is not None else "—"
            lines.append(
                "| {name} | {grade} | {state} | {availability} | {productive} | {yield_rate} | {duplicates} | {drops} | {delay} | {misattribution} | {reasons} |".format(
                    name=str(row.get("name") or row.get("sourceId")).replace("|", "\\|"),
                    grade=row.get("evidenceGrade") or "D",
                    state=row.get("reviewStateLabel") or row.get("reviewState"),
                    availability=_percent(row.get("availabilityRate")),
                    productive=_percent(row.get("productiveRate")),
                    yield_rate=_percent(row.get("validYieldRate")),
                    duplicates=_percent(row.get("duplicateRate")),
                    drops=_percent(row.get("dropRate")),
                    delay=delay_text,
                    misattribution=_percent(row.get("misattributionRate")),
                    reasons=reasons.replace("|", "\\|"),
                )
            )
        if len(review_rows) > limit:
            lines.extend(
                [
                    "",
                    f"表格仅展示前 {limit} 个高优先级候选；完整数据见 `public/data/source_performance_review.json`。",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## 人工处理要求",
            "",
            "停用或降级前应检查来源 URL、抓取适配器、重复来源、历史有效产出和至少 20 条记录的误归属抽样。人工抽样结果写入 `config/source_quality_reviews.json`。",
            "",
        ]
    )
    return "\n".join(lines)


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schemaVersion") != 1:
        errors.append("invalid schemaVersion")
    if not isinstance(report.get("sources"), list):
        errors.append("sources must be an array")
    if int(report.get("sourceCount", -1)) != len(report.get("sources", [])):
        errors.append("sourceCount does not match sources")
    for index, row in enumerate(report.get("sources", [])):
        if not isinstance(row, dict) or not row.get("sourceId"):
            errors.append(f"invalid source row {index}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        report = _read_json(args.json, {})
        errors = validate_report(report if isinstance(report, dict) else {})
        print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
        return 1 if errors else 0

    state = _read_json(args.state, {})
    manifest = load_review_manifest(args.reviews)
    report = build_review(
        state if isinstance(state, dict) else {},
        review_index(manifest),
    )
    errors = validate_report(report)
    if errors:
        raise ValueError("; ".join(errors))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "period": report["period"],
                "sourceCount": report["sourceCount"],
                "reviewRequiredSourceCount": report["reviewRequiredSourceCount"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
