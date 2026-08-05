# Research Agent v1

Research Agent v1 turns the repository's structured entity snapshots into a daily, evidence-linked research brief. It does not crawl new sources itself and does not replace the existing refresh pipeline.

## Pipeline

1. Build stable snapshots for venture companies, institutions, listed-company profiles, people, capital events, and regulatory disclosures.
2. Remove execution-only timestamps and normalize unordered arrays.
3. Compare with the previous persisted snapshot. On the first run, bootstrap from `HEAD^` so the current entity library is not misclassified as entirely new.
4. Rank material changes with deterministic rules.
5. Build an evidence package from official pages, regulatory documents, and the repository's graded sources.
6. Send only the bounded evidence package to SiliconFlow's OpenAI-compatible chat-completions endpoint.
7. Reject model items that do not reference a valid evidence ID.
8. Publish static JSON for the Next.js export.

## Required repository secret

Create a GitHub Actions repository secret named:

```text
SILICONFLOW_API_KEY
```

Do not place the key in source files, workflow YAML, JSON outputs, issues, or logs. Rotate any key that has already been pasted into a chat or other plaintext surface.

The workflow uses these non-secret defaults:

```text
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V4-Flash
RESEARCH_AGENT_REASONING_EFFORT=high
```

## Outputs

- `public/data/research_agent_daily.json`: current brief, evidence, change log, and a rolling 30-run history.
- `public/data/research_agent_snapshot.json`: normalized comparison baseline for the next run.
- `/research-agent/`: static research interface.

## Failure policy

A missing key, API timeout, malformed response, or invalid evidence reference does not block the site's primary data refresh. The generator publishes an explicit deterministic fallback with `runStatus` describing the reason. No fallback content is presented as model analysis.

## Local validation

```bash
python -m py_compile tools/research_agent.py
python -m unittest tests.test_research_agent
python tools/research_agent.py --offline
python tools/research_agent.py --check
```

The output is research material only and is not investment advice.
