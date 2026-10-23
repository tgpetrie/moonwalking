# BHABIT per-coin scoring: research brief

Research only. No code was changed. Written 2026-10-23 on branch
`claude/scoring-research` (docs only, based on `claude/retention-hotfix`, which is
production's release `6235e2d2` plus the storage-retention fix).

**What was inspected:** `backend/live_ranking.py`, `alert_events.py`,
`signal_context.py`, `position_levels.py`, `sell_side_intelligence.py`,
`derivatives_positioning.py`, `coin_intel_external.py`, `position_intel.py`,
`sentiment_api.py`, and the December 2025 enhanced aggregator at commit
`cd2ada48` (`backend/sentiment_aggregator_enhanced.py`). **Not inspected:** the
frontend, and newer branches (the consolidation into `Moonwalking-Unified` may
differ from what is described here). **Not verified:** vendor pricing and limits
(that is the data-source brief), and any claim marked *unverified*.

---

## 0. Summary

1. **BHABIT already has a real numeric per-coin score** (`live_score`, 1-99, model
   `live-strength-v1`), but its own docstring says it is "deliberately descriptive
   rather than predictive". It is a weighted blend of 1-minute, 3-minute and
   1-hour price moves, one-hour volume change, a confirmation score and a
   persistence score, minus a chase penalty, shrunk toward 50 when inputs are
   missing.
2. **Measured on your production history, that score carries no usable
   information about the next 24 hours.** Rank correlation (information
   coefficient, IC) between the direction-aligned score and the 24-hour ATR return
   is **-0.026** over 490,930 signals; the weekly mean IC is -0.001 and positive in
   only 2 of 9 weeks. Every component is within about +/-0.07 of zero (section 3).
3. **The separate alert "confidence" is an evidence count, not a probability.**
   Against matched same-coin controls it shows no incremental value, and
   high-confidence "up" signals are slightly worse (-0.07 to -0.09 R).
4. **The December 2025 aggregator is useful as a source of ideas, not as a
   baseline.** It mixes real inputs with generated ones, applies market-wide inputs
   (Fear & Greed, generic RSS headlines) to every coin, and uses unvalidated
   hand-set weights (section 2).
5. **Recommended starting approach:** a *calibrated cross-sectional rank score*
   per horizon, built from volatility-normalised, BTC-residual features, trained
   walk-forward, with **confidence reported separately from bullishness** and
   **kept in shadow mode until it passes pre-registered gates** (sections 4 and 8).
6. **Expect that it may find nothing.** The honest design includes kill criteria.
   If no feature set clears the gates, the score stays labelled "strength right
   now" (descriptive) and the product does not imply a forecast.
7. **Do not let cost basis or user preferences change the score.** They should
   change risk guidance and sizing context, not the market view (section 7).
8. The measurement infrastructure is the project's strongest asset: point-in-time
   feature snapshots, graded outcomes, a candle archive and a controls pipeline.
   Most of the evaluation plan can run on it now.

---

## 1. What BHABIT supports today, and the gaps

### 1.1 Capabilities (by layer)

| Layer | Where | What it does | Notes |
|---|---|---|---|
| Live strength score | `live_ranking.py` (`live-strength-v1`) | Weights: 1m move 0.20, 3m move 0.25, 1h move 0.15, 1h volume change 0.15, confirmation 0.15, persistence 0.10. Each move is mapped to 0-100 with a fixed full scale (1.25%, 3%, 6%; volume 200%). Chase penalty up to 7+7 for extended moves, +5 thin / +2 wide liquidity. Then `score = 50 + (raw-50) x reliability`, `reliability = max(0.35, data_quality/100)`. Labels: Leading >=80, Strong >=65, Building >=55, Mixed >=45, Weak >=35, Fading. | Descriptive by design. Deterministic and explainable. No forecast target. |
| Alert confidence | `alert_events._event_confidence` | State base points + severity (0-9) + independent families (up to 12) + modifiers (up to 6) + persistence (up to 6), capped at 99. Notifications at >=85 (>=80 for Reversal Risk), >=65 for held coins. | An evidence count. Not calibrated to any outcome. |
| "The Read" | `alert_events.derive_event_read` | Maps state, confidence, direction and families to labels such as CONTINUATION FAVORED (conf >=85 or >=78) and BREAKDOWN CONFIRMED (>=88). | Thresholds are hand-set. |
| Market context | `signal_context.py` | Move vs market median (robust z), vs BTC, spot buying/selling from trade imbalance (+/-0.35, >=5 trades, >=$10k), liquidity from spread (>=30 bps wide, >=80 thin). | Real and useful; coarse buckets. |
| Levels and risk | `position_levels.py`, `sell_side_intelligence.py` | 49 hourly candles, support/resistance, ATR(14), range position (zones at 15/40/60/85), a 0-10 top-risk score, stop-limit and target geometry. | Marked `outcome_validated: False`. |
| Derivatives context | `derivatives_positioning.py` | Hyperliquid funding and open interest, keyless. | OI history is in memory only (about 24h), so no durable history to test. |
| External intel | `coin_intel_external.py` | CoinPaprika events and Twitter, CoinGecko trending and community, LunarCrush (key needed), lexicon sentiment. | Slow and noisy; not in the score. |
| Sentiment service | `sentiment_api.py`, `sentiment_aggregator.py` | Market-wide sentiment surfaces. The truth audit (P1.1) removed fabricated fallbacks. | Market-wide, not per coin. |
| Portfolio layer | `position_intel.py`, `portfolio_mode.py` | Holdings, fills-based cost basis, allocation, open orders, posture from signal state, historical outcome stats. Read-only. Held coins get a lower notification bar (65 vs 85). | Personalisation is notification priority only. |
| Measurement | `signal_outcomes.py`, `board_outcomes.py`, `control_dry_run.py`, candle archive | 5/15/30/60-minute grading, feature snapshots stored at signal time, matched-peer feasibility instrument, 4h/12h/24h tracking (on `claude/demote-weak-reads`). | Enables look-ahead-safe evaluation. |

### 1.2 Meaningful gaps

1. **No forecast target.** The score ranks "who is moving", not "who will outperform".
2. **Horizon is minutes to one hour.** Nothing at 4 hours to 7 days, where decisions
   about holding and exit actually live.
3. **Fixed full-scale constants** (1.25%, 3%, 6%, 200%) are not volatility-adjusted. A 3%
   move means different things for BTC and a small cap.
4. **Collinear inputs with fixed hand weights** (1m, 3m and 1h moves and a streak).
5. **No relative volume.** Only 1-hour volume change, not volume against the coin's own baseline.
6. **`data_quality` counts presence, not freshness**, and there is no uncertainty estimate.
7. **No sentiment, news or fundamentals in the score**, only as context.
8. **Confidence is not calibrated**, and bullishness and confidence are not separated.
9. **No regime awareness**, although sections 3 and 8 show effects flip with the market.
10. **No cost awareness.** A signal's size is not compared with what it costs to trade it.
11. **Personalisation does not reach the score** (only notification priority).
12. **No durable history for derivatives** inputs.

---

## 2. The December 2025 aggregator: reuse and avoid

`EnhancedSentimentAggregator.get_coin_sentiment` (879 lines, commit `cd2ada48`):
weighted average of source scores (0-100), weight = tier weight (0.85 / 0.70 /
0.50 / 0.30) x per-source reliability, plus a tier-divergence alert and
Fear & Greed extremes.

| Aspect | What it did | Verdict |
|---|---|---|
| Source tiers and reliability | Hand-set weights, no calibration | **Idea worth keeping** as a *prior*, to be replaced by measured weights |
| Tier divergence (tier 1 vs tier 3) | Alert if the gap exceeds 12 points | **Keep the idea**: disagreement is a feature (section 5) |
| Fear & Greed | Market-wide, same value for every coin | **Reuse as regime context only**, never as a per-coin score |
| CoinGecko "overall" | 35% price change + 25% community + 20% "volume sentiment" + 10% developer + 10% public interest | **Avoid.** Price is inside "sentiment" (circular); "volume sentiment" is `volume/market cap x 100 + 50`, so it can never be below 50; community and developer scores barely change over time |
| RSS headlines | VADER compound over generic crypto feeds | **Avoid as a per-coin input.** The function takes no symbol, so the same headline score is applied to every coin |
| Reddit | VADER on titles matching the symbol in a few subreddits | **Keep as an attention measure** (mention counts vs baseline), not as polarity |
| Generated data | Random values seeded by an MD5 of the symbol for fallbacks, history, social history, trending topics, and hard-coded Telegram 0.5 | **Never reuse.** These are fabricated; the later truth audit removed them |
| Coverage | About 70 hard-coded CoinGecko IDs | Too narrow for a 400-coin universe |
| Missing data | Substituted fallbacks instead of abstaining | Replace with explicit abstention (section 5) |

**Conclusion:** none of its output is evidence about price behaviour. Its structure
(sources, tiers, divergence) maps cleanly onto the "freshness" and "disagreement"
requirements below.

---

## 3. What our own evidence says works

All numbers are from your production history. Costs are assumptions: 0.2% round trip
unless stated; Codex's pilot also uses 0.9%, which has **not** been verified against
your account's fees.

| Question | Result | Caveat |
|---|---|---|
| Does `live_score` predict the next 24h? | IC **-0.026** (up -0.060, down +0.009, within coin -0.027); weekly mean -0.001, sd 0.093, positive in 2/9 weeks | Measured only on coins that fired a signal; 490,930 signals; direction-aligned 24h ATR return |
| Which components? | 1m -0.020, 3m -0.024, 1h trend **-0.068**, volume +0.009, confirmation -0.016, persistence -0.032 | Slightly negative trend components suggest short-horizon reversal at 24h |
| Data quality | Rows with all 6 inputs: IC **-0.092**; rows with 3-5: +0.012 | Fully populated rows are the more extended moves |
| Do signals beat their own coin's comparable hours? | **No.** 117,787 matched signals over 13 weeks (2026-07-17 to 10-11): all signals -0.031 R, 95% CI [-0.052, -0.010] | Matched on coin, direction, volatility, BTC 4h trend, 1-7 days away |
| Is confidence informative? | **No.** "Up" at 72-95+: -0.07 to -0.09 R vs matched controls; "down" 95+: +0.069 R (z about 2) | 13 weeks only |
| Are the weak reads worse than chance? | **No.** Pooled demoted reads -0.009 R, CI [-0.039, +0.021] | An earlier "worse than random" result was an artefact of comparing against all coins |
| Sell-side thresholds | Volume gate: +0.021 ATR, day-clustered z +0.4 over a year; top-of-range effect flips with BTC's regime (falling -0.13, flat +0.27, rising +0.52); a rule frozen on the first half flipped sign in 2 of 3 regimes | 561,160 coin-hours, 370 days, hourly candles, today's 407 listed coins |
| Per-coin tuning | Rank correlation of a coin's effect between halves: -0.01 (confidence), +0.03/+0.05 (volume gate) | Per-coin tuning fits noise |

**Literature context** (verified titles; see References): one well-known
academic result concerns **cross-sectional, weekly** predictors, e.g. Liu, Tsyvinski and Wu
(2022) report that market, size and momentum factors capture cross-sectional
expected crypto returns, with momentum examined at one- to four-week horizons.
That is a different horizon and a different construct from a 1-minute to 1-hour
tape score. It is consistent with our finding that minute-scale features carry
no 24-hour information, and it argues for adding **weekly, cross-sectional,
vol-normalised** features, not for tuning the current ones.

---

## 4. Scoring approaches

**Principles for any approach:** (a) define what the score predicts, (b) one score per
horizon, (c) a number that is *not* a probability unless it has been calibrated,
(d) bullishness, confidence and risk are three separate outputs, (e) nothing is
imputed, (f) every weight and threshold is a hypothesis with an evidence rule.

### Approach A (recommended start): calibrated cross-sectional rank score

* **Target:** for horizon h in {4h, 24h, 7d}, the BTC-residual, volatility-scaled
  forward return, ranked within the tradable universe at time t.
* **Features:** volatility-normalised returns at several lookbacks; BTC-residual
  momentum; relative volume (vs the coin's own median); realised volatility
  regime; liquidity and spread; funding and OI changes (once history exists);
  optional attention shock (mentions vs own baseline).
* **Model:** regularised linear or logistic model, trained walk-forward. Few
  parameters, so it can be audited and fits small samples.
* **Output:** `Score_h` = percentile of predicted outperformance within the
  universe (0-100). Separate `Confidence_h` and `Risk_h` (section 5).
* **Strengths:** simple, testable, directly addresses "does it beat the cohort",
  small data requirement.
* **Weaknesses:** may find no signal; needs the cohort data (available in the
  candle archive); linear.

### Approach B: evidence-weighted checklist with shrinkage

Keep today's factors but express each as a log-likelihood ratio estimated from
history with empirical-Bayes shrinkage toward zero; combine and map the posterior
to 0-100. **Strengths:** closest to the current design, very transparent.
**Weaknesses:** assumes independence between factors (they are collinear);
posterior is only as good as the shrinkage.

### Approach C: regime-switched ensemble (boosted trees)

Per-regime weights or a tree ensemble using BTC trend and volatility regime as
features. **Strengths:** can capture the sign flips seen in section 3.
**Weaknesses:** highest overfitting risk; needs far more data; hardest to explain.
Only after A shows a stable signal.

**Recommendation:** run **A in shadow mode** as the main track; keep **B** as the
fallback if A finds only a sparse signal; defer **C**. Keep `live_score` as a clearly
labelled descriptive "strength now" until a forecast score earns promotion.

---

## 5. How the score accounts for the required factors

A numeric score stays: `Score_h in [0,100]`, the percentile of predicted
outperformance at horizon h. **Bullishness is Score; Confidence is a separate
reliability number; Risk is a third.**

| Factor | Treatment | Evidence that would justify it |
|---|---|---|
| **Timeframe** | One score per horizon (4h, 24h, 7d); never blended. Show trend alignment across horizons as information. Match the horizon to the decision (monitor and exit vs entry). | Per-horizon IC and calibration |
| **Momentum** | Multi-lookback, vol-normalised, BTC-residual. Sign is an empirical question per horizon: reversal at short, momentum at weekly horizons per the literature. | Out-of-sample IC by horizon |
| **Liquidity** | A **gate and a cost term**, not a score component: spread, quote volume, estimated round-trip cost. A coin whose expected move is below its cost is flagged "not worth trading". | Thin-liquidity board entries were the clear outlier in earlier tests (-0.25% vs matched controls at 15 minutes) |
| **Sentiment** | Not a level. Use (a) market-wide sentiment as regime context, (b) coin-level attention *shocks* vs own baseline, (c) contrarian extremes. Timestamp at ingestion, not publication. Keep only if it adds IC *after* controlling for price and volume. | Incremental IC and a placebo with shuffled timestamps |
| **Source freshness** | Weight decays with age (half-life per source); beyond a cut-off the source is dropped; staleness widens uncertainty. | Per-source decay fitted on history |
| **Disagreement** | Dispersion of standardised scores across independent families (price, volume, positioning, attention). It **lowers Confidence, not Score.** | Does high dispersion precede worse or noisier outcomes? |
| **Missing data** | Never impute. Score only from available feature groups, require a minimum coverage per group, otherwise output "insufficient data". Show which inputs are missing. | Coverage-conditional IC |

**Confidence_h (0-100)** = reliability of `Score_h`, built from: effective sample
size of similar historical situations, calibration error in that score bucket,
data completeness, freshness, and disagreement. **It is not P(up).** Example
output: `Score 71 | Confidence 38 (thin history, 2 of 5 families stale) | Risk elevated (thin liquidity)`.

**Risk_h** is separate: expected drawdown (ATR-based), liquidity and spread, regime,
distance to invalidation.

---

## 6. How decisions relate to the score

| Decision | Uses | Does not use | Guardrail |
|---|---|---|---|
| **Discovery** | `Score_h` rank, attention shock, liquidity gate, `Confidence_h` shown | Cost basis, user P&L | A screen, not a recommendation; label experimental |
| **Entry** | `Score_h` at the chosen horizon, `Risk_h`, stop and target geometry (ATR, room to resistance), expected net edge vs cost | Raw confidence alone | Informational until the score passes the gates; says "wait" when geometry or cost fails |
| **Holding** | Change in `Score_h` since entry (with hysteresis), `Risk_h`, regime change, liquidity deterioration | Entry price | Avoid flip-flopping: require persistence and a minimum change |
| **Exit** | Risk first: invalidation or stop breach, score deterioration with confirmation, concentration limit, target | "Top of range" as a sell warning (not supported by the data) | Show levels as descriptive until validated |

---

## 7. Portfolio exposure, cost basis and preferences

The score describes the **coin**. Position context changes **risk guidance and
sizing**, not the market view.

* **Exposure:** weight, concentration, correlation to the rest of the portfolio and
  to BTC beta, and dollars to stop (already in P2.6). A held coin gets higher
  attention when `Risk` rises, not when `Score` is high.
* **Cost basis:** show unrealised P&L and distance from basis, but do **not** let
  it adjust `Score` or `Confidence`. Anchoring on cost basis is a known
  behavioural trap, and a coin's outlook does not depend on what you paid.
  *(No tax advice.)*
* **User preferences:** horizon, risk tolerance, maximum position size and
  drawdown tolerance act as **filters and presentation settings** (which horizon
  score to feature, which alert thresholds, which risk bands), not as score inputs.
* **Notifications:** keep a lower bar for holdings, but trigger it on changes in
  `Risk` and on deteriorating `Score`, not on a fixed confidence number.
* **Framing:** informational. Nothing here is personalised financial advice.

---

## 8. Evaluation plan

**Labels.** Forward BTC-residual, volatility-scaled returns at 4h, 24h and 7d, plus
a triple-barrier (target / stop / time) variant. Costs as explicit scenarios
(0, 0.2, 0.5, 0.9, 1.2%), each labelled an assumption until verified.

**Point-in-time features only.** Use the stored `feature_snapshot_json` (captured
at signal time) and candle features computed from bars **strictly before** t.
Universe at time t, not today's listings (survivorship). Ingestion timestamps for
any external source (publication lags and revisions are look-ahead).

**Splits.** Purged, embargoed walk-forward and combinatorial purged
cross-validation to handle overlapping labels (López de Prado, 2018). At least 12
months spanning rising, flat and falling regimes. Thresholds chosen on validation
only; the test set is touched once per pre-registered model.

**Multiple testing.** Pre-register the list of features, horizons and thresholds.
Use a higher hurdle than t = 2: Harvey, Liu and Zhu (2016) propose about t = 3.0 as
a rough guide and argue it may still be too low; also report false-discovery
adjusted results.

**Controls (already built).** Matched same-coin controls, BTC-neutral returns,
placebo shuffles, day- and week-block uncertainty, negative controls (variables
that should not matter). A score is judged by **excess over matched controls**, not raw returns.

**Calibration.** Reliability diagrams, Brier score and expected calibration error;
Platt scaling when data is scarce (below roughly a few hundred to a thousand
cases) and isotonic regression with more data (Niculescu-Mizil and Caruana,
2005). Report resolution (does the score separate outcomes), not only calibration.

**Economic test.** Net of costs, with turnover, drawdown and bootstrapped
intervals. "Beats controls" and "profitable after realistic costs" are separate gates.

**Live observation.**
1. **Shadow mode** for at least 8-12 weeks: the model version is frozen and
   written next to every signal, but not displayed or used for alerts.
2. **Experimental display** with Confidence and uncertainty, labelled as such.
3. **Alert use** only after the gates are met.
Monitor rolling IC, calibration and data coverage; retire or retrain on drift.
Extend extended-outcome tracking to include 7 days.

**Proposed promotion gates (heuristic assumptions to be pre-registered, not
findings):** out-of-sample IC at least +0.03 after BTC-residualisation; positive in
at least about 65% of weeks; interval excludes zero across at least 12 weeks;
calibration slope roughly 0.8-1.2; positive excess over matched controls; and a
stated net-of-cost result under each cost scenario. **If no model clears these, the
score remains descriptive.**

---

## 9. Heuristic assumptions register

| Heuristic today | Where | Evidence that would justify it |
|---|---|---|
| Weights 0.20 / 0.25 / 0.15 / 0.15 / 0.15 / 0.10 | `live_ranking.py` | Out-of-sample regression or IC contribution per component (today: about zero) |
| Full scales 1.25% / 3% / 6% / 200% | `live_ranking.py` | Replace with volatility normalisation; compare IC |
| Confirmation +/-6 per alert (cap 18), spot +/-10, breaking-away +/-7 | `live_ranking.py` | Incremental IC of each |
| Chase penalty (1m >1.6%, 3m >4%), liquidity +5/+2 | `live_ranking.py` | Does extension predict reversal after controls? |
| Reliability floor 0.35 | `live_ranking.py` | Coverage-conditional performance |
| Label cut-offs 80 / 65 / 55 / 45 / 35 | `live_ranking.py` | Calibration by bucket |
| Confidence state base, severity points, families, cap 99 | `alert_events.py` | Calibration curve against outcomes |
| Notify at 85 (80 reversal), held 65 | `alert_events.py` | Not supported (confidence shows no edge) |
| Read thresholds 78 / 85 / 88 | `alert_events.py` | Same |
| 49 candles, zones at 15 / 85, volume 1.5x, ATR buffer 0.2 | `position_levels.py`, `sell_side_intelligence.py` | Sensitivity across windows; a year of data shows no stable effect for the volume gate or the top zone |
| Cost 0.2% | outcome stores | Verify against actual fee tier; run 0.2-1.2% scenarios |

---

## 10. Suggested sequence

1. **Define the target and the feature set** (this document, plus the data-source
   brief). Pre-register hypotheses and gates.
2. **Build a point-in-time feature table** from the candle archive (cohort-wide) and
   the stored snapshots, with universe-at-time-t handling.
3. **Run Approach A offline** on a purged walk-forward; report IC, controls and
   calibration under each cost scenario.
4. **If gates pass:** shadow mode, then experimental display, then alert use.
   **If not:** keep `live_score` labelled descriptive and say so in the product.
5. Add derivatives history capture now (it is the one input that cannot be backfilled).

**Not recommended:** tuning the existing thresholds, per-coin weights, adding
more sentiment sources before testing incremental value, or blending horizons
into one number.

---

## 11. Uncertainties

* Results come from 13 weeks of signals (2026-07-17 to 2026-10-11) and a
  1-year candle archive of today's 407 listed coins; survivorship applies.
* Hourly candles cannot show intra-hour order; live order-book and spot-flow
  inputs cannot be replayed.
* I did not verify vendor pricing, limits or coverage (the data-source brief
  covers that) and did not inspect the frontend or the unified branch.
* The 0.9% round-trip cost is an assumption; actual fees depend on the account's
  tier.
* The literature points cited are limited to the four sources below. They are
  methodological or concern weekly cross-sectional effects, and none validates a
  specific BHABIT threshold.

## References (verified 2026-10-23)

* Liu, Y., Tsyvinski, A., and Wu, X. (2022). *Common Risk Factors in
  Cryptocurrency.* Journal of Finance 77(2), 1133-1177.
  https://onlinelibrary.wiley.com/doi/10.1111/jofi.13119 (working paper:
  https://www.nber.org/papers/w25882).
* Harvey, C. R., Liu, Y., and Zhu, H. (2016). *... and the Cross-Section of
  Expected Returns.* Review of Financial Studies 29(1), 5-68.
  https://academic.oup.com/rfs/article/29/1/5/1843824
* Niculescu-Mizil, A., and Caruana, R. (2005). *Predicting Good Probabilities With
  Supervised Learning.* ICML. https://dl.acm.org/doi/10.1145/1102351.1102430
* López de Prado, M. (2018). *Advances in Financial Machine Learning.* Wiley
  (ch. 7 cross-validation in finance incl. embargo; ch. 12 combinatorial purged
  cross-validation).
  https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086

## Appendix: how the measured numbers were produced

Scripts and results are in `~/.moonwalking/analysis` on the owner's PC (not in git):
`recon.py` (24h ATR reconstruction from the candle archive), `matched_control.py` and
`evidence_block.py` (matched same-coin controls), `thr_year.py`, `thr_year2.py`,
`ctrl_tests.py` (sell-side replay and controls), and `score_ic.py` (information
coefficient of the current score). Inputs: a read-only snapshot of the production
`signal_outcomes.sqlite` and the separate candle archive.
