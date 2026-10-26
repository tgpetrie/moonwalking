# Local-model source-audit pilot

Frozen 2026-10-26 before the scored 20-case runs. A single Qwen 9B Render
warm-up checked API availability and latency before this protocol. Its output
is not included in the scored results. No model weights or facts are tuned.

## Assignment and limits

- Run the installed `qwen3.5:9b` as a source extractor and `qwen3:14b` as a
  separate check, sequentially on this PC's RTX 3060 12 GB to avoid concurrent
  model residency. Unload the pilot's first model before loading the second.
- Each model receives the same fixed 20 packets from the saved source review:
  public Coinbase identity context, candidate scope, metric availability,
  dates, missingness, zero counts, source URLs and one authored claim to assess.
  This is candidate-evidence extraction, not independent provider discovery.
- No inference request includes expected answers. Each uses a fresh conversation,
  temperature 0, a fixed seed, a 4,096-token context and a 320-token output cap.
  Models receive no tools, filesystem access or network tools. All inference
  requests go only to `127.0.0.1:11434`; no holdings or trade data is used.
- Labels distinguish observed values, an explicitly empty returned series, and
  unverified coverage. HTTP errors or a missing catalog candidate do not prove
  global absence. The task also checks parent/child, chain/app and migration
  distinctions. Authored probes are not attributed as quotations from Gemini.
- Save first responses, errors, request settings, server timings and evaluations.
  Do not retry incorrect answers or select cases after seeing results.

## Evaluation

Each case has five exact gold fields: product ID, TVL/fee/revenue status, and
claim verdict. Report every field's accuracy, exact cases, valid citation-ID sets,
errors and wall time. A citation ID is checked for existence, not semantic
entailment: a real ID alone does not prove a correct explanation. Notes need
human review. Both models are Qwen-family models, not statistically independent
validators; agreement is not evidence of truth.

This is a small diagnostic corpus, containing 20 known source cases and supplied
rules, not a broad accuracy estimate. Gold-label disagreements and unsupported
notes must remain visible. This does not measure predictive value of a coin
score. Numerical calculations and score evaluation remain deterministic code.

## Run

From the repository root, with Ollama already running:

```powershell
python -B scripts/local_ai_source_audit/run.py --model qwen3.5:9b
# Unload the pilot's 9B model before the 14B run on this 12 GB GPU.
python -B scripts/local_ai_source_audit/run.py --model qwen3:14b
python -B scripts/local_ai_source_audit/run.py --summarize
# Or run/resume the whole queue, releasing each model after its batch:
python -B scripts/local_ai_source_audit/run.py --all
```

`BENCHMARK.json` is refused if its frozen contents differ. Existing saved cases
are skipped to resume after interruption; first model responses are retained.
Outputs: `docs/research/results/local_ai_source_pilot_v2_20261026/`.

## Packet correction A1

During the first 9B batch, examination of its first two responses exposed an
input-packaging bug: the provider `id` overwrote the intended evidence `id`, so
different metric records for a parent protocol shared the same label. The first
batch is preserved under `local_ai_source_pilot_20261026/` as a malformed-packet
diagnostic, **not a model-performance result**. No 14B run used that format.

V2 separates `provider_id` from the unique evidence labels `tvl`, `dailyFees`,
and `dailyRevenue`, and explicitly names each metric. Five offline tests check
the input namespace, parent IDs, gold-answer exclusion, citation scoring, and
empty versus unverified series. The 20 claims and gold answers are unchanged.
All 20 cases are rerun with the corrected format; failures are not selectively
retried. V2 is a post-diagnostic pilot, not an untouched holdout evaluation.

## Results

Both fixed runs completed locally, with first responses preserved for every case.
No scored inference request failed or required a retry. Ollama version 0.40.6;
base models `qwen3.5:9b` and `qwen3:14b`. These are two actual inference workers,
not additional names for their `local-assistant` / `local-qwen14b` wrappers.

| V2 measurement, same 20 cases | Qwen 3.5 9B | Qwen 3 14B |
|---|---:|---:|
| Parsed JSON responses | 20/20 | 20/20 |
| Objective fact-field matches (product + three availability fields) | 68/80 | 77/80 |
| TVL status matches | 17/20 | 20/20 |
| Fee status matches | 16/20 | 19/20 |
| Revenue status matches | 15/20 | 18/20 |
| Reference claim-label agreement | 17/20 | 17/20 |
| Valid evidence-ID sets | 11/20 | 17/20 |
| Cases passing all automated checks | 7/20 | 13/20 |
| Sum of case wall times | 89.2 seconds | 195.1 seconds |

The 9B model was warm from its diagnostic run; the 14B model's first case includes
loading. Wall times are operational observations, not a controlled hardware
benchmark. The 27B and vision models were not loaded for this text-only pilot.

### What the errors show

- The 9B model frequently substituted fabricated citation labels such as
  `series_returned` for actual evidence IDs, and sometimes confused observed metric
  availability with uncertainty about token identity. The existence checks catch
  those outputs; they must not become facts in a coin score.
- The 14B model performed better on fact fields and evidence IDs, but its PERP
  explanation incorrectly inferred that observed zero values indicate missing
  days were imputed. The source does not establish that. A syntactically valid
  citation or a correct final label does not establish a grounded explanation.
- Claim labels are provisional human references, not mathematical truth. FET's
  authored sentence has a negation/scope ambiguity; VET, PERP and MKR can admit
  different readings of "contradicted" versus "insufficient evidence". Preserve
  raw agreement counts, but do not interpret these disagreements as a general
  factual error rate or adjust labels to improve a model's score. A future
  evaluation needs clearer claims and fresh cases.

`REVIEW_QUEUE.json` combines deterministic metric facts with both models' draft
claim assessments. It contains 20 records, **13 high-priority** cases flagged for
factual-field conflicts, invalid citation IDs or model disagreement. Every draft
interpretation remains subject to review. The queue does not change scoring code.

### Concrete work split after the pilot

1. **Deterministic code** remains authoritative for source IDs, numeric metrics,
   dates, missingness and scoring calculations. There is no benefit in letting a
   model overwrite facts already parsed exactly from JSON.
2. **9B local worker:** fast draft flags and simple source-text triage, with strict
   validation and no automatic promotion to the evidence table.
3. **14B local worker:** first choice for a more careful source-audit draft and
   difficult parent/child, chain/app or migration cases, alongside deterministic
   checks and human review. Its outputs are still proposals.
4. **Claude/Codex:** review flagged cases and define actual source/score experiments.
   Neither local-model agreement nor this extraction benchmark is predictive
   validation of the numeric coin score.

The reusable `--all` queue runs models sequentially, saves every first response,
resumes without repeating saved cases and releases models for which it actually
made a request. A fully cached resume does not unload someone else's loaded model.
Eight offline harness tests pass, including preservation of parsed facts and
the resume ownership guard.
The completed pilot models were unloaded after work, freeing the GPU for other
tasks. No global Ollama settings, model installation, application, numeric scoring
model, frozen panel or collector store was changed.
