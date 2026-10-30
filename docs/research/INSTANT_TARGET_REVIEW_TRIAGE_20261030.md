# Instant target reviews: reproduced findings and v2 draft

Subsequent checkpoint: Claude's independent v2 review at `10b0f96` is complete.
Codex accepted its catalog/version guard fix through `92fb51d`; see the
[acceptance and outstanding study decisions](INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md).
316 targeted checks pass. The initial v2 reproduction/source records below
remain pinned to `8b5b266`, not the current evaluator hash. Both contract JSON
files are unchanged. Study freeze, Gemini v2 review and fitting remain gated.

Date: October 30, 2026. Scope: static source review plus deterministic
synthetic paths. **No real prospective outcomes, fitting or historical
discovery/validation were inspected or rerun.**

Both Gemini responses inspected the same five sources at `941f47a` and
explicitly did not run tests. Preserve them as external review evidence:
[response A](reviews/GEMINI_INSTANT_REVIEW_A_20261030.md),
[response B](reviews/GEMINI_INSTANT_REVIEW_B_20261030.md), and
[provenance manifest](reviews/GEMINI_INSTANT_REVIEWS_20261030_MANIFEST.json).
These overlapping responses are not two independent empirical studies.
Neither response inspected the original unamended proposal as a separate
source. They cannot establish complete original-proposal fidelity.

## Earlier response, before source access

The subsequently supplied [full preliminary response](reviews/GEMINI_PRE_SOURCE_CONCEPTUAL_REVIEW_20261030.md)
explicitly inspected **zero repository files** and ran no tests. The review
history is one conceptual response followed by two overlapping source-based
responses, not three independent confirmations. This additional review is
also not the original unamended proposal being evaluated.

Its main useful cautions are already represented in the v2 draft: separate
forecast outcomes from activity triggers, include forward-only movers,
name the timing reference, retain unknown data, and respect dependence.
Its broad assertion that the implementation only graded post-trigger
continuation was superseded by the later source inspection, which confirmed
that independent forward labels and pre-trigger timing already existed.

Additional suggestions are recorded without changing the current draft:

| Preliminary suggestion | Disposition |
|---|---|
| Find a physical origin by scanning back to an extremum/compression boundary | Still an open label-design question. A fixed search interval, tie/boundary rules and maturity must be specified before outcomes are inspected. A favorable retrospective extremum is not automatically an objectively identified physical start. V2's `anchor-30s` reference remains an explicit proxy, not physical onset. |
| Replace no-retrace with a volatility-scaled adverse bound or TWAP retention | Candidate alternatives, not verified fixes. Adverse excursion is already retained; the strict no-retrace subset does not gate the v2 primary target. The claimed routine 30-50% retracement frequency is not established by any supplied data. No tolerance or new retention target is selected here. |
| Use matched quiet controls, lead lags and residualized features | Possible diagnostics to preregister. Matching must use causal covariates and preserve sampling/exposure information. Moving 15/30/60s before a selected trigger does not by itself prove physical anticipation or eliminate selection effects. Residualization is optional, discovery-fitted and cannot establish a physical mechanism on its own. |
| Use two-way cluster-robust inference | An alternative inference design, not an automatic correction to the existing paired UTC-day block plan. The number of independent clusters/regimes and small-sample limits still matter. Do not switch methods after seeing which interval is favorable. |
| Use overlapping 30s/180s acceleration, 180s compression or a cross-sectional market benchmark | These differ from the corrected proposal's non-overlapping 30s/prior-150s acceleration, active prior-candle compression context and declared BTC-beta residual. Exact feature formulas remain gated; this conceptual response does not silently replace them. |

There are no new measurements or reproduced implementation failures in the
pre-source response. V2 code, target thresholds and its pending-review status
are unchanged by archiving it.

## Findings and decisions

| Review claim | Verified assessment | Action |
|---|---|---|
| Trigger-relative consumed fraction omits the run-up | Reproduced. In the existing synthetic path, the prior leg is 0.002 log units and total displacement from `anchor-30s` is 0.022. V1 reports 0 at the trigger; that earlier reference gives 0.002/0.022 = 9.09%. V1's arithmetic matches its declared origin, but the unqualified name can mislead a whole-move interpretation. | V2 names and reports both references. It does not claim that the earlier window boundary is the physical origin. |
| Strict onset catalog omits forward-only moves | Reproduced. A signed 1 bp dip after the trigger can leave `verified_forward=True` and `verified_onset=False`; v1's onset catalog has zero entries. This is correct for that catalog's stated strict-subset purpose, but insufficient for a broad event denominator. No incorrect production missed-move rates have been demonstrated because that protocol is not implemented. | Add a separate forward-window catalog and timing API. Operational missed-move/false-alert rates remain disabled until event association and exposure rules are frozen. |
| Zero-tolerance no-retrace is a code defect | It is an explicitly documented v1 pilot choice, not a formula/implementation discrepancy. A small adverse dip rejects the strict subset; how often that happens in real markets is unmeasured here. Claims of massive attrition or routine sweep behavior are hypotheses. | Keep the rule as a secondary diagnostic. It does not gate v2's primary pointwise target. No arbitrary tolerance is selected from outcomes. |
| Post-trigger breakout requires additional movement | Correct by construction and already documented. Whether it is useful depends on the stated confirmation question. It does not establish that an earlier physical start is known. | Retain the diagnostic definition; keep it separate from the primary forward target and from whole-move claims. |
| LF hashing is broken | Rejected. `Path.read_text` already normalizes newlines; the existing CRLF/LF test passes. Response A itself acknowledges that behavior. Adding another replacement is not a correctness fix. | No hash-formula change. |
| Alert timing can divide by zero on a forged label | Defensive API concern. Generated verified labels require a positive favorable peak, so this does not demonstrate a failing valid evaluation path. | V2 rejects nonpositive/nonfinite external peak values before division. |
| Pace baseline may overlap the active window | The current metadata check already requires `pace_end_ts_ms == anchor-30s`. The missing upstream builder must actually construct 120 prior non-overlapping windows ending there. | Preserve the check and keep builder provenance in the recorder gate. |
| Onset definition makes F1/F2/F5 successful algebraically | Gate contamination is a real evaluation risk, but several claimed equivalences are too strong. A 5s-step crossing does not force positive 30s-versus-prior-150s F1 acceleration. Count-pace OR volume-pace exceeding 2 does not force volume pace to exceed 2. Unsigned activity does not determine signed taker imbalance. Exact F1/F5 formulas are not yet frozen. | Use the independent forward label as the declared primary pointwise target, compare gate-conditioned continuation against the gate inputs, and test incremental value. Do not call all circularity eliminated. |

The [synthetic reproduction record](results/instant_target_review_20261030/REPRODUCTIONS.json)
and [v2 tests](../../tests/test_instant_targets_v2.py) reproduce these cases.
One counterexample has a verified velocity/activity onset but current 30s
return 0.002 versus prior-150s return per 30s of 0.0024: the corresponding
rate acceleration is **negative**, contrary to the algebraic guarantee.

## Claude's baseline contribution

Reviewed Claude commit `d711832774caed64063b6281d8acad6aae5a8791` on
`claude/instant-radar-review` without editing its worktree. It moves the
baseline cutoff before both velocity windows, whose earliest endpoint is
`anchor-35s`. At a minute-aligned anchor, v1's last completed 1m return can
include the ramp being normalized.

This is a useful baseline-policy refinement, **not proof of future-data
leakage**: v1's baseline is still available by the anchor. Because it changes
the measurement definition, it is adopted only in the opt-in v2 draft:

```text
sigma_baseline_end_ms = floor((anchor_ms - 30_000 - 5_000) / 60_000) * 60_000
```

V1 JSON, default baseline rule and valid-label outputs stay reproducible.
The v2 metadata check enforces this cutoff; the upstream baseline builder
still needs implementation/provenance checks. The full independent review
signoff is not inferred merely from the existence of Claude's fix commit.

## Opt-in v2 draft

The [v2 draft contract](INSTANT_TARGET_CONTRACT_V2_DRAFT.json) is explicitly
unapproved for fitting and is **not the default evaluator**. Use it by name:

```python
engine = TargetEvaluator(samples, contract_path=V2_CONTRACT_PATH)
label = engine.evaluate(anchor, baseline, "up", 300, asof_ts_ms)
windows = forward_event_catalog([label])
timing = engine.forward_alert_timing(windows[0], actual_publish_ts_ms)
```

All existing 30s/180s inputs, 5m/15m horizons, quote/coverage checks, signed
magnitude/retention requirements, trade quanta and cost scenarios remain.
V2 adds these explicit boundaries:

- **Primary pointwise label:** `verified_forward`, evaluated on all eligible
  grid observations, including no-move and non-board rows. It does not require
  an activity trigger, breakout deadline or no-retrace diagnostic.
- **Secondary strict-trigger subset:** `verified_onset` remains available for
  attrition and conditional continuation analysis. `event_catalog()` remains
  that secondary catalog; `forward_event_catalog()` is separate.
- **Forward windows are not physical impulses:** earliest qualifying-window
  selection can predate the physical start and overlapping horizons remain
  dependent. Forward-window timing uses labels such as
  `before_forward_window_anchor`, not `pre_onset_prediction`.
- **Named references:** `post_anchor_consumed_fraction` uses the forecast/
  trigger anchor; `pre_window_consumed_fraction` uses `anchor-30s` and the
  maximum favorable residual over the entire `[anchor-30s,anchor+H]` path,
  including any earlier wick. Missing history or no positive reference peak
  gives a null pre-window metric without erasing the complete forward label.
  There is no unqualified `consumed_fraction` field in v2 timing results.
- **Trigger-relative timing:** v2's strict-trigger API reports
  `before_activity_trigger`, `early_after_activity_trigger` or
  `late_after_activity_trigger`; its half-consumed comparison uses the named
  pre-window reference. None claims a physical first tick.
- **Provenance:** v2 labels carry both the normalized contract SHA-256 and
  evaluator-source SHA-256. Catalogs reject mixed contract/implementation
  cohorts. The pinned v1 source export is unchanged.

The forward label still uses entry spread, sigma and beta. Features can share
those controls; changing the target does not guarantee statistical independence
or eliminate all selection effects. Report coverage and stratify/control
the relevant spread/liquidity/beta regimes.

## What F1-F5 would need to demonstrate

Gemini supplied plausible hypotheses and ablations, not measured effects.
The following is the working research checklist, not a newly fitted formula:

| Mechanism | Evidence sought beyond its comparator | Evidence against / uncertainty |
|---|---|---|
| F1 acceleration | Useful incremental prediction beyond current velocity and F5, comparing 30s with the prior 150s at the same rate scale; assess genuine pre-trigger observations separately. | Robust reversed/negative incremental effect argues against the declared version. A wide interval around zero is inconclusive. |
| F2 signed participation | Signed match-derived imbalance adds value beyond unsigned pace/count, with verified sides, deduplication and coverage. | Unsigned activity alone explaining the result does not support the signed-flow hypothesis. Unknown coverage or inadequate independent episodes stays inconclusive. |
| F3 sampled BBO | Size-pressure information adds value beyond spread alone and F2, using observation-age-aware time weighting. | Spread-driven target feasibility alone does not establish directional book information. Sampled BBO cannot establish full-depth mechanisms. |
| F4 compression/expansion | Active prior compression adds useful context beyond baseline sigma and acceleration, with already-available traded candles. | Dead-book/outage artifacts do not support compression. Too few valid regimes cannot reject it confidently. |
| F5 market relative | Useful value beyond raw coin movement, with beta-fallback cohorts and BTC-regime controls; retain absolute coin cost outcomes too. | Pure residual-target alignment is not sufficient for an executable-return claim. Quiet BTC or wide uncertainty leaves marginal value unresolved. |

Use discovery-only scaling/choices, prespecified meaningful-effect criteria,
fixed false-alert burden or matched coverage, limited ablations and fresh
validation with paired day/episode-aware uncertainty. A confidence interval
containing zero does not prove zero value. Correlated F1/F5 predictors need
incremental-value checks, not an invented requirement of exact orthogonality.
Log-loss requires declared probability predictions; an ordinal 0-100 score
does not by itself supply them. Seven validation days may be insufficient.

Next: independently review this draft, freeze event association/exposure,
exact F1-F5 formulas, stages/readiness and the recorder contract, and resolve
the existing feed gate before study collection/fitting. The all-product audit
gate remains false. No live rank, UI, worker or production service changed.

Verification: all **130** targeted v1/v2/audit/campaign/contract/driver/restore/WS
tests passed, along with Black 24.8.0, repository guardrails, documentation
links and diff checks. All 11 frozen historical artifact hashes and all five
source sections in the pinned Gemini export are unchanged. The reproduction
record's evaluator hash matches the tested source. Native Mac/cloud execution
and independent review of the v2 draft remain pending.
