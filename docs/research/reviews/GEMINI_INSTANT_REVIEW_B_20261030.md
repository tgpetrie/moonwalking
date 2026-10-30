**Source Inspection & Availability Confirmation**
All five source sections in the attached `Moonwalking-Gemini-941f47a.txt` bundle were readable and directly inspected:

1. `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (blob `9edf93a789541a813734569da8a6b1d127c7fe70`, 24,078 bytes)


2. `docs/research/INSTANT_TARGET_CONTRACT_V1.json` (blob `2f89ddc9b2110e6f134b90b90878373374f44e00`, 2,329 bytes)


3. `docs/research/INSTANT_TARGET_LABELS_20261029.md` (blob `1637825ec149b28f2417dfa47ea08fd4217449c6`, 9,178 bytes)


4. `scripts/scoring_experiment/instant_targets.py` (blob `24005f0c2523cc874c2a5e8675cd795fe791503e`, 16,465 bytes)


5. `tests/test_instant_targets.py` (blob `1595b6baa8d20d10a9812d0a767bc23317`, 16,283 bytes)



**Unavailable Sources:**

* **Original Unamended Proposal Text:** Not present in this conversation except as quoted, summarized, and corrected inside `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md`. Where this review compares the implementation to the original proposal, it relies strictly on the explicit boundary statements in `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` and `INSTANT_TARGET_LABELS_20261029.md` rather than reconstructing unverified text from memory.


* **Referenced Auxiliary Files:** `docs/research/LIVE_MOVERS_DATA_CONTRACT_20261027.md`, `backend/coinbase_ws.py`, and `results/feed_audit_20261028_completed/REPORT.json` are referenced in the markdown documents but are outside the five-file bundle.


* **Test Execution:** No tests were executed; `tests/test_instant_targets.py` was reviewed statically.



---

## 1. Reconsideration of Preliminary Review vs. Actual Implementation

Inspecting the actual code in `scripts/scoring_experiment/instant_targets.py` resolves several concerns raised in the preliminary conceptual review while exposing specific code-level measurement distortions:

* **Two-Tier Label Separation Already Implemented (`verified_forward` vs. `verified_onset`):** The preliminary review warned that gating the entire dataset on a velocity/activity threshold would blind the system to smooth movers and prevent a recall audit. In fact, `TargetEvaluator.evaluate()` computes `verified_forward` unconditionally at every eligible 5s grid anchor (`instant_targets.py`, lines 211–263) before and independently of `verified_onset` (lines 264–337). Even when pace baselines are unavailable, `verified_forward` is preserved (`test_onset_unavailable_does_not_erase_complete_forward_label` in `test_instant_targets.py`, lines 242–255).


* **Pre-Onset vs. Post-Onset Separation Already Implemented:** `TargetEvaluator.alert_timing()` (`instant_targets.py`, lines 339–395) explicitly separates `[anchor - 180s, anchor)` (`pre_onset_prediction`) from `[anchor, peak_ts_ms]` with `< 0.5` consumed (`early_detection`) and `late_detection`.


* **Unknown Data Never Becomes False:** `TargetEvaluator._quality()`, `_baseline_quality()`, and `evaluate()` return `status="pending"` before `anchor + H` and `status="unavailable"` with `verified_forward=None, verified_onset=None` on any missing grid point, stale quote (`> 10000ms`), `last_trade_fallback`, or unverified coverage (`instant_targets.py`, lines 113–175, 198–218).



However, inspecting the exact equations in `instant_targets.py` reveals **concrete measurement defects** in how `verified_onset`, breakout, no-retrace, and `consumed_fraction` interact.

---

## 2. Assessment of Target Definitions & Demonstrated Code Defects

### 1. Activity-Confirmed Velocity Crossing as "Onset" vs. Physical Beginning of a Move

In `instant_targets.py` (lines 294–318), `onset_candidate` fires at `anchor` ($t_0$) when:

* `previous_velocity < 1.0 - 1e-12` over `[anchor - 35s, anchor - 5s]`,


* `current_velocity >= 1.0 - 1e-12` over `[anchor - 30s, anchor]` (where 30s residual log return is normalized by $\sigma_{1\text{m}} / \sqrt{2}$),


* `recent_trades >= 5` in `(anchor - 30s, anchor]` and `pace > 2.0 + 1e-12` against the 120-window median.



**Conceptual vs. Code Assessment:**
`INSTANT_TARGET_LABELS_20261029.md` ("Two separate labels") explicitly acknowledges that *"Onset means an activity-confirmed threshold crossing; it is not a claim to identify the physical first tick of a move."* While honest, anchoring the event at `anchor` means at least $\ge 1.0 \cdot (\sigma_{1\text{m}}/\sqrt{2})$ of favorable residual displacement has **already occurred during `[anchor - 30s, anchor]**` just to trip `current_velocity`. Because `TargetEvaluator.evaluate()` sets the forward path origin to `anchor` (`path = [(ts, self._residual(anchor, ts, ...))]`, line 220), that pre-crossing displacement (`[anchor - 30s, anchor]`) is erased from `terminal_residual_log`, `peak_residual_log`, and `consumed_fraction`.

### 2. Breakout Measured from Crossing with a 180-Second Deadline

In `instant_targets.py` (lines 319–326):

```python
breakout_ts = next(
    (
        ts
        for ts, value in path[1:]
        if ts <= anchor + onset["breakout_deadline_seconds"] * 1000
        and value + tolerance >= onset["breakout_sigma"] * sigma
    ),
    None,
)

```

**Code-Demonstrated Measurement Distortion (Origin Reset Penalty):**
Because `path` measures cumulative residual strictly from `anchor` (`self._residual(anchor, ts, ...)`), `value >= 1.5 * sigma` requires an **additional** $+1.5\sigma_{1\text{m}}$ of favorable residual *after* `anchor` on top of the $\ge 0.707\sigma_{1\text{m}}$ ($1.0 \cdot \sigma_{1\text{m}}/\sqrt{2}$) already achieved at `anchor`. If a coin surges $+2.0\sigma_{1\text{m}}$ in a single 5s bucket `[anchor - 5s, anchor]` to cross the velocity gate, pauses for 180 seconds to digest the spike, and then trends to $+4.0\sigma_{1\text{m}}$ by 300s, `breakout_ts` is `None` and `verified_onset` is `False`—whereas a slower coin that barely crosses $+0.71\sigma_{1\text{m}}$ at `anchor` and adds $+1.5\sigma_{1\text{m}}$ at `anchor + 180s` passes.

### 3. No-Retracement Requirement Through the Entire 5m/15m Horizon

In `instant_targets.py` (lines 226 and 327):

```python
adverse = min(value for _, value in path)
...
no_retrace = adverse >= -onset["no_retrace_tolerance_log"]  # -1e-12

```

**Code-Demonstrated Measurement Defect (Single-Grid-Point Microstructure Fragility):**
Because `path` starts at `anchor` where `value == 0.0`, `no_retrace` requires that across all 60 grid points (for 5m) or 180 grid points (for 15m), the market-relative residual **never dips even 0.01 bps (`1e-6`) below `anchor`'s exact midpoint**.

* **Why this is a critical defect at `anchor`:** At `anchor`, the coin has just completed a $\ge 30\text{s}$ aggressive taker burst (`pace > 2.0`, `velocity_sigma >= 1.0`). In real L1 order books, an aggressive taker sweep widens the spread or temporarily exhausts one side of the BBO; on the very next 5s snapshot (`anchor + 5000`), passive replenishment or a 1-tick BTC uptick (when `beta > 0`) routinely causes `self._residual(anchor, anchor + 5000, ...)` to print `-0.0001` before resuming a $+3.0\%$ trend.


* Even `test_later_retrace_rejects_onset_but_preserves_forward_impulse` (`test_instant_targets.py`, lines 135–146) demonstrates that a single 5s dip rejects `verified_onset` while `verified_forward` is `True`. Requiring zero pullback below the post-burst `anchor` price for 15 full minutes guarantees massive attrition between `verified_forward` and `verified_onset`, selecting almost exclusively synthetic or ultra-low-noise monotonic drifts.



### 4. Signed, Market-Relative Magnitude, Retention, and Fraction Consumed

* **Signed & Market-Relative Magnitude (`instant_targets.py`, lines 177–180, 220–243):** Properly direction-symmetric (`sign = 1 if direction == "up" else -1`) and properly scaled against `max(3 * sigma * sqrt(H/60), 0.015, 3 * entry_spread_fraction)`.


* **Retention (`instant_targets.py`, lines 224–227):** Properly checks `terminal / peak >= 0.6` with first-timestamp tie-breaking (`peak_ts, peak = max(path, key=lambda pair: pair[1])`).


* **Consumed Fraction (`instant_targets.py`, lines 371–373) — Demonstrated Reference-Point Distortion:**
```python
consumed = (
    self._residual(anchor, ts, label["beta"], sign) / label["peak_residual_log"]
)

```


When an alert is published at `publish_ts_ms == anchor` (exact onset detection, `detection_delay_seconds == 0`), `ts == anchor`, so `self._residual(anchor, anchor, ...)` is identically **`0.0`** (`consumed == 0.0`, verified in `test_unaligned_publication_uses_only_backward_asof_snapshot`, line 292). Yet by the definition of `onset_candidate`, at `ts == anchor` the coin has *already* moved at least $\ge 1.0 \cdot (\sigma_{1\text{m}}/\sqrt{2})$ over the preceding 30 seconds. Reporting `consumed_fraction = 0.0` at `anchor` artificially flatters on-trigger detections by ignoring the pre-anchor leg of the move.



### 5. Separation of Prediction Before Onset from Detection Afterward

* **In `alert_timing()` (`instant_targets.py`, lines 339–395):** The code cleanly separates `pre_onset_prediction` (`publish_ts_ms < anchor`, within 180s), `early_detection` (`anchor <= publish_ts_ms <= peak_ts_ms` and `consumed < 0.5`), and `late_detection`. It also strictly enforces backward as-of grid lookup (`ts = publish_ts_ms // self.cfg["grid_ms"] * self.cfg["grid_ms"]`, line 359) and verifies quote freshness at actual `publish_ts_ms` (lines 364–369).


* **Missing Protocol Gate:** As acknowledged in `INSTANT_TARGET_LABELS_20261029.md` ("Maturity, event catalog and alert timing"), `alert_timing()` grades a single `(label, publish_ts_ms)` pair, but **multi-event alert assignment** (when a single alert falls inside `[anchor - 180s, anchor + H]` for both a 5m and 15m event, or when an alert fires when `verified_forward=True` but `verified_onset=False`) is not yet implemented in `instant_targets.py`.



### 6. Event Deduplication, Missed-Move Coverage, and Exclusion of Unknown Data

* **Event Deduplication (`event_catalog` in `instant_targets.py`, lines 398–424):** Selects the earliest `verified_onset` per `(product_id, direction, horizon_seconds)` and suppresses subsequent `verified_onset` rows in `[anchor, anchor + H)`.


* **Code-Demonstrated Gap in Catalog Coverage:** `event_catalog()` filters exclusively on `if row.get("verified_onset")` (line 419). If a coin experiences a genuine $+5\%$ 5m move (`verified_forward == True`) that either accelerated smoothly without crossing `pace > 2.0` or had a 1-tick pullback at `anchor + 5s` (`no_retrace == False`, so `verified_onset == False`), **`event_catalog()` drops the move completely** and `alert_timing()` raises `ValueError("a verified onset from this contract and product is required")` (lines 346–350). Consequently, missed-move coverage and alert timing cannot be evaluated on `verified_forward`-only episodes unless a parallel forward-event catalog is built.




* **Unknown Data Exclusion (`instant_targets.py`, lines 113–175, 206–218):** Exemplarily strict. Missing grid points, stale quotes, `last_trade_fallback`, unverified coverage, and unknown `trade_count_at_bucket_start` all resolve to `status="unavailable"` with `None` booleans, never `False`.



---

## 3. Circularity Analysis: `onset_candidate` vs. Prospective F1/F2

### Exact Algebraic Overlap in the Codebase

Comparing `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Section 4) with `scripts/scoring_experiment/instant_targets.py` (lines 294–318) exposes direct mathematical coupling between the prospective features and `verified_onset`:

1. **Onset Velocity vs. F1 (Midpoint Acceleration) & F5 (Market Residual):**
* In `instant_targets.py` (lines 294–299), `current_velocity` is the 30s market-relative residual divided by $\sigma_{1\text{m}}/\sqrt{2}$, and `onset_candidate` requires `previous_velocity < 1.0` and `current_velocity >= 1.0`.


* In `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Section 4), **F5** is the market-relative residual over 30s/180s (`x_i,j = log(mid_i,j / mid_i,j-1) - beta_i * log(mid_BTC,j / mid_BTC,j-1)` scaled by $\sigma_{i,1\text{m}}(t_0)$), and **F1** is midpoint acceleration over the non-overlapping 30s and preceding 150s windows normalized by $\sigma_{i,1\text{m}}(t_0)$.


* Because `current_velocity >= 1.0` and `previous_velocity < 1.0` forces the 30s residual return at `anchor` to be both large ($\ge 0.707\sigma_{1\text{m}}$) and strictly rising over the last 5s step (`current_velocity - previous_velocity > 0`), any grid point where `verified_onset == True` is **guaranteed by definition** to have high positive F5 and elevated F1 at `t0 = anchor`.




2. **Onset Activity Gate vs. F2 (Signed Participation & Pace):**
* In `instant_targets.py` (lines 300–318), `onset_candidate` requires `recent_trades >= 5` in `[anchor - 25s, anchor]` and `pace > 2.0` (30s trade count or USD volume divided by the 120-window median).


* In `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Section 4), **F2** is defined as `TakerImb * log(1 + PaceRatio)`, gated on `>= 5` unique matches in the 30s window.


* Thus, the exact eligibility gate (`>= 5` matches) and the unsigned magnitude multiplier (`PaceRatio`) of F2 are hard-coded into the definition of `verified_onset`.





### How F1, F2, and F5 Can Appear Successful Purely by Circularity

If the discovery fit or validation evaluation predicts `verified_onset` across the full universe of `(product_id, anchor_ts_ms)` rows (`INSTANT_TARGET_CONTRACT_V1.json`: `"universe": "all_causally_eligible_products_and_grid_times_including_no_move_rows"`):

* Any row with `recent_trades < 5`, `pace <= 2.0`, or `current_velocity < 1.0` has `verified_onset == False` **100% of the time by deterministic rule**, regardless of what price does over the next 5m/15m.


* A model using F1, F2, and F5 at `anchor` will achieve near-perfect rejection of non-candidate rows simply by replicating the `onset_candidate` boundary, even if F1 and F2 have zero ability to predict whether the move continues after `anchor` (`verified_forward`, `breakout_ts`, and `no_retrace`).



### How to Evaluate Predictive Contribution Without Circular Advantage

Because `instant_targets.py` already outputs both `verified_forward` and `onset_candidate` alongside `verified_onset`, circularity can be completely eliminated by enforcing three evaluation rules in the prospective study:

1. **Primary Point-in-Time Target Must Be `verified_forward`, Not `verified_onset`:**
When training or evaluating F1–F5 at cutoff $t_0 = \text{anchor}$ across the full eligible universe, fit and score against **`verified_forward`** (which depends *only* on future path `(anchor, anchor + H]` and causal $\sigma, \beta$, and never touches pre-anchor velocity or pace).


2. **Conditional Post-Trigger Evaluation (`verified_forward | onset_candidate == True`):**
When evaluating at `anchor` among triggered candidates (`onset_candidate == True`), condition the sample on `onset_candidate == True` and include `velocity_sigma` and `pace_multiple` (already returned by `evaluate()` at lines 331–332) in the baseline null model. Credit F1 (150s-to-30s convexity) and F2 (`TakerImb` signed directionality) *only* for their marginal log-loss / Top-$K$ precision lift above unsigned `pace_multiple` and `velocity_sigma`.


3. **Strict Pre-Onset Lead Evaluation (`t_0 <= anchor - 5s`):**
When using `event_catalog()` (`verified_onset` episodes) to evaluate early-warning alerts via `alert_timing()`, evaluate F1–F5 strictly in the **`pre_onset_prediction` window (`[anchor - 180s, anchor - 5s]`)** where `onset_candidate` has not yet fired.



---

## 4. Candidate Mechanism Review (F1–F5)

### Standalone vs. Marginal Contribution & Structural Controls

In accordance with `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Sections 4–6):

* **Standalone vs. Conditional (Additional) Information:** Each feature must be evaluated both standalone (controlling for baseline $\sigma_{1\text{m}}$, spread, and liquidity) and via **leave-one-out ablation** from the full five-feature directional model `(F1, F2, F3, F4, F5)`. For instance, because the smoothed input specification in Section 4 (`S_i,h,j`) already subtracts $\beta_i \log(\text{mid}_{\text{BTC},j}/\text{mid}_{\text{BTC},j-1})$, F1 and F5 will be heavily collinear unless F1 measures strictly the *difference* between the 30s and preceding 150s rates of change while F5 measures the *level* of market-relative displacement.


* **Non-Board Eligible Universe:** Every 5s grid point for all causally eligible products—including dormant coins that never enter Top-$K$ (`K=5`, `K=10`) or never cross `onset_candidate`—must remain in the denominator for false-alert/hour and missed-move rates.


* **Liquidity, Market-Wide Moves, and Dependent Observations:** Stratify performance by trailing daily USD volume and baseline spread (`spread_bps`). Because alerts and grid rows across products and horizons within the same UTC day share BTC shocks and overlapping 5m/15m windows, all confidence intervals for feature ablations must use the contract's **paired UTC-day block bootstrap** (Section 6), never naive per-alert or per-row binomial standard errors.



### Feature Evaluation Matrix (F1–F5)

| Feature | Precise Hypothesis | Expected Behavior (Up vs. Down) | Timing Relative to Onset | Appropriate Baseline / Ablation | Supporting Evidence | Rejecting Evidence | Inconclusive Evidence | Data-Quality Checks & Major Confounders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **F1: Midpoint Acceleration** | Convexity between the non-overlapping 30s midpoint return and preceding 150s return (normalized by causal $\sigma_{1\text{m}}$ with `0.0015` floor) predicts 5m/15m `verified_forward` continuation better than a constant-velocity 180s drift.

 | **Up (`d=+1`):** $r_{30\text{s}}/\sigma_{1\text{m}}$ significantly exceeds the per-30s rate of the preceding 150s window.<br>

<br>**Down (`d=-1`):** Signed $-r_{30\text{s}}/\sigma_{1\text{m}}$ significantly exceeds preceding 150s signed rate.

 | **Late pre-onset (`[anchor-30s, anchor)`) and at `anchor`:** Captures the inflection from flat/slow 150s baseline into the 30s ramp. | **Baseline:** Single-window 30s velocity (`velocity_sigma`) + F5 market residual.<br>

<br>**Ablation:** Full `[F1..F5]` model minus `F1` on `verified_forward` and conditional on `onset_candidate`. | Positive marginal improvement in out-of-sample `verified_forward` precision at Top-$K$ (`K=5, 10`) and log-loss over F5 + F2 across paired UTC-day blocks.

 | High 30s acceleration relative to 150s marks short-lived blow-off spikes that fail the 60% `retention` rule (`test_large_wick_with_good_terminal_magnitude_fails_retention`).

 | Standalone lift is positive on `verified_onset` (due to circularity with `velocity_crossing_sigma`), but marginal lift on `verified_forward` after controlling for F2 and F5 spans zero across the 7 validation day-blocks.

 | **Checks:** Exclude `last_trade_fallback`; require quote age $\le 10\text{s}$ at `b`, `b-30s`, and `b-180s`, plus $\ge 1$ live match in window.

<br>

<br>**Confounders:** `EXTENDED` coins (`E > 3.5`) accelerating into exhaustion; wide-spread midpoint jumps.

 |
| **F2: Match-Derived Signed Participation & Pace** | Directional aggressor imbalance (`TakerImb * log(1 + PaceRatio)` from deduplicated `matches` with maker-side inversion, gated on $\ge 5$ matches in 30s) identifies informed liquidity absorption before and during breakout.

 | **Up (`d=+1`):** `taker_buy_usd > taker_sell_usd` (`TakerImb > 0`) amplified by `PaceRatio > 1`.<br>

<br>**Down (`d=-1`):** `taker_sell_usd > taker_buy_usd` (`TakerImb < 0`) amplified by `PaceRatio > 1`.

 | **Both before onset (`[anchor-180s, anchor)`) and at `anchor`:** Taker absorption against resting limit orders precedes midpoint displacement and separates real volume from thin-book quote shifts.

 | **Baseline:** Unsigned `pace_multiple` and `recent_trade_count` (the exact `onset_candidate` activity inputs in `instant_targets.py` lines 303–311).<br>

<br>**Ablation:** `[F1..F5]` minus `TakerImb` sign, and minus `F2` entirely.

 | Adding signed `TakerImb` improves `pre_onset_prediction` recall and increases conditional `verified_forward` precision among `onset_candidate` rows above unsigned `pace_multiple`.

 | Signed taker imbalance shows zero or negative lift over unsigned pace (e.g., aggressive taker sweeps into passive iceberg walls that mean-revert within 5m/15m). | Step 2.5 feed audit remains unverified on thin products (as seen in `INSTANT_TARGET_LABELS_20261029.md` where ALCX/AURORA had only 4 and 3 paired trades), or validation day-block CI spans zero.

 | **Checks:** Deduplicate by `(product_id, trade_id)`; ignore initial `last_match` snapshot; withhold F2 on REST-unreconciled gaps or unknown maker side.

<br>

<br>**Confounders:** Thin-coin `< 5` match gate exclusions; wash prints; iceberg passive absorption. |
| **F3: Sampled BBO Pressure & Spread** | Time-weighted L1 order-book imbalance (from verified `ticker` bid/ask sizes) paired with tight relative spread (`spread_bps`) signals queuing support and low friction for clearing the $3 \times \text{entry\_spread}$ target threshold.

 | **Up (`d=+1`):** Time-averaged bid size > ask size with narrow/stable `spread_bps`.<br>

<br>**Down (`d=-1`):** Time-averaged ask size > bid size with narrow/stable `spread_bps`. | **Before onset (`t < anchor`)** as directional pressure; **at `anchor**` primarily as a feasibility/friction filter (since `required_terminal_log` scales with `3 * entry_spread_fraction`, line 232).

 | **Baseline:** Entry `spread_bps` alone + F2 match flow.<br>

<br>**Ablation:** `[F1..F5]` minus `F3` (and separating BBO size imbalance from `spread_bps`). | Time-weighted BBO imbalance adds pre-onset lead time (`pre_onset_prediction` share) or filters out wide-spread false alerts that fail net-of-cost bps scenarios.

 | L1 size imbalance is contrarian (large visible L1 size is spoofing or passive supply/demand that blocks the move) or adds zero lift once `spread_bps` and F2 are included. | Sampled `ticker` batching misses rapid intra-5s L1 queue depletion, leaving F3 noisy with paired day-block intervals overlapping zero.

 | **Checks:** Carry prior quote only with original `quote_ts_ms`; mark durations with quote age $> 10\text{s}$ unavailable; reject crossed books (`ask < bid`).

<br>

<br>**Confounders:** L1-only depth hiding L2 liquidity; `ticker` sampling bias toward trade events. |
| **F4: Compression Followed by Expansion** | Moves launching from a tight, actively traded prior 15m volatility/range regime ($\ge 10$ traded 1m candles in prior 15 completed minutes) into a 30s expansion achieve higher 5m/15m retention than moves in already-dispersed books.

 | **Symmetric regime modifier** (interacts with direction $d \in \{+1, -1\}$ from F1/F2/F5): Low prior 15m range/volatility relative to baseline followed by +30s expansion (Up) or -30s expansion (Down).

 | **Pre-onset setup (`t < anchor`)** defines compression; **inflection at `anchor**` triggers expansion. | **Baseline:** Causal $\sigma_{1\text{m}}$ (60m baseline) + F1 acceleration without 15m compression conditioning.<br>

<br>**Ablation:** `[F1..F5]` minus `F4`.

 | Conditioning on prior 15m active compression increases `retention` ($\ge 0.60$) and reduces `adverse_residual_log` drawdowns on 5m/15m `verified_forward` moves.

 | Compression fails to improve `verified_forward` hit rate over F1+F2, or inversely selects low-volatility/pegged coins that fail the `0.015` (1.5%) minimum log return floor.

 | Positive association in discovery disappears when controlling for the $\ge 10$ traded-candles activity gate or across the 7 validation day-blocks.

 | **Checks:** Strictly enforce $\ge 10$ traded closed 1m candles in prior 15m available $\le t_0$ so dead/illiquid books or feed outages are never scored as "compressed".

<br>

<br>**Confounders:** Diurnal quiet hours; $\sigma_{1\text{m}}$ floor (`0.0015`) clipping true ultra-low volatility.

 |
| **F5: Market-Relative Movement** | Idiosyncratic coin displacement net of synchronous causal BTC movement ($r_{\text{coin}} - \beta r_{\text{BTC}}$, scaled by $\sigma_{1\text{m}}$) isolates asset-specific repricing that persists over 5m/15m, avoiding false alerts during market-wide BTC sweeps.

 | **Up (`d=+1`):** Positive decayed/boxcar residual return ($r_{\text{coin}} - \beta r_{\text{BTC}} > 0$).<br>

<br>**Down (`d=-1`):** Negative residual return ($r_{\text{coin}} - \beta r_{\text{BTC}} < 0$).

 | **Both before onset** (diverging from BTC during market moves) **and at `anchor**` (suppressing pure beta cascades). | **Baseline:** Unadjusted raw coin return (Percentage Move ranker) + `beta_fallback` flag.<br>

<br>**Ablation:** `[F1..F5]` using market-relative F5 vs. replacing F5 with raw unadjusted return.

 | Outperforms raw percentage-move ranker on `verified_forward` Top-$K$ precision and significantly reduces false alerts/hour during high-BTC-volatility blocks (`test_market_move_is_not_an_idiosyncratic_impulse`).

 | Residual adjustment degrades net-of-cost coin return (`gross_coin_return_bps`) or underperforms raw return because high-beta lag effects dominate 5m/15m moves. | BTC volatility is flat during the 7-day validation window ($\log(\text{BTC}_t/\text{BTC}_0) \approx 0$), making F5 nearly identical to raw coin return and F1.

 | **Checks:** Require synchronized coin and BTC `quote_ts_ms` within `10000ms` of cutoff and `price_source == "mid"`; track `beta_fallback == True` cohort separately.

<br>

<br>**Confounders:** Stale/fallback $\beta=1.0$ mis-scaling low-beta or high-beta alts; altcoin lead-lag delay behind BTC impulses.

 |

---

## 5. Final Verdict, Ranked Corrections, and Remaining Frozen Definitions

### Verdict on Target Alignment

**`verified_forward` Matches the Intended Task; `verified_onset` and `event_catalog` Introduce Three Measurement Distortions.**

1. **What Matches:** The separation of causal inputs (`Sample`, `Baseline`) from evaluation outcomes (`TargetEvaluator.evaluate`), the strict `pending`/`unavailable` missingness handling, the 30s/180s input vs. 300s/900s outcome split, and the `verified_forward` label (`instant_targets.py`, lines 211–263) faithfully implement the corrected prospective contract.


2. **What Diverges / Distorts Measurement:**
* **Circularity on `verified_onset`:** `onset_candidate` hard-codes the exact 30s velocity (`>= 1.0 sigma`), 30s match count (`>= 5`), and 30s pace (`> 2.0x`) mechanics that define F1, F2, and F5.


* **Post-Anchor Origin Reset (`instant_targets.py`, lines 220, 319–327, 371):** Anchoring `path`, `breakout_ts`, `no_retrace`, and `consumed_fraction` at `anchor` (after the 30s onset ramp has already happened) requires the coin to add *another* $+1.5\sigma_{1\text{m}}$ after `anchor`, forbids even a `-1e-12` 1-tick pullback below the post-burst `anchor` price for 5m/15m, and misreports `consumed_fraction` as `0.0` at `anchor`.


* **Catalog Blindness to Non-Onset Forward Movers (`instant_targets.py`, lines 348, 419):** Because `event_catalog()` and `alert_timing()` require `verified_onset == True`, genuine 5m/15m impulses (`verified_forward == True`) that fail the strict `no_retrace` or `pace > 2.0` gates are excluded from event-level missed-move and alert-timing metrics.





---

### Ranked Corrections Needed Before Prospective Outcome Analysis

1. **Make `verified_forward` the Primary Point-in-Time Target and Build a Parallel Forward-Event Catalog (`instant_targets.py`, lines 346–350, 398–424):**
* *Measurement Problem Fixed:* Prevents F1, F2, and F5 from winning discovery/validation via deterministic overlap with `onset_candidate`, and stops `event_catalog()` / `alert_timing()` from discarding real 5m/15m moves (`verified_forward == True, verified_onset == False`) when computing missed-move rates and false-alert denominators.




2. **Include the Pre-Anchor Onset Leg (`anchor - 30s` or Pre-Ramp Minimum) in `consumed_fraction` and Breakout Excursion (`instant_targets.py`, lines 319–326, 371–373):**
* *Measurement Problem Fixed:* Currently, an alert published at `anchor` (`detection_delay_seconds == 0`) gets credited with `consumed_fraction = 0.0` even though at least $\ge 0.707\sigma_{1\text{m}}$ (and often 20%–40% of the total move) already occurred during `(anchor - 30s, anchor]` to trip `current_velocity >= 1.0`. Similarly, measuring the $1.5\sigma_{1\text{m}}$ breakout from `anchor - 30s` (or crediting the onset impulse) stops penalizing fast 30s surges that consolidate after `anchor`.




3. **Relax `no_retrace` from `-1e-12` at `anchor` to a Pre-Onset Reference (`anchor - 30s`) or a Volatility/Spread-Scaled Adverse Tolerance (`instant_targets.py`, line 327; `INSTANT_TARGET_CONTRACT_V1.json`, line 22):**
* *Measurement Problem Fixed:* After a 30s aggressive taker sweep (`pace > 2.0`), a 1-tick BBO bounce or a 1-tick BTC move at `anchor + 5s` causes `self._residual(anchor, anchor + 5000, ...)` to drop below `-1e-12`, setting `no_retrace = False` and rejecting genuine sustained breakouts (`verified_forward == True`). Benchmarking `no_retrace` against `anchor - 30s` (the pre-crossing price) or allowing an adverse buffer scaled to entry `spread_bps` / $\sigma_{1\text{m}}$ eliminates single-tick microstructure rejection.




4. **Verify `pace_end_ts_ms` Non-Overlap Against `velocity_ms` in Documentation vs. Code (`instant_targets.py`, lines 281–284, 300–302):**
* *Measurement Problem Fixed:* In `instant_targets.py` (line 301), `recent` spans `range(anchor - velocity_ms + step, anchor + 1, step)`, which covers the 6 buckets `[anchor - 25s, anchor]` (covering time `[anchor - 30s, anchor)`), and line 282 checks `baseline.pace_end_ts_ms != anchor - velocity_ms` (`anchor - 30s`). Ensure the upstream `Baseline` builder computes the 120-window median strictly over `[anchor - 3630s, anchor - 30s]` so the active 30s window is never included.





---

### Remaining Definitions That Must Be Frozen Before Collection or Fitting

In addition to the five gates listed in `INSTANT_TARGET_CONTRACT_V1.json` (`remaining_study_gates`, lines 49–55), freeze the following exact specifications before unlocking `fitting_allowed`:

1. **Exact Mathematical Formulas for F1–F5 & Orthogonality Between F1 and F5:** Specify whether F1 uses raw midpoint log returns or BTC-residual log returns (`x_i,j`), and freeze the exact formula combining the 30s and preceding 150s windows so F1 and F5 are not redundant linear combinations of the same 30s/180s decayed sums.


2. **Multi-Event Alert Assignment & Operational Denominator Rules:** Define how a single published alert at `t_alert` is scored when it overlaps both a 5m and 15m event, how alerts firing on `verified_forward=True, verified_onset=False` episodes are classified (true positive vs. false alert), and the exact denominator for `false_alerts_per_hour`.


3. **Live Stage Thresholds (`CONFIRMED` vs. `IGNITING` vs. `FADING/ABSORBED`):** While `EXTENDED` (`E > 3.5` or `abs(r_24h) > 10%` with `< $1M` volume) and the `>= 5` matches gate for `IGNITING` are specified in `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Sections 3 & 5), the exact numeric feature cutoffs separating `IGNITING`, `CONFIRMED`, and `FADING/ABSORBED` must be frozen.


4. **Discovery Readiness Minima:** Freeze the minimum required count of deduplicated `verified_forward` and `verified_onset` episodes per direction (`up`, `down`) and horizon (`300s`, `900s`), and the minimum number of valid products passing the Step 2.5 feed-side/coverage audit during Days 1–7 before any regularized five-feature weight fit is permitted.
