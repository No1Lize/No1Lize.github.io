#!/usr/bin/env python3
"""One-time migration that wires automatic candidate onboarding into the app."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: patch target not found: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_venture_profile_catalog_loader() -> None:
    replace_once(
        "tools/venture_profile_extraction.py",
        "from typing import Any, Iterable, Sequence\n",
        "from pathlib import Path\nfrom typing import Any, Iterable, Sequence\n",
    )
    replace_once(
        "tools/venture_profile_extraction.py",
        '''    for line in _catalog_lines(text, "export const institutionCatalog", "export type IpoCompany"):\n''',
        '''    if not companies:\n        registry_path = (\n            Path(__file__).resolve().parents[1]\n            / "config"\n            / "company_registry.json"\n        )\n        try:\n            registry = json.loads(registry_path.read_text(encoding="utf-8"))\n        except (OSError, json.JSONDecodeError):\n            registry = {}\n        for raw in registry.get("companies", []):\n            if not isinstance(raw, dict):\n                continue\n            source = raw.get("source") if isinstance(raw.get("source"), dict) else {}\n            slug = clean_text(raw.get("slug"), 100)\n            name = clean_text(raw.get("name"), 200)\n            source_url = normalize_url(source.get("url"))\n            if not slug or not name or not source_url:\n                continue\n            companies.append(\n                CatalogCompany(\n                    slug=slug,\n                    name=name,\n                    english_name=clean_text(raw.get("englishName"), 200),\n                    region=clean_text(raw.get("region"), 80),\n                    sector=clean_text(raw.get("sector"), 120),\n                    stage=clean_text(raw.get("stage"), 80),\n                    status=clean_text(raw.get("status"), 80),\n                    summary=clean_text(raw.get("summary"), 1200),\n                    product=clean_text(raw.get("product"), 1200),\n                    source_name=clean_text(source.get("name"), 200) or name,\n                    source_url=source_url,\n                )\n            )\n\n    for line in _catalog_lines(text, "export const institutionCatalog", "export type IpoCompany"):\n''',
    )


def patch_candidate_builder() -> None:
    replace_once(
        "tools/build_company_candidates.py",
        '''new companies by themselves. The output is a review queue, not a production\ncatalog: no candidate becomes a formal company route without an explicit\noperator decision and a separate catalog change.\n''',
        '''new companies by themselves. The output is a review queue. A reviewed\ncandidate becomes a formal route only after a versioned onboarding request passes\nregistry, official-source and profile publication gates.\n''',
    )
    replace_once(
        "tools/build_company_candidates.py",
        'VALID_DECISIONS = {"pending", "accepted", "rejected", "merged"}',
        'VALID_DECISIONS = {"pending", "accepted", "rejected", "merged", "published"}',
    )
    replace_once(
        "tools/build_company_candidates.py",
        '''            "decidedAt": clean(raw_value.get("decidedAt"), 40),\n        }''',
        '''            "decidedAt": clean(raw_value.get("decidedAt"), 80),\n            "reviewedBy": clean(raw_value.get("reviewedBy"), 120),\n            "onboarding": raw_value.get("onboarding")\n            if isinstance(raw_value.get("onboarding"), dict)\n            else {},\n        }''',
    )
    replace_once(
        "tools/build_company_candidates.py",
        '''                "decidedAt": decision.get("decidedAt", ""),\n            }''',
        '''                "decidedAt": decision.get("decidedAt", ""),\n                "reviewedBy": decision.get("reviewedBy", ""),\n                "onboarding": decision.get("onboarding", {}),\n            }''',
    )
    replace_once(
        "tools/build_company_candidates.py",
        'status_order = {"pending": 0, "accepted": 1, "merged": 2, "rejected": 3}',
        'status_order = {"pending": 0, "accepted": 1, "published": 2, "merged": 3, "rejected": 4}',
    )
    replace_once(
        "tools/build_company_candidates.py",
        '''        "rejectedCount": counts["rejected"],\n        "candidates": candidates,''',
        '''        "rejectedCount": counts["rejected"],\n        "mergedCount": counts["merged"],\n        "publishedCount": counts["published"],\n        "candidates": candidates,''',
    )


def patch_review_ui() -> None:
    replace_once(
        "components/tracking-company-candidate-review.tsx",
        '''  "rejected",\n  "merged",\n];''',
        '''  "rejected",\n  "merged",\n  "published",\n];''',
    )
    replace_once(
        "components/tracking-company-candidate-review.tsx",
        '''  rejected: "已拒绝",\n  merged: "已合并",\n};''',
        '''  rejected: "已拒绝",\n  merged: "已合并",\n  published: "已发布",\n};''',
    )
    replace_once(
        "components/tracking-company-candidate-review.tsx",
        '''  async function saveDecision(nextStatus: CompanyCandidateStatus) {\n    if (!selected) return;''',
        '''  async function saveDecision(nextStatus: CompanyCandidateStatus) {\n    if (!selected) return;\n    if (selected.status === "published") {\n      setStatus("已发布公司必须通过正式公司注册表维护，不能在候选审核区回退或覆盖。");\n      setStatusKind("error");\n      return;\n    }''',
    )
    replace_once(
        "components/tracking-company-candidate-review.tsx",
        '''              查看候选证据并执行通过、拒绝或合并操作。决定写入\n              <code> {DECISION_PATH}</code>，不会自动把候选加入正式公司档案。''',
        '''              查看候选证据并执行通过、拒绝或合并操作。审核通过后需在下方补齐规范实体资料；提交建档请求后，工作流会自动写入正式公司注册表、抓取档案并发布页面。决定写入\n              <code> {DECISION_PATH}</code>。''',
    )
    replace_once(
        "components/tracking-company-candidate-review.tsx",
        '''            <span><small>已合并</small><strong>{counts.merged}</strong></span>\n          </div>''',
        '''            <span><small>已合并</small><strong>{counts.merged}</strong></span>\n            <span><small>已发布</small><strong>{counts.published}</strong></span>\n          </div>''',
    )
    replace_once(
        "components/tracking-company-candidate-review.module.css",
        "grid-template-columns: repeat(4, minmax(70px, 1fr));",
        "grid-template-columns: repeat(5, minmax(70px, 1fr));",
    )
    replace_once(
        "components/tracking-company-candidate-review.module.css",
        "min-width: min(100%, 360px);",
        "min-width: min(100%, 450px);",
    )
    replace_once(
        "components/company-candidate-directory.tsx",
        "候选需人工审核，系统不会自动加入正式公司档案。",
        "候选需先人工确认公司实体；审核通过后还需补齐规范名称、slug 与官方来源，质量门通过后才会自动创建正式公司档案。",
    )


def main() -> int:
    patch_venture_profile_catalog_loader()
    patch_candidate_builder()
    patch_review_ui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
