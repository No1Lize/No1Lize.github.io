#!/usr/bin/env python3
"""One-time deterministic patch for source evidence grading and quarantine wiring."""

from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: patch target not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> int:
    crawler = Path("tools/crawl_articles.py")
    replace_once(
        crawler,
        '''except ImportError:\n    from article_observation import (\n        apply_incoming_observations,\n        prepare_existing_articles,\n        validate_observation_metadata,\n    )\nfrom urllib.error import HTTPError, URLError\n''',
        '''except ImportError:\n    from article_observation import (\n        apply_incoming_observations,\n        prepare_existing_articles,\n        validate_observation_metadata,\n    )\n\ntry:\n    from .source_evidence import (\n        enrich_article_sources,\n        enrich_source_evidence,\n        validate_source_evidence,\n    )\nexcept ImportError:\n    from source_evidence import (\n        enrich_article_sources,\n        enrich_source_evidence,\n        validate_source_evidence,\n    )\nfrom urllib.error import HTTPError, URLError\n''',
        "crawler source evidence imports",
    )
    replace_once(
        crawler,
        '''def _source(\n    name: str, url: str, level: str, platform: str\n) -> dict[str, str]:\n    return {\n        "name": clean_text(name),\n        "url": normalize_url(url),\n        "level": level if level in VALID_SOURCE_LEVELS else "待交叉验证",\n        "platform": clean_text(platform),\n    }\n''',
        '''def _source(\n    name: str, url: str, level: str, platform: str\n) -> dict[str, str]:\n    return enrich_source_evidence(\n        {\n            "name": clean_text(name),\n            "url": normalize_url(url),\n            "level": level if level in VALID_SOURCE_LEVELS else "待交叉验证",\n            "platform": clean_text(platform),\n        }\n    )\n''',
        "crawler source evidence enrichment",
    )
    replace_once(
        crawler,
        '''    if source.get("level") not in VALID_SOURCE_LEVELS:\n        errors.append("invalid:source-level")\n    if not (0 <= int(article.get("importance", -1)) <= 100):\n''',
        '''    if source.get("level") not in VALID_SOURCE_LEVELS:\n        errors.append("invalid:source-level")\n    errors.extend(validate_source_evidence(source))\n    if not (0 <= int(article.get("importance", -1)) <= 100):\n''',
        "crawler source evidence validation",
    )
    replace_once(
        crawler,
        '''    merged = repair_media_company_attribution(merged)\n    source_status = merge_source_status(\n''',
        '''    merged = repair_media_company_attribution(merged)\n    merged = enrich_article_sources(merged)\n    source_status = merge_source_status(\n''',
        "crawler legacy source evidence migration",
    )

    tracking = Path("tools/crawl_with_tracking.py")
    replace_once(
        tracking,
        '''    from . import crawl_articles as crawler\n    from . import tracking_quality\n    from . import tracking_taxonomy\nexcept ImportError:  # Executed directly with ``python tools/...``.\n    import crawl_articles as crawler\n    import tracking_quality\n    import tracking_taxonomy\n''',
        '''    from . import crawl_articles as crawler\n    from . import source_health_runtime\n    from . import tracking_quality\n    from . import tracking_taxonomy\nexcept ImportError:  # Executed directly with ``python tools/...``.\n    import crawl_articles as crawler\n    import source_health_runtime\n    import tracking_quality\n    import tracking_taxonomy\n''',
        "tracking quarantine imports",
    )
    replace_once(
        tracking,
        '''    original_repair_attribution = crawler.repair_media_company_attribution\n    original_evaluate_quality = crawler.evaluate_quality\n    tracking_report: dict[str, Any] = {}\n''',
        '''    original_repair_attribution = crawler.repair_media_company_attribution\n    original_evaluate_quality = crawler.evaluate_quality\n    original_replace_source_batches = crawler.replace_source_batches\n    quarantined_source_ids = source_health_runtime.load_publication_quarantine()\n    tracking_report: dict[str, Any] = {}\n''',
        "tracking quarantine state",
    )
    replace_once(
        tracking,
        '''    def external_article(spec: dict[str, Any], **kwargs: Any) -> dict[str, Any]:\n        kwargs.setdefault("company", spec.get("company") or None)\n        kwargs.setdefault("company_slug", spec.get("companySlug") or None)\n        return original_external_article(spec, **kwargs)\n\n    def repair_media_company_attribution(\n''',
        '''    def external_article(spec: dict[str, Any], **kwargs: Any) -> dict[str, Any]:\n        kwargs.setdefault("company", spec.get("company") or None)\n        kwargs.setdefault("company_slug", spec.get("companySlug") or None)\n        return original_external_article(spec, **kwargs)\n\n    def replace_source_batches(\n        existing: list[dict[str, Any]],\n        incoming: list[dict[str, Any]],\n        statuses: list[dict[str, Any]],\n    ) -> list[dict[str, Any]]:\n        publishable, replacement_statuses = (\n            source_health_runtime.withhold_quarantined_publication(\n                incoming, statuses, quarantined_source_ids\n            )\n        )\n        if quarantined_source_ids:\n            print(\n                "Source publication quarantine: "\n                + json.dumps(sorted(quarantined_source_ids), ensure_ascii=False)\n            )\n        return original_replace_source_batches(\n            existing, publishable, replacement_statuses\n        )\n\n    def repair_media_company_attribution(\n''',
        "tracking quarantine batch replacement",
    )
    replace_once(
        tracking,
        '''    crawler._external_article = external_article\n    crawler.repair_media_company_attribution = repair_media_company_attribution\n    crawler.evaluate_quality = evaluate_quality\n''',
        '''    crawler._external_article = external_article\n    crawler.replace_source_batches = replace_source_batches\n    crawler.repair_media_company_attribution = repair_media_company_attribution\n    crawler.evaluate_quality = evaluate_quality\n''',
        "tracking quarantine install",
    )

    updates = Path("lib/channel-updates.ts")
    replace_once(
        updates,
        '''  lastVerifiedAt?: string;\n  lastVerifiedEstimated?: boolean;\n};\n''',
        '''  lastVerifiedAt?: string;\n  lastVerifiedEstimated?: boolean;\n  sourceGrade?: "A" | "B" | "C" | "D";\n  sourceGradeLabel?: string;\n  sourceVerificationPolicy?: string;\n};\n''',
        "channel source grade fields",
    )
    replace_once(
        updates,
        '''    platform?: string;\n  };\n};\n''',
        '''    platform?: string;\n    evidenceGrade?: "A" | "B" | "C" | "D";\n    evidenceLabel?: string;\n    evidencePolicy?: string;\n  };\n};\n''',
        "article source grade fields",
    )
    replace_once(
        updates,
        '''    keywords: uniqueKeywords([article.type, ...additionalKeywords]),\n''',
        '''    keywords: uniqueKeywords([\n      article.type,\n      ...(article.source.evidenceGrade\n        ? [`${article.source.evidenceGrade}级来源`]\n        : []),\n      ...(article.source.evidenceGrade === "D" ? ["待交叉验证"] : []),\n      ...additionalKeywords,\n    ]),\n''',
        "channel source grade filters",
    )
    replace_once(
        updates,
        '''    lastVerifiedAt: article.lastVerifiedAt,\n    lastVerifiedEstimated: article.lastVerifiedEstimated,\n  };\n''',
        '''    lastVerifiedAt: article.lastVerifiedAt,\n    lastVerifiedEstimated: article.lastVerifiedEstimated,\n    sourceGrade: article.source.evidenceGrade,\n    sourceGradeLabel: article.source.evidenceLabel,\n    sourceVerificationPolicy: article.source.evidencePolicy,\n  };\n''',
        "channel source grade mapping",
    )

    client = Path("components/channel-update-directory-client.tsx")
    replace_once(
        client,
        '''                    data-intelligence-source={item.source}\n                    data-intelligence-source-level={item.label}\n                    data-intelligence-context={item.context}\n''',
        '''                    data-intelligence-source={item.source}\n                    data-intelligence-source-level={item.sourceGrade}\n                    data-intelligence-source-grade={item.sourceGrade}\n                    data-intelligence-context={item.context}\n''',
        "channel source grade metadata",
    )
    replace_once(
        client,
        '''                        <span>{item.label}</span>\n                        <time\n''',
        '''                        <span>{item.label}</span>\n                        {item.sourceGrade && (\n                          <em\n                            className={styles.sourceGrade}\n                            data-source-grade={item.sourceGrade}\n                            title={item.sourceVerificationPolicy}\n                          >\n                            {item.sourceGrade}级 · {item.sourceGradeLabel}\n                          </em>\n                        )}\n                        <time\n''',
        "channel source grade badge",
    )

    css = Path("components/channel-update-directory.module.css")
    replace_once(
        css,
        '''.meta i {\n  border: 1px solid color-mix(in srgb, var(--blue) 55%, var(--border));\n''',
        '''.sourceGrade {\n  border: 1px solid var(--border);\n  padding: 2px 7px;\n  color: var(--muted);\n  font-style: normal;\n}\n\n.sourceGrade[data-source-grade="A"],\n.sourceGrade[data-source-grade="B"] {\n  border-color: color-mix(in srgb, var(--green) 55%, var(--border));\n  color: var(--green-bright);\n}\n\n.sourceGrade[data-source-grade="C"] {\n  border-color: color-mix(in srgb, var(--blue) 50%, var(--border));\n  color: var(--blue);\n}\n\n.sourceGrade[data-source-grade="D"] {\n  border-color: color-mix(in srgb, var(--faint) 70%, var(--border));\n  color: var(--faint);\n}\n\n.meta i {\n  border: 1px solid color-mix(in srgb, var(--blue) 55%, var(--border));\n''',
        "channel source grade styles",
    )

    workflow = Path(".github/workflows/scheduled-sync.yml")
    replace_once(
        workflow,
        '''      - tools/update_source_health.py\n      - tools/professional_media_progress.py\n''',
        '''      - tools/update_source_health.py\n      - tools/source_evidence.py\n      - tools/source_health_runtime.py\n      - tools/professional_media_progress.py\n''',
        "workflow source governance paths",
    )
    replace_once(
        workflow,
        '''            tools/update_source_health.py \\\n            tools/professional_media_progress.py \\\n''',
        '''            tools/update_source_health.py \\\n            tools/source_evidence.py \\\n            tools/source_health_runtime.py \\\n            tools/professional_media_progress.py \\\n''',
        "workflow source governance compile",
    )
    replace_once(
        workflow,
        '''            tests.test_source_health \\\n            tests.test_professional_media_progress \\\n''',
        '''            tests.test_source_health \\\n            tests.test_source_evidence \\\n            tests.test_source_health_runtime \\\n            tests.test_professional_media_progress \\\n''',
        "workflow source governance tests",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
