# Automation publication handoff

VCIQ public data publication follows a fail-closed handoff:

1. Reconcile tracked entities to a fixed point.
2. Run `Refresh public intelligence` when tracking scope changes.
3. Require the refreshed article snapshot to match the canonical tracking configuration and pass coverage/quality gates.
4. Re-run entity reconciliation against the refreshed snapshot.
5. Dispatch `Build and deploy GitHub Pages` only after the tracking scope is stable.

## GitHub Actions recursion constraint

Repository writes performed with the workflow `GITHUB_TOKEN` do not recursively trigger ordinary push/workflow-run chains in every downstream case. Production automation therefore must use an explicit `workflow_dispatch` handoff whenever one bot-driven workflow depends on another workflow running next.

Do not weaken `validate-tracking-snapshot.mjs` to compensate for a missing handoff. A stale snapshot must remain non-deployable.

## Recovery invariant

If a full refresh completed successfully and committed a new `public/data/articles.json`, but no later Pages run exists for the resulting `main`, create an explicit publication handoff rather than rebuilding or editing the data by hand.
