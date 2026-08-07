# Company candidate trust policy

VCIQ uses exception-based review for new company entities.

## Lane A: audited manual / trusted

A company explicitly added through an **audited human capture** does **not** require a second human review when shared entity resolution still resolves the identity to a company.

Flow:

```text
human capture (capturedBy recorded)
  -> entity/type conflict check
  -> accepted automatically
  -> verified automatic onboarding
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
  -> verified automatic onboarding
  -> onboarding/profile quality gate
  -> formal company publication
```

Automatic discovery must never inherit manual trust merely because it has a high score, a primary source, or appears in `sampleCompanies`.

## Verified automatic onboarding

An `accepted` company should not require the administrator to retype a profile when public primary evidence can establish it safely. The automatic profile preparation path is therefore deliberately evidence-first:

```text
accepted
  -> exact existing-registry check
  -> exact official-source or Wikidata identity
  -> fetch official homepage
  -> verify name on official page
  -> verify tracked sector on official page
  -> synthesize summary/product from official page only
  -> verify model support quotes exist verbatim on that page
  -> requested
  -> existing publication quality gate
  -> published
```

The language model is a **bounded extractor/summarizer**, not an identity or source authority. It cannot invent or select a homepage. It only runs after deterministic public-source verification, and its factual output is rejected unless it supplies support snippets found on the fetched official page.

Automatic onboarding fails closed. The company remains `accepted` and waits for exception handling when the public identity is ambiguous, the official site cannot be established, the official page does not support the tracked sector, the model cannot ground its output, or the resulting slug conflicts with another formal entity.

Investment institutions are also held out of the company-profile path rather than being silently published as startup companies. Existing formal company identities are merged instead of duplicated.

## Precedence

Final versioned decisions always win. `accepted`, `rejected`, `merged`, and `published` decisions are not overwritten by the manual-trust automation. Existing `requested`, `failed`, `merged`, and `published` onboarding state is not overwritten by automatic profile preparation.

The resulting invariant is:

```text
audited human intent is not reviewed twice;
automation is reviewed before promotion;
ambiguous provenance is reviewed before promotion;
identity ambiguity is reviewed before publication;
models summarize verified evidence but do not establish identity;
quality gates apply to every formal profile.
```
