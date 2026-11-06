# Planned inventory and timed input evidence, stage 1

November 4, 2026 (Pacific). Implementation **`8607a36`** adds a bounded,
offline foundation for the eligibility producer. **1,195 targeted tests pass**,
including 32 new cases, on Windows Python 3.12.10 / pytest 8.3.5. Black 24.8.0,
guardrails and all 11 historical hashes pass. Subsequent independent review `f1ab7d5` is accepted as `086eb20`;
1,241 targeted tests pass with no code patch. Read
[the November 6 acceptance](INSTANT_INPUT_REVIEW_ACCEPTANCE_20261106.md).

This stage completes planned-slot accounting and measured packet/trade
processing records. It does **not** complete positive study eligibility:
baseline/feature evidence, full input-health requirements and publication
policy are still missing. Every planned row explicitly reports unavailable
eligibility. It supplies no boolean bridge into the directional reporter.

Code: `scripts/scoring_experiment/instant_input_evidence.py`.
[Contract](INSTANT_INPUT_EVIDENCE_CONTRACT_V1_DRAFT.json),
[checks](results/instant_input_evidence_20261104/CHECKS.json) and
[review prompt](../ai/CLAUDE_INPUT_EVIDENCE_REVIEW_20261104.md).

## Inventory accounting

The intent is the static cross product of declared products, every 5s cutoff
in `[first_cutoff, stop_cutoff)` and both directions. BTC is required as the
benchmark. Every expected row is retained, including products with no packet,
missing quotes or no proven trade interval. Empty observations do not shrink
the declared inventory or become healthy zero counts.

The canonical intent and its hash are separate from the time the recorder
actually loaded it. A file hash does not prove it was declared in advance.
`inventory_precedes_first_cutoff` requires the measured loading time to be
strictly earlier. Loading an old plan during replay records today's time and
does not claim prospective declaration. This validates completeness relative
to the submitted plan; it cannot independently prove that the plan contains
the intended exchange universe. That universe still needs an external,
predeclared identity/source review.

Limits are 10,000 inventory rows, 32 products, the existing 100,000-packet
monitor bound and existing book-level bounds. These are offline guards, not
a measured one-hour capacity profile or new capture permission. A tape must
start at local receipt sequence 1 and remain contiguous. Bounds, malformed
packets or clock regression fail the artifact closed. Sealing requires all
planned cutoff times to have been reached; no prefix is certified a complete capture.
An empty tape can yield complete **inventory accounting** with all rows
unavailable; it is never called a complete or healthy capture.

## Processing and component evidence

Packet evidence stores receipt sequence/time, measured processing start and
completion, availability at least receipt plus 1ms, and canonical envelope
hash. Unique live-match rows retain their first receipt, packet completion,
connection and continuity epoch, exact Decimal price/size and inverted maker
side. Unknown sides remain separate. REST recovery, ticker sizes and
`last_match` do not create execution rows; duplicates never move first receipt.
Completion measures book/trade payload processing, not disk commit or durable
publication. Injected clocks remain trusted synthetic-test inputs.

Coin and BTC evidence are computed separately:

- The quote component uses the existing last processed book view and original
  observation age. Its selected state and heartbeat must also have completed
  this producer's processing by the requested knowledge time. A heartbeat
  cannot refresh quote age; an unfinished quote cannot borrow book-only
  completion. No continuous 30s F3 path is certified.
- The 30s trade component uses exact receipt-ID proofs plus completed trade
  rows, scoped to the verifying connection and continuity epoch. A first
  receipt at a shared-millisecond reset stays in its original epoch and cannot
  be certified by the following epoch. Known raw counts remain diagnostic;
  verified counts/amounts stay null without these checks. Only a proven empty
  receipt window becomes zero. Unknown taker side prevents signed-flow use.

`checkpoint(cutoff)` freezes the full product/direction cohort with component
knowledge at that cutoff and a separately measured assessment-completion
time. Returned rows are frozen and their nested component payload is serialized;
decoded copies cannot mutate them. Later packets, conflicts or failures never
rewrite the frozen cohort. Local logger/clock corruption still fails the whole
artifact closed, rather than exporting earlier rows from a failed run.

`component_evidence(product, cutoff, asof=later)` is a separately marked later
diagnostic. For a window ending at 30,000ms, its closing heartbeat at 30,000ms
is not available before 30,001ms even with no processing delay. The later
diagnostic can then report a proven zero; the frozen 30,000ms row remains
unproven. Neither result is full-feed or quote-continuity certification.

## API and offline artifacts

```python
from instant_input_evidence import InputEvidenceRecorder

recorder = InputEvidenceRecorder(products, first_cutoff, stop_cutoff)
for saved_envelope in saved_packets:
    recorder.ingest(saved_envelope)
report = recorder.seal()
```

The CLI takes a saved JSONL/gzip tape and a JSON inventory containing
`products`, `first_cutoff` and `stop_cutoff`:

```sh
python scripts/scoring_experiment/instant_input_evidence.py packets.jsonl.gz --inventory inventory.json --out-dir ../new-evidence-output
```

Output must be new and outside both input directories. It contains
`packet_processing.jsonl`, `trade_processing.jsonl` and `REPORT.json` with
inventory, complete planned rows, source/ledger hashes and closed gates.
Input hashes are checked before/after. Failures retain `FAILURE.json`; a
failed/partial output is not an eligibility artifact. Output files are written
at finalization, so the ledger does not establish durable availability at the
earlier processing times. No socket, account, production or database is opened.

## Review and remaining work

The 32 new cases include synthetic CLI round trip, planned omissions,
payload completion versus book completion, late proofs, epoch-boundary
certification, immutable cohorts, exact signed amounts, unknown sides,
deduplication/conflicts, stale and missing benchmark quotes, caps and clocks.
The epoch-boundary counterexample failed during implementation before the new
layer's owner/epoch check and passes afterward. Existing adapters/contracts,
targets/V1/V2, historical results, backend and frontend are unchanged. No real
capture/replay, market outcome experiment, fit, native Mac or full-suite run
is claimed. All new evidence needed for review is generated by committed tests.

The stage-1 review is complete. Next: build actual timed baseline and
F1-F5 evidence and declare publication/entry/age policy. Do not infer warmup
from elapsed time, turn scoped ID checks into full health, or fabricate ready
features. Later grading, real upstream connection identity, streaming limits
and durable publication remain open. Preserve the original feed gate, >=62
complete warmup minutes, locked historical validation and V1 default. The
study is unfrozen and fitting/live scoring remain unchanged.
