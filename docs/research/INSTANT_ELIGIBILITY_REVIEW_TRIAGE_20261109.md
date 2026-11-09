# Gemini eligibility review: dispositions after the batched source pilot

November 9, 2026 (Pacific). The [Gemini response](reviews/GEMINI_ELIGIBILITY_REVIEW_20261109.md)
is reconciled against the 15-source packet at `17b87ac` and the real-source
attempt at implementation `c9d79be`. All 15 listed paths, lengths and
shortened digests match the packet manifest. Gemini reports reading all
sections and running no tests or independent digest calculations. Some pasted
table cells end mid-sentence. The [archive manifest](reviews/GEMINI_ELIGIBILITY_REVIEW_20261109_MANIFEST.json)
identifies the received bytes and the preserved text.

## Adopt as design directions

- Keep the declared product × cutoff × direction inventory and report every
  planned slot, including ALCX and AURORA. Enforce that completeness against
  the independently declared plan in the producer. The existing directional
  reporter can reject a one-sided omission but cannot detect a product/cutoff
  omitted from both boards.
- Use all five ready features and both ready baseline components for a
  complete-vector candidate. Keep each feature's status and missingness reason.
  Verified empty windows and a ready zero are distinct from unavailable
  evidence. A ready pace baseline can have a zero median and still make F2
  unavailable. Continue using the calculated median: 60 positive-volume bins
  and 60 proved zero bins already yield a positive median. Preserve beta
  fallback as a separate flag. Keep the existing formulas for the next
  engineering check.
- Permit feature-specific coverage diagnostics with declared inputs and
  controls. Report the natural coverage of each diagnostic and the
  intersection for matched comparisons. Keep a single ranker's readiness
  separate from shared market evidence, eventual outcome gradability and
  actual delivery. The current delayed grader requires all five features;
  a ready partial vector does not yet have a grade or an evaluated ranker.
- Give a versioned delayed eligibility adapter separate fields for content
  cutoff, evidence as-of, feature completion, preparation completion, local
  commit and consumer observation. Keep cutoff `b` on the 5s grid. Both the
  book lookup and indexed lookup select market receipts strictly before
  (b); a later proof or payload completion may verify earlier receipts
  without extending the window. Preserve the existing reporter's
  `available_ts_ms <= ts_ms` rule and the original decision record.
- Preserve the difference between an input that missed its evidence as-of,
  a prepared decision that missed its delivery deadline, and evidence that
  contradicts an already observed decision during later grading. Keep all
  three in the accounting. For a published decision, a later contradiction
  can make the outcome ungradable without rewriting the decision or shrinking
  exposure. Keep per-board time unions and own-direction 300s/900s grades
  separate from planned-slot coverage and product-hours.

## Corrections and evidence limits

**BTC is the reference in the current delayed V2 outcome.** The timed
baseline estimates BTC beta against BTC as 1, including the flat-benchmark
fallback. Its F5 value and signed forward residual then cancel by construction.
The V2 minimum terminal move is positive. A synthetic rising BTC price path
confirmed a zero residual and no positive V2 grade in both directions at both
horizons, with and without the beta fallback flag. Treat BTC as a benchmark and
engineering control in the proposed study roster, keeping its rows in the
readiness report. A study of BTC moves would need a separate target definition.
SOL was the only non-benchmark product with all five features ready across
the sampled cohorts. One eligible non-benchmark product at a cutoff cannot
provide a cross-sectional comparison. Declare a wider non-benchmark candidate
universe through an outcome-blind coverage rule before prospective selection.

**The timing alternatives are proposals.** In the 532 sampled 30s trade
windows, zero were verified at cutoff and all were verified in the +5s view.
The largest recorded ready-proof delay in that later view was **1,003ms**.
For the 40 complete BTC/SOL rows, all recorded feature availability times
were at most **897ms** after cutoff. These are observations made from the
saved +5s view. They do not establish readiness at +1.5s for the whole cohort
or show what would have been delivered by +2.5s. The run actually used a
fixed +5s evidence offset. Across all 80 rows, the last local commit was
at +5,662ms and the last separate consumer read at +5,678ms. A +6s bound
contains those measurements in this run. It is neither a tested deadline
policy nor a measure of public delivery.

**Counts describe readiness and measurement.** Of the 20 rows per product,
BTC and SOL each had 20 complete feature vectors. ALCX had 12 ready F3
observations and no complete vectors. ALCX's F5 reason was
`stale_book_observation` on six rows, including both directions at cutoff
`1794140150000`, and `volatility_baseline_unavailable` on 14. The feature
reason by itself does not identify which quote endpoint was stale or whether
a separate cutoff spread control was ready. AURORA had 20 ready rows each
for F1, F3 and F5, with F2 blocked by the pace median and F4 blocked by the
traded-candle minimum. No one scored or graded these rows in the pilot.
The ten 5s diagnostic cohorts start at `1794140120000`; the
`1794140130000` in the coverage summary is the first eligible **30s
probe grid** point. Both use the same acknowledgment-based warmup boundary.

**Keep feed certification separate.** The paired side counts and sampled
receipt-ID proofs are valuable evidence for the run. The original gate
also requires REST reconciliation, adequate representation of each maker
side and its other declared checks. Gemini's 100-pair proposal, the 25%
product duty cycle and the proposed tail/coverage percentages stay open.
Record actual overflow events and incomplete attempts, rather than
inferring overflow from a sampled queue watermark. The before/after
host-clock offsets do not establish a rate that can be extrapolated to
another session.

## Next engineering check

1. Implement the research-only delayed eligibility adapter with complete
   inventory accounting, separate readiness and deadline fields, and a
   regression check that late evidence or a later grade cannot rewrite the
   frozen decision. Preserve the existing target, feed gate and reporter
   contracts. Distinguish the BTC benchmark role from the proposed
   non-benchmark ranker cohort.
2. First compare fixed evidence prefixes at +0, +1.5, +2.5 and +5 seconds
   on the preserved journal without grading outcomes. Report readiness
   and its failure reasons at each as-of. A replay can test visibility
   and reproducibility; it cannot establish live scheduling or delivery
   at an earlier offset.
3. Use that comparison to predeclare a bounded, outcome-blind capture
   across distinct activity periods. Declare the non-benchmark candidate
   set, a warmup and attempt-stop/retry rule, the tested timing schedules
   and the required scope of side/coverage evidence in advance. Observe
   local commit and consumer delay directly. Keep partial sessions and
   missing slots in the report. A small number of adjacent cohorts can
   find blockers; it cannot certify a p99.9 latency tail or 99.5% uptime.
   A longer run would need a separately verified storage/rotation plan.
4. Resolve full feed certification, publication age and prospective
   sample design separately before authorizing outcome collection. Freeze
   model, comparison, burden, sample, purge and stopping rules before
   fitting and fresh validation. The existing outcome and historical
   validation locks still apply.

The [pilot result](INSTANT_BATCHED_SOURCE_PILOT_RESULTS_20261108.md) and
[attempt report](results/instant_batched_source_pilot_20261108/ATTEMPT_01.json)
supply the measurements above. This reconciliation is a documentation
checkpoint. The numeric policy, study and publication age limit are open.
