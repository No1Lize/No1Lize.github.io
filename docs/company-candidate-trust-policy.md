# Company candidate trust policy

VCIQ uses exception-based review for new company entities.

## Lane A: audited manual / trusted

A company explicitly added through an **audited human capture** does **not** require a second human review when shared entity resolution still resolves the identity to a company.

Flow:

```text
human capture (capturedBy recorded)
  -> entity/type conflict check
  -> accepted automatically
  -> onboarding/profile quality gate
  -> formal company publication
```

The automatic acceptance is a versioned review decision. It records who added the company and why the second review was skipped. It does not bypass the formal profile requirements for canonical name, slug, official homepage, source traceability, or profile quality.

A manual company remains review-gated when entity resolution finds a person/topic match, multiple competing aliases, a versioned reclassification, an automated/anonymous capture actor, or another unresolved identity conflict.

`sampleCompanies` is **not** treated as human provenance. Reconciliation and automatic discovery can also write this derived tracking field. A config-only value therefore stays pending unless a separate audited human provenance record exists.

## Lane B: automatic discovery

Companies found only by crawler/article evidence continue to use the normal candidate review path.

```text
automatic discovery
  -> evidence/materiality threshold
  -> pending review
  -> accepted / rejected / merged
  -> onboarding/profile quality gate
  -> formal company publication
```

Automatic discovery must never inherit manual trust merely because it has a high score, a primary source, or appears in `sampleCompanies`.

## Precedence

Final versioned decisions always win. `accepted`, `rejected`, `merged`, and `published` decisions are not overwritten by the manual-trust automation.

The resulting invariant is:

```text
audited human intent is not reviewed twice;
automation is reviewed before promotion;
ambiguous provenance is reviewed before promotion;
identity ambiguity is reviewed before publication;
quality gates apply to every formal profile.
```
