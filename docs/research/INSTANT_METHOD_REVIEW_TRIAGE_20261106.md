# Current Gemini methodology review: dispositions and next implementation

November 6, 2026 (Pacific). The new [29-file response](reviews/GEMINI_METHOD_REVIEW_20261106.md)
is received and reconciled against packet `fee55a7`. Read its
[archive manifest](reviews/GEMINI_METHOD_REVIEW_20261106_MANIFEST.json).
This is distinct from the already reconciled October 30 eight-file response.
All 29 supplied path/hash entries contain the expected packet metadata;
Source 07 also contains a shortened erroneous token, preserved verbatim with
its correct explicitly supplied hash. This is metadata comparison, not proof
of Gemini's independent hash computation. Gemini reports no test execution or
empirical performance verification. The original unamended proposal remains absent.

**Disposition:** retain the existing target/diagnostic architecture and the
five fixed candidate formulas. Accept the two-clock issue as the next design
dependency, with the corrections below. Do not freeze new numerical limits,
change an existing availability field, or enable fitting/collection/live use.
The [synthetic checks](results/instant_method_review_20261106/CHECKS.json)
test contract boundaries, not predictive benefit.

## Accepted and already implemented

- Keep V1 default and opt-in V2 `verified_forward(b,H)` as the fixed-cutoff
  pointwise research outcome at 300s and 900s. It measures future displacement
  and retention; a high hit rate alone does not establish early discovery,
  physical onset or an executable return from publication.
- Keep whole-reference-window strict timing, its separately named forward-peak
  fraction and explicit null/left-censor reasons. Do not reopen the old S1
  substitution or let associated catalog coverage forgive pointwise failure.
- Keep deterministic earliest-unused association, own-direction gradability,
  per-board time unions, paired ranker comparisons and visible natural coverage.
- Preserve the input ledger's actual completion times and epoch attribution.
  Stage 1 is intentionally incapable of positive study eligibility; the review
  does not convert scoped ID evidence into full health.
- Preserve fixed 30s/180s input windows and existing sigma/pace cutoffs. Sigma,
  beta and spread are shared feature/target controls, so ablations and stratum
  reporting are necessary. Models and weights remain separate from broader
  short/medium/long outlook scoring.

## Required corrections to the response

### C1. Availability cannot be redefined as receipt-only

The proposed separation of feature content cutoff `b` from later proof and
decision completion is useful. Its explanation of the existing `Sample` field
is incorrect: `instant_targets.TargetEvaluator._quality` rejects
`row.available_ts_ms > row.ts_ms` as `future_receipt`, even when grading occurs
much later. `_baseline_quality` also rejects a baseline/beta unavailable at
the anchor. `instant_directional_exposure._slots` requires eligibility
availability at or before its cutoff. `PublicationTiming` represents later
proofs, but explicitly marks legacy cutoff compatibility false and never
enables fitting. Chronology validation is not a semantic bridge into either API.

Four synthetic V1/V2 × up/down cases confirm that an otherwise ready label
becomes unavailable when the anchor input is known 180ms late. Another case
confirms that a valid publication timeline does not make the same late
eligibility record acceptable to the existing directional reporter.

**Next design:** a separately versioned timed-component/decision contract must
retain observation cutoff, evidence knowledge, computation completion and
publication as separate clocks. Observations received at/after `b` cannot enter
its features, although later evidence may verify a prior receipt interval.
Do not move late trades into earlier volume buckets or rewrite frozen cohorts.
Existing cutoff inputs and baseline provenance stay intact. Later grading and
any publication-anchored entry/outcome require explicit adapters; existing
`evaluate(..., asof=later)` alone does not grant the proposed semantics.

### C2. 2,500ms is a proposal, not a measured sufficient budget

The preserved hour's 965.5ms median / 1,993ms maximum is additional receipt wait
for the earliest interval in each merge. It excludes a general guarantee about
boundary-heartbeat phase, computation, queues, serialization and publication.
For example, a hypothetical 1,000ms boundary wait plus 1,993ms additional merge
wait already totals 2,993ms. The sixth synthetic case records that chronology
and correctly fails a supplied 2,500ms diagnostic bound. This does not estimate
its real frequency or select a different cap.

Defer a numerical budget until a predeclared data-only source/latency protocol
specifies measurement, busy-period/missingness strata and allowed exclusions.
A policy may reject late rows; it must report them, not guarantee every row
publishes within the budget. Engineering safety bounds, a pilot diagnostic
criterion and a frozen study age limit are different decisions.

### C3. Publication diagnostics need actual quotes and return units

`floor(published/5000)*5000` identifies a grid boundary, not the last quote.
Use actual receipt and processing timestamps plus age. A first post-publication
quote can provide a separately named delayed quote benchmark; it is not an
executed fill or the price known at publication. Its delay/selection rule and
maximum wait must be declared, including how missing or stale entries are counted.

The response's bare `mid_after - mid_at_b` has price units, not basis points.
For a mid-price diagnostic, declare a normalized, direction-signed simple or
log return and multiply by 10,000. A side-aware execution-cost scenario needs
declared bid/ask entry/exit rules, fees and limitations; L1 observations do not
prove a fill, depth, impact or executable profit. If entry is delayed to `t_e`,
an outcome ending at `t_e+H` has a different maturity from `published+H` and
`b+H`. Keep all named estimands separate.

### C4. Unmeasured sources and new gates remain proposals

The pinned hour measured ticker-derived endpoint freshness, not a real
`level2_batch` capture. Its thin-product staleness cannot be presented as a
measurement of both channels. Sampled carried-book integration also does not
establish continuous physical book validity or intrabatch paths.

F4's suggestion to align candle end with sigma's earlier endpoint is a policy
choice, not an implemented requirement. The draft says prior closed candles;
freeze candle source, half-open intervals, alignment and completion before use.
Receipt-built OHLC must come from actual trades, with verified empty intervals
kept empty. Merely using the same store does not prove causal availability.
Similarly, a new F1 minimum-trade gate, liquidity thresholds, a 5-product/100-event/
50-alert minimum, stage thresholds, ±5 clipping, nonnegative weights and model/
regularization/calibration choices have not been adopted. Do not silently add
them to the current four-product diagnostic or change the original failed gate.

## F1–F5 implementation/evaluation guardrails

The exact formulas remain those in section 3 of the
[consolidated candidate](INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md). These are
mechanism hypotheses, not evidence of informed trading, catalysts or spoofing.

| Feature | Required comparison and evidence |
|---|---|
| F1 acceleration | Compare against current 30s velocity plus F5 on synchronized midpoint endpoints. Test incremental value of rate change, not velocity level; preserve sigma-floor and extension strata. |
| F2 signed participation | Compare against unsigned USD pace and counts, with fixed count/positive-denominator requirements and explicit unknown-side availability. Signed flow must add benefit beyond activity on the same causal rows; the response's F2 table omits a full coverage-control cell, so retain these controls explicitly. |
| F3 sampled pressure | Compare the full 30s receipt-state integral against spread plus F2. Carry original observation ages; any stale/unknown positive-duration segment makes it unavailable, with no shortened-window renormalization. Record latency and source identity separately from the feature value. |
| F4 active compression/expansion | Compare against the expansion interaction alone plus F1/sigma. Keep real traded-candle counts and outage exclusions; a sparse or empty book is not evidence of compression. Candle alignment remains to be declared. |
| F5 market relative | Compare against raw signed 180s coin return, with beta fallback/BTC-regime controls. Report residual-label performance and separately named raw/net cost-scenario returns so matching a residual-defined target is not mistaken for execution benefit. |

For every feature, support requires prespecified meaningful incremental benefit
with matched coverage/burden and paired uncertainty. Robust harm can reject the
declared mechanism; an upper bound below a prespecified meaningful benefit can
reject that benefit. A zero/negative point estimate alone or an interval spanning
both zero and meaningful benefit remains inconclusive. Do not choose whichever
of IC, Top-K, horizon, direction or subgroup looks best after validation.

## Freeze order and immediate next implementation

1. Implement timed baseline/component evidence under separate provenance and
   completion clocks. Preserve 60 closed minute returns and 120 completed
   nonoverlapping pace windows. Never infer warmup from elapsed time or relabel
   a late baseline as known at `b`. This implementation work can proceed without
   choosing weights or a numerical publication budget.
2. Specify the new delayed-decision/grading interfaces, F3 piecewise-constant
   boundaries and F4 candle source/alignment before connecting positive eligibility.
   The present ledger and directional report retain their existing semantics.
3. Before any new source pilot, predeclare the sources/universe, full-health
   evidence, real connection IDs, streaming/storage/durability profile and latency
   diagnostic criteria. Preserve the original four-product verdict; no new capture
   is authorized by this review.
4. Before an outcome study, freeze feature/missingness/stage rules, ranker roster,
   four direction/horizon tables, alert cooldown, exposure/burden estimands,
   discovery split/purge and uncertainty. Future outcome missingness cannot shrink
   decision exposure. Report both ungradable burden and its uncertainty; failure
   count divided by board hours is a descriptive observed burden, not missingness-
   adjusted operational performance when many alerts remain ungradable.
5. Before fitting/fresh validation, freeze a primary effect/comparator, model and
   readiness/power rules. Fourteen valid shadow days are a starting collection
   protocol, not demonstrated power for five marginal effects. Any extension
   schedule, maximum duration and stopping rule must be predeclared; do not inspect
   held-out performance repeatedly or extend until a favorable result appears.

This checkpoint archives/reconciles methodology and adds six synthetic boundary
checks. No executable contract, evaluator, recorder, feature/model, numeric policy,
historical result or production behavior changes. The study remains unfrozen,
physical onset undefined, the feed gate inconclusive, and fitting/live use off.
