# Local chart narration connected — 2026-10-19

The AMP scheduled worker now uses the already installed Ollama base model
`qwen3.5:9b`. The inspected local server reported version 0.40.6 and model digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.
No model download, API key, cloud call or new service was introduced.

## What the model does

`scripts/chart_narration.py` builds a sentence catalog from the deterministic
`moonwalking.chart-evidence/v1` packet. The model selects and orders evidence IDs;
Python supplies all displayed wording, prices, dates, distances and qualifications.
Raw generated prose is never displayed. The model chooses two calculated price
references alongside the required source range. All current-position and limitation
facts are mandatory. Range context renders before its calculated levels. A beyond-high
extension requires the selected-high reference as well.

This is bounded explanation selection, not an independently researched forecast.
The model cannot add probabilities, arrival dates, causes or trading instructions.
Its selection is not evidence that the chosen references are more likely to occur.

## Local request and validation

Requests use the fixed `http://127.0.0.1:11434` endpoint with proxies disabled and
redirects rejected. `/api/tags` must identify the exact installed model. `/api/chat`
uses structured JSON output, per-topic ID enums, temperature 0, context 4096,
output limit 384 tokens, thinking disabled, streaming disabled and keep-alive one
minute. The model request timeout is 45 seconds; inventory timeout is three seconds.
These parameters follow the [Ollama chat API](https://docs.ollama.com/api/chat)
and [structured output documentation](https://docs.ollama.com/capabilities/structured-outputs).

Validation rejects unknown keys, duplicate JSON keys, incorrect topic order,
unknown/repeated/wrong-topic IDs, missing required context, another model's response,
incomplete or length-stopped output, and responses exceeding one MiB. No tools,
external retrieval, credentials or private portfolio context are supplied.

## Worker, cache and fallback

`scripts/chart_worker.py` saves `narration_detail` with the evidence and status in
the existing worker transaction. The scheduled task reads this checkout, so its
existing hourly/sign-in invocation now includes narration.

`narration_detail.evidence_sha256` fingerprints the rendered fact catalog, configured
model name and renderer source. It is not the raw history-file checksum. When this
fingerprint is unchanged, a previously accepted plan is validated again and rendered
from the current catalog, without an HTTP/model request. Cached output retains its
original generation time, model digest and generation duration. A cached label does
not claim that Ollama is currently reachable.

Unavailable, timed-out or invalid model output produces an explicitly labelled
deterministic fallback. The data-refresh/evidence job can still succeed. The dashboard
shows the saved product, model, generation time, cached/fallback state and three
explanation paragraphs. Running, stale and error states identify saved explanations
as previous output. Background refresh still does not replace the user's active chart.
Ollama must be available for a new model selection; no service-startup settings changed.

## Observed verification

- The first real model plan put macro IDs in the limitations paragraph. Validation
  rejected it and the worker used fallback. Per-topic schema constraints were tightened.
- Subsequent real AMP calls were accepted. Observed warm generation durations were
  approximately 3.8–4.9 seconds; these are local smoke observations, not a benchmark.
- An actual `Moonwalking-Chart-AMP-USD` scheduled-task run finished with result 0 and
  `local_ai` narration. A subsequent unchanged worker run returned `cached`, preserving
  the accepted generation timestamp. Prices and analysis were unchanged on those runs.
- `npm run verify`: 553 frontend tests, token/manifest synchronization and production
  build passed. Existing Browserslist, bundle-size and act warnings remain.
- `python -m unittest scripts/test_chart_narration.py scripts/test_chart_worker.py -q`:
  41 offline tests passed, including 23 narration tests. No live model is needed by tests.
- `npm run guardrails` and `git diff --check` passed. An independent local agent reviewed
  text/number boundaries, cache rendering, fallback and AI-state labels with no actionable
  findings, and independently ran the 23 narration tests. Claude/Gemini did not review
  this narration implementation.

Runtime data and smoke artifacts remain in the ignored `frontend/.runtime/` directory.
No production deployment, main merge, owner data-store access or predictive validation
is part of this integration.
