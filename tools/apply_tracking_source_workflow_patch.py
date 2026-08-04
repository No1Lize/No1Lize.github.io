#!/usr/bin/env python3
"""Temporary migration for tracking-discovery and scheduled-refresh workflows."""

from __future__ import annotations

from pathlib import Path


def patch_tracking_discovery() -> None:
    expression = lambda value: chr(36) + "{{ " + value + " }}"
    path = Path(".github/workflows/tracking-discovery.yml")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '''          python -m py_compile tools/enrich_tracking_institutions.py
          python -m py_compile tools/enrich_tracking_people_from_sample_companies.py''',
        '''          python -m py_compile tools/tracking_source_governance.py
          python -m py_compile tools/enrich_tracking_institutions.py
          python -m py_compile tools/enrich_tracking_people_from_sample_companies.py''',
        1,
    )
    text = text.replace(
        '''            tests.test_tracking_institution_people \\
            tests.test_tracking_sample_company_people \\
            tests.test_tracking_person_channels''',
        '''            tests.test_tracking_source_governance \\
            tests.test_tracking_institution_people \\
            tests.test_tracking_sample_company_people \\
            tests.test_tracking_person_channels''',
        1,
    )
    expand_marker = '''      - name: Expand tracking entities from public web sources
        id: expand'''
    before = '''      - name: Normalize automatic sources before discovery
        id: source-governance-before
        shell: bash
        run: |
          set -euo pipefail
          python tools/tracking_source_governance.py | tee /tmp/source-governance-before.json
          CHANGED=$(python -c "import json;print(str(json.load(open('/tmp/source-governance-before.json'))['changed']).lower())")
          echo "changed=$CHANGED" >> "$GITHUB_OUTPUT"

'''
    if expand_marker not in text:
        raise SystemExit("tracking discovery expand point not found")
    text = text.replace(expand_marker, before + expand_marker, 1)
    changes_marker = '''      - name: Consolidate discovery changes
        id: changes'''
    after = '''      - name: Normalize automatic sources after discovery
        id: source-governance-after
        shell: bash
        run: |
          set -euo pipefail
          python tools/tracking_source_governance.py | tee /tmp/source-governance-after.json
          CHANGED=$(python -c "import json;print(str(json.load(open('/tmp/source-governance-after.json'))['changed']).lower())")
          echo "changed=$CHANGED" >> "$GITHUB_OUTPUT"

'''
    if changes_marker not in text:
        raise SystemExit("tracking discovery changes point not found")
    text = text.replace(changes_marker, after + changes_marker, 1)

    start = text.index("      - name: Consolidate discovery changes\n")
    end = text.index("      - name: Validate the expanded config before committing\n", start)
    values = {
        name: expression(name)
        for name in (
            "steps.source-governance-before.outputs.changed",
            "steps.expand.outputs.changed",
            "steps.directory.outputs.changed",
            "steps.institutions.outputs.changed",
            "steps.team.outputs.changed",
            "steps.channels.outputs.changed",
            "steps.source-governance-after.outputs.changed",
        )
    }
    block = f'''      - name: Consolidate discovery changes
        id: changes
        shell: bash
        run: |
          if [ "{values['steps.source-governance-before.outputs.changed']}" = "true" ] || \\
             [ "{values['steps.expand.outputs.changed']}" = "true" ] || \\
             [ "{values['steps.directory.outputs.changed']}" = "true" ] || \\
             [ "{values['steps.institutions.outputs.changed']}" = "true" ] || \\
             [ "{values['steps.team.outputs.changed']}" = "true" ] || \\
             [ "{values['steps.channels.outputs.changed']}" = "true" ] || \\
             [ "{values['steps.source-governance-after.outputs.changed']}" = "true" ]; then
            echo "changed=true" >> "$GITHUB_OUTPUT"
          else
            echo "changed=false" >> "$GITHUB_OUTPUT"
          fi

'''
    text = text[:start] + block + text[end:]
    text = text.replace(
        '''          npm run validate:tracking
          npm run validate:taxonomy''',
        '''          python tools/tracking_source_governance.py --check
          npm run validate:tracking
          npm run validate:taxonomy''',
        1,
    )
    text = text.replace(
        "            git add config/user_tracking.json config/tracking_auto_discovery.json",
        '''            git add \\
              config/user_tracking.json \\
              config/tracking_auto_discovery.json \\
              public/data/source_health.json''',
        1,
    )
    text = text.replace(
        '''            git reset --hard origin/main

            if [ "$DISCOVERY_MODE" = "seed-only" ]; then''',
        '''            git reset --hard origin/main
            python tools/tracking_source_governance.py \\
              | tee /tmp/source-governance-before-replay.json

            if [ "$DISCOVERY_MODE" = "seed-only" ]; then''',
        1,
    )
    text = text.replace(
        '''            python tools/enrich_tracking_person_channels.py \\
              --max-tracks 20 | tee /tmp/channel-discovery-replay.json

            npm run validate:tracking''',
        '''            python tools/enrich_tracking_person_channels.py \\
              --max-tracks 20 | tee /tmp/channel-discovery-replay.json
            python tools/tracking_source_governance.py \\
              | tee /tmp/source-governance-after-replay.json

            python tools/tracking_source_governance.py --check
            npm run validate:tracking''',
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_scheduled_sync() -> None:
    path = Path(".github/workflows/scheduled-sync.yml")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '''      - tools/update_source_health.py
      - tools/source_evidence.py''',
        '''      - tools/update_source_health.py
      - tools/tracking_source_governance.py
      - tools/source_evidence.py''',
        1,
    )
    text = text.replace(
        '''            tools/update_source_health.py \\
            tools/source_evidence.py''',
        '''            tools/update_source_health.py \\
            tools/tracking_source_governance.py \\
            tools/source_evidence.py''',
        1,
    )
    text = text.replace(
        '''            tests.test_source_health \\
            tests.test_source_evidence''',
        '''            tests.test_source_health \\
            tests.test_tracking_source_governance \\
            tests.test_source_evidence''',
        1,
    )
    text = text.replace(
        '''      - name: Start a clean full-source status ledger
        run: python tools/prepare_full_refresh.py''',
        '''      - name: Require a normalized automatic source registry
        run: python tools/tracking_source_governance.py --check
      - name: Start a clean full-source status ledger
        run: python tools/prepare_full_refresh.py''',
        1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_tracking_discovery()
    patch_scheduled_sync()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
