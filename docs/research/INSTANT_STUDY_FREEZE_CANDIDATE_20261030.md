# Instant study rules: consolidated freeze candidate — 2026-10-30

Subsequent implementation: the additive reporting schema and offline sparse
replay/baseline prototype were implemented at `8211262` and independently
reviewed/accepted through `ab95159`; read the
[implementation checkpoint](INSTANT_OFFLINE_PIPELINE_20261030.md).
This does not freeze these study rules or change the target evaluator at
`92fb51d`. The "next implementation" descriptions below retain their draft
history; the independent offline review is complete and real-data verification is next.

**Status: draft for review, not frozen, not permission to fit or deploy.**
Executable labels remain at `92fb51d`; V1 stays the default. Neither executable
contract nor the evaluator changes in this checkpoint. This document combines
[Claude's review](reviews/CLAUDE_INSTANT_V2_REVIEW_20261030.md),
[Codex's acceptance](INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md) and the newly
received [Gemini v2 design review](reviews/GEMINI_V2_DESIGN_REVIEW_20261030.md).
External recommendations are evidence to assess, not user authorization.

Gemini reports inspecting the eight-section `cc3b6a6` packet for `8b5b266` plus
the acceptance report. Its eight stated source hashes match the pinned bytes.
That does not establish that Gemini ran tests or inspected the full patched
`92fb51d` source. The original unamended proposal is still unavailable. Its
claim that every eligible grid row receives a label describes the intended
universe, not a deployed recorder or a measured coverage result.

## 1. Target and reference decisions

Keep `verified_forward` as the primary pointwise outcome, separately at 300s
and 900s, across the causally eligible universe including non-board/no-move
rows. The strict activity/no-retrace target remains a secondary diagnostic.
Neither a forward-window anchor nor anchor minus 30s identifies physical onset.

| Decision | Draft disposition |
|---|---|
| S1: earlier wick | Retain the existing whole-reference-window peak and strict timing semantics. Gemini's narrower search is a different metric, not a fix to a contract violation. Preserve the previous wick; do not overwrite `pre_window_peak_*` with a post-anchor search. |
| Additional continuation diagnostic | A future additive field may report `pre_window_to_forward_peak_consumed_fraction`, using anchor minus 30s as price reference and the maximum over `[anchor,anchor+H]` as denominator. Give it its own name, peak timestamp and null reason. Report both peak references and whether the whole-window peak predates the anchor. This is not physical-move consumption, a competing fitted target, or a reason to choose whichever result looks better. |
| S2: baseline cutoffs | Retain sigma ending at `floor((anchor-35000)/60000)*60000` and pace ending at `anchor-30000`. Both are causal. The completed-minute volatility sample and nonoverlapping activity baseline estimate different quantities. Verify the actual baseline builder, not just supplied metadata. |
| S3: missing fraction reason | Recommend an additive `pre_window_consumed_fraction_reason` field: source reason when reference quality fails (with an explicit fallback reason), `invalid_pre_window_peak` for a missing/nonfinite peak, `nonpositive_pre_window_peak` for a finite peak <=0, and null for a populated fraction. Preserve unavailable outcomes as null. The reporting contract/implementation still need this amendment and tests before freeze. |

Why retain S1? On the reproduced path the earlier wick is 0.04 log units, the
trigger is 0.002 and the later peak is 0.022 from the pre-window reference.
The existing fraction is 5%; Gemini's alternative is 9.09%. Both are valid
answers to differently named questions. The existing strict result is late
because the whole-window peak has passed, not because the fraction exceeds
50%. Report the separate conditions; do not turn this strict diagnostic into
a claim that most of a physical move has elapsed. The primary forward label
does not require that strict timing classification.

Do not clamp negative or greater-than-one fractions to `[0,1]`; those values
can describe a reversal or an observation outside the denominator's interval.
Any changed semantics require a separately versioned contract before fitting.

## 2. Alert success and event coverage answer different questions

For an actual publication at `t`, retain its recorded 5s decision cutoff `b`,
publication delay, input availability and quote age. Evaluate the primary
pointwise `verified_forward(b,H)` on its declared fixed horizon. This is a
decision-cutoff outcome, not a fill at a price from before publication. Keep
illustrative spread/fee outcomes distinct from execution claims.

For complete mature labels:

```text
pointwise_success_H = verified_forward(b,H) is True
pointwise_failure_H = verified_forward(b,H) is False
ungradable_H = pending or unavailable
```

Do not erase a pointwise failure because another catalog window is associated
with the alert. Keep ungradable counts and coverage visible, outside both
success and failure counts. Evaluate the two horizons in separate tables.

Gemini's proposed false-alert rule is not interchangeable with this rule:

| Synthetic alert | Its own target | Gemini's broad association rule |
|---|---|---|
| 5m alert; move begins at +340s | False: move starts after +300s | Forgiven by a qualifying catalog window anchored at +65s |
| 15m alert; move begins at +940s | False: move starts after +900s | Also forgiven by a window anchored at +65s |
| 5m alert at an earlier move's endpoint | False for the next 5m | Forgiven by the old window's inclusive association endpoint |

These are not demonstrations of live-feature leakage. They demonstrate a
different success deadline and association meaning. A broad retrospective
association may be reported as coverage; it must not replace a failed
fixed-horizon prediction or be advertised as physical early-warning success.

Proposed separate **forward-window coverage diagnostic**, pending an
implementation/matching review: group by product, direction and horizon;
sort windows by anchor and alerts by publication; assign the earliest unused
qualifying alert to each window in chronological order, allowing an edge only
in `[anchor-180s, forward_peak]`. One alert covers at most one window per
horizon; an identical timestamp is ordered by the retained publication ID.
An alert can have separate associations in 5m and 15m tables. Retain unmatched
alerts/windows. This rule is a transparent candidate, not implemented or a
physical-event matching protocol.

Call its missing coverage `uncovered_forward_window_rate`, not physical
`missed_move_rate`. Keep operational missed-move/false-alert rates disabled
until the entire association/exposure contract is approved and executable.

Exposure rules for the eventual protocol must include mature trailing horizons,
warmup, verified health, feed/universe membership and candidate eligibility.
Report healthy board wall-clock hours, eligible-product hours, universe sizes
and ungradable alerts; a shrinking universe must remain visible. Compare all
rankers on identical complete-data rows as well as their natural coverage.

## 3. Five-feature candidate, fixed before outcome inspection

These are proposed formulas, not implemented features or empirically selected
weights. Keep the fixed 30s/180s windows; do not optimize a window grid on the
discovery sample. For direction `d=+1/-1`, use causal midpoint log returns,
the declared sigma floor, verified match sides and receipt-time windows.
The following makes one concrete candidate available for implementation
review; changing it later must be recorded before any discovery outcomes.

| Feature | Proposed single fitted input | Required comparison |
|---|---|---|
| F1 acceleration | `d * (r_coin_30s - r_coin_prior150s/5) / sigma_1m` using adjacent nonoverlapping endpoint returns | Current velocity and market-relative movement; verify incremental value beyond their levels |
| F2 signed participation | `d * ((buy_usd-sell_usd)/(buy_usd+sell_usd)) * log1p(volume_pace)`; volume pace is current 30s match USD divided by the median of 120 completed, nonoverlapping 30s windows ending at `b-30s` | Unsigned pace/count and the full model without F2 |
| F3 sampled book pressure | `d/30s * integral((bid_size-ask_size)/(bid_size+ask_size), b-30s..b)` over last-observed BBO state | Spread-only control plus F2; spread stays separately recorded rather than hidden in a second F3 predictor |
| F4 active compression/expansion | `compression * max(d*r_coin_30s/sigma_1m,0)`, where `compression=1/(1+log(max(high)/min(low))/(sigma_1m*sqrt(15)))` over traded closed candles in the prior 15 completed minutes | Sigma/F1 and the same candidate without F4 |
| F5 market relative | `d * (r_coin_180s - beta*r_BTC_180s) / sigma_1m`, with synchronized endpoints and beta already available at the decision cutoff | Raw coin movement, beta-fallback/BTC-regime strata and coin returns under stated cost scenarios |

For F2, require >=5 unique matches and positive measured baselines/denominators;
do not insert epsilon/neutral scores to manufacture availability. The feature
uses volume pace; the secondary activity trigger's count-or-volume maximum
remains a different quantity. Record every excluded grid row and its reason.
Raw match windows are `[b-30s,b)`, and the 120 baseline windows end at `b-30s`.

For F3, use receipt-ordered observation times and require valid, <=10s-old
quotes throughout the 30s integration interval. An unchanged carried quote
keeps its original age. A stale/unknown duration makes the primary feature
unavailable; do not remove that duration and renormalize the rest to 30s.
This is sampled L1 information, not a continuous full-book measurement.

For F4, require >=10 traded, closed, already-available candles in the prior
15 minutes and verified health for any confirmed empty interval. Never invent
OHLC for an absent/unverified candle. No compression claim follows from an
outage. The explicit directional expansion interaction keeps this one input
from rewarding quietness alone on both boards.

Unnormalized decayed sums at fixed 30s/180s half-lives remain separately logged
diagnostics under the corrected math. This candidate chooses boxcar endpoint
F1/F5 as fitted inputs; do not add both decay states as extra fitted weights,
or select a smoother variant using validation. That choice is declared here
as a new draft recommendation, not something Gemini has already endorsed.
For those incremental decay diagnostics, beta must be known before each
increment; do not rebuild past states with a newly estimated beta. In contrast,
the proposed endpoint F5 is computed at its own cutoff with an already-known
beta. Keep that distinction and target-shared scale/beta controls visible.

Support means prespecified meaningful incremental value beyond the comparator,
with matched coverage/false-alert burden, ablations and paired uncertainty.
Robust harm argues against the declared mechanism. A point estimate near zero
or interval spanning zero is inconclusive unless the interval also rules out
the separately prespecified meaningful benefit. Probability metrics require
a declared probability model; this candidate currently supplies ordinal ranks.

## 4. Gates and next implementation step

The fit remains a separately fitted instant model for each direction, sharing
raw market data with the broader outlook, not its formula/weights. No numeric
weights, readiness minima or stage boundaries are invented by this document.
The existing hard extension gate stays; remaining stage rules, regularization,
scaling and meaningful-effect/power criteria must be fixed before fitting.

The feed gate remains false. Gemini's suggestion to restrict to passing
products is a possible future amended universe, not a pass of the current
all-product gate. Any bounded supplemental diagnostic must be predeclared;
do not repeat completed samples until a favorable verdict appears. Preserve
all failures and the original thin-product verdict.

Next concrete implementation work: the additive diagnostic/schema amendment,
then a standalone offline 5s recorder/replay and causal baseline-builder
contract with healthy-zero versus outage, receipt boundaries, deduplication,
quote ages, late recovery, 60 closed returns and 120 pace-window tests. Do not
attach it to the always-on collector or change live rankings during this step.
This checkpoint does not implement that recorder or launch another capture.

After the data gates pass, collect at least 14 valid shadow days, with fixed
discovery/validation split, 60m phase purge and all labels matured. Freeze the
code/model/universe before fresh validation once. Use paired UTC-day blocks
retaining all products/rankers together; report independent episode/regime
coverage and the fragility of seven validation days. Insufficient readiness
requires predeclared additional collection, not relaxed minima or reused
validation. Physical-move recall remains unavailable until its own event
definition is specified.

## Reproduction and scope

Run `python scripts/scoring_experiment/reproduce_instant_study_choices.py`.
The [saved synthetic evidence](results/instant_study_choices_20261030/REPRODUCTIONS.json)
records the current evaluator hash, wick/reference alternatives, two delayed
move cases, the completed-move case and the missing diagnostic. All are
fabricated paths for checking definitions, not market performance.
The [Gemini archive manifest](reviews/GEMINI_V2_DESIGN_REVIEW_20261030_MANIFEST.json)
records source availability and normalization. The recorded 316 implementation
checks remain from `92fb51d`; this document does not claim a fresh full-suite
pass. Historical experiments, executable targets, source packets, production
and other agents' worktrees are unchanged.

Current [draft verification](results/instant_study_choices_20261030/CHECKS.json):
identical synthetic replay, all eight packet sections/archive hashes, all 11
historical hashes, unchanged evaluator/contract bytes, Black 24.8.0, repository
guardrails, JSON, local links and diff checks pass. These checks validate the
documented examples and checkpoint integrity, not the candidate's predictive
value or power.
