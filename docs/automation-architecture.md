# Automation control plane and data lineage

## Purpose

VCIQ has multiple scheduled and change-driven data producers. The control plane gives those existing workflows one auditable contract without moving crawler logic into a new orchestrator.

The design has four invariants:

1. The registry describes automation; it does not execute arbitrary commands.
2. Existing domain workflows keep their current quality gates.
3. A failed or unverified run cannot update public lineage.
4. Static deployment never mutates committed `config/` or `public/data/`.

## Components

### `config/automation_jobs.json`

The registry is the source of truth for:

- task identity and ownership;
- Workflow path and trigger;
- dependencies;
- inputs and outputs;
- shared-output declarations;
- freshness SLA;
- timeout and retry policy;
- failure policy;
- publication quality gate;
- the four public research object types.

Duplicate output ownership is rejected unless every owner explicitly marks the output as shared. Dependency cycles and paths escaping the repository are rejected.

### `tools/run_pipeline.py`

The CLI exposes metadata operations only:

- `check` validates the registry and committed contracts;
- `start` creates a run context;
- `finalize` records a successful, quality-gated producer run;
- `refresh` observes current repository artifacts and rebuilds health/lineage;
- `build-provenance` records the exact static deployment source.

`finalize` requires `status=success`, `quality-gate=passed`, and all required outputs to exist.

### `tools/build_pipeline_health.py`

The observer computes:

- SHA-256 and byte size for each public managed artifact;
- producer task, run ID, code SHA, source ref and completion time;
- effective data timestamp;
- age against the strictest owning-job SLA;
- per-artifact, per-job and overall status.

When an unchanged artifact already has producer metadata, that producer is preserved. Otherwise the observer uses the last Git commit touching the file as a transparent bootstrap producer. It never invents a successful workflow run.

### Public snapshots

`public/data/data_lineage.json` is artifact-centric.

`public/data/pipeline_health.json` is task-centric.

The committed files begin as explicit bootstrap contracts. Producer workflows replace them only after successful data changes. Pages independently rebuild current versions inside `out/data/`, so the deployed observability endpoints always describe the exact source commit even when a producer has not yet adopted explicit finalization.

## Status semantics

| Status | Meaning |
| --- | --- |
| `healthy` | Required artifacts exist and remain inside their freshness SLA. |
| `stale` | At least one present required artifact exceeds its SLA. |
| `missing` | A required output does not exist. |
| `degraded` | Producer metadata reports a non-success state or a required dependency is unavailable. |
| `unknown` | The contract exists but there is not enough evidence to assert health. |

Optional advisory outputs may be missing without degrading the whole site.

## Run context

A run context contains:

```json
{
  "schemaVersion": 1,
  "pipelineVersion": "automation-control-plane-v1",
  "jobId": "public-intelligence-full-refresh",
  "runId": "gha:123456:1:public-intelligence-full-refresh",
  "codeSha": "...",
  "sourceRef": "refs/heads/main",
  "startedAt": "...",
  "completedAt": null,
  "status": "running",
  "qualityGate": "pending",
  "inputs": [],
  "outputs": [],
  "freshnessSlaHours": 30,
  "failurePolicy": "retain-last-good"
}
```

GitHub Actions run IDs are used when available. Local runs receive an explicit `local:` identity.

## Producer integration pattern

A producer determines whether its domain data changed first. Only then does it finalize the control-plane record:

```bash
SEMANTIC_CHANGED=...
if [ "$SEMANTIC_CHANGED" = "true" ]; then
  python tools/run_pipeline.py finalize <job-id> --quality-gate passed
  git add <domain outputs> \
    public/data/data_lineage.json \
    public/data/pipeline_health.json
fi
```

After a rebase, deterministic post-processing and finalization run again before amending the commit. This prevents shared lineage from being published against an obsolete repository head.

## Pages integration

The Pages job:

1. checks out the triggering SHA with full history;
2. validates committed data and the control-plane contract;
3. builds the static site;
4. verifies that `config/` and `public/data/` stayed unchanged;
5. writes current health and lineage into `out/data/`;
6. writes `out/build-provenance.json`;
7. uploads and deploys only after all gates pass.

A failed build therefore leaves the previous Pages deployment intact.

## Extension rules

When adding a producer:

1. add exactly one registry job;
2. declare every repository output;
3. mark shared output ownership on all owners;
4. define a measurable freshness SLA;
5. use `retain-last-good` unless the output is strictly advisory;
6. call `finalize` only after the existing quality gate passes;
7. add the control snapshots to the same atomic commit;
8. add regression coverage for dependencies and workflow wiring.

The control plane should not grow a generic command executor. Domain workflows remain explicit and reviewable.
