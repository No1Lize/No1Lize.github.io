#!/usr/bin/env python3
"""Patch venture normalizer CLI to converge derived quality state before exit."""

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("normalize_venture_profiles.py")

OLD = '''    payload = json.loads(args.input.read_text(encoding="utf-8"))
    original = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    catalog_text = args.catalog.read_text(encoding="utf-8")
    normalized, stats = normalize_payload(payload, catalog_text)
    normalized_text = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    already_normalized = original == normalized_text
    quality = normalized.get("qualityGate", {})

    if args.check:
        passed = bool(quality.get("passed", False)) and already_normalized
        print(json.dumps({
            "passed": passed,
            "alreadyNormalized": already_normalized,
            "stats": stats,
            "qualityGate": quality,
        }, ensure_ascii=False))
        return 0 if passed else 1

    args.input.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
    )
    print(json.dumps({
        "stats": stats,
        "passed": quality.get("passed", False),
        "changed": not already_normalized,
    }, ensure_ascii=False))
    return 0 if quality.get("passed", False) else 1
'''

NEW = '''    payload = json.loads(args.input.read_text(encoding="utf-8"))
    initial_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    catalog_text = args.catalog.read_text(encoding="utf-8")

    if args.check:
        normalized, stats = normalize_payload(payload, catalog_text)
        normalized_text = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        already_normalized = initial_text == normalized_text
        quality = normalized.get("qualityGate", {})
        passed = bool(quality.get("passed", False)) and already_normalized
        print(json.dumps({
            "passed": passed,
            "alreadyNormalized": already_normalized,
            "stats": stats,
            "qualityGate": quality,
        }, ensure_ascii=False))
        return 0 if passed else 1

    combined_stats: dict[str, int] = {}
    stable = False
    iterations = 0
    for iterations in range(1, 4):
        before = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        payload, stats = normalize_payload(payload, catalog_text)
        for key, value in stats.items():
            combined_stats[key] = combined_stats.get(key, 0) + int(value)
        after = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if after == before:
            stable = True
            break

    final_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    quality = payload.get("qualityGate", {})
    args.input.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
    )
    passed = bool(quality.get("passed", False)) and stable
    print(json.dumps({
        "stats": combined_stats,
        "passed": passed,
        "changed": initial_text != final_text,
        "stable": stable,
        "iterations": iterations,
    }, ensure_ascii=False))
    return 0 if passed else 1
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Venture normalizer fixed-point CLI already applied.")
        return
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"expected one normalizer CLI block, found {count}")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied venture normalizer fixed-point CLI.")


if __name__ == "__main__":
    main()
