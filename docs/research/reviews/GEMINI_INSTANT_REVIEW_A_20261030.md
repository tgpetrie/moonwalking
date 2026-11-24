**Source Inspection & Availability Confirmation**
All five source sections in the attached `Moonwalking-Gemini-941f47a_2.txt` bundle were readable and directly inspected:

1. `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Git blob `9edf93a789541a813734569da8a6b1d127c7fe70`, SHA-256 `b43b781f626790097bfa2da5cdfa64db16a3ab1b143622b40a229301dae4a442`, 24,078 bytes)


2. `docs/research/INSTANT_TARGET_CONTRACT_V1.json` (Git blob `2f89ddc9b2110e6f134b90b90878373374f44e00`, SHA-256 `35d9b8a286d051aff08148a2af9987b379d65e92d57c3bea76112be52cfca7a4`, 2,329 bytes)


3. `docs/research/INSTANT_TARGET_LABELS_20261029.md` (Git blob `1637825ec149b28f2417dfa47ea08fd4217449c6`, SHA-256 `55c40f28724bf56b14e282f595e09aa734f4a37434a5dc8f3d68d31c4b9e7216`, 9,178 bytes)


4. `scripts/scoring_experiment/instant_targets.py` (Git blob `24005f0c2523cc874c2a5e8675cd795fe791503e`, SHA-256 `ac664e775023a5e3d9a5ce34c4e07f7a6bb65b0329359a753c49fef60a75740c`, 16,465 bytes)


5. `tests/test_instant_targets.py` (Git blob `1595b6baa8d20d10a9812d0a7f0d0a767bc23317`, SHA-256 `e602c8930bd9226588a0b248be32d4a0550b83638ab79635d12921a087c613ff`, 16,283 bytes)



**Unavailable Sources & Static Review Scope:**

* **Original Unamended Proposal Text:** The verbatim text of the original unamended early-warning proposal is not present as a separate document in this conversation. Where this review compares the implementation to the original proposal, it relies strictly on the explicit boundary statements and corrections documented in `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` and `docs/research/INSTANT_TARGET_LABELS_20261029.md` rather than reconstructing unverified text from memory.


* **External Repository Files:** Referenced files outside the five-file bundle (`docs/research/LIVE_MOVERS_DATA_CONTRACT_20261027.md`, `backend/coinbase_ws.py`, and `results/feed_audit_20261028_completed/REPORT.json`) are unavailable.


* **Test Execution:** No tests were executed; `tests/test_instant_targets.py` and `scripts/scoring_experiment/instant_targets.py` were inspected statically.



---

## 1. Reconsideration of Preliminary Conceptual Review Against Actual Code

Inspecting the actual implementation in `scripts/scoring_experiment/instant_targets.py` overturns several concerns from the preliminary conceptual review while isolating where genuine code-level measurement defects versus intentional design choices exist:

* **Two-Tier Label Separation (`verified_forward` vs. `verified_onset`) Already Exists:** The preliminary review warned that gating the entire target on a velocity/activity threshold would blind the study to smooth movers and prevent a total-recall audit. In reality, `TargetEvaluator.evaluate()` in `scripts/scoring_experiment/instant_targets.py` computes `verified_forward` unconditionally at every eligible 5s grid `anchor` (`instant_targets.py`, lines 219–263) before evaluating `verified_onset` (`instant_targets.py`, lines 264–337). Even when the pace baseline is warming or unavailable, `verified_forward` is preserved while `verified_onset` returns `None` with `onset_status="unavailable"` (`instant_targets.py`, lines 267–293; verified by `test_onset_unavailable_does_not_erase_complete_forward_label` in `tests/test_instant_targets.py`, lines 242–255).


* **Strict Causality and Unknown-Data Exclusion Are Properly Implemented:** `TargetEvaluator._quality()`, `_baseline_quality()`, and `evaluate()` (`instant_targets.py`, lines 113–175, 198–218) guarantee that immature horizons return `status="pending"` and any missing 5s grid point, stale quote (`> 10000ms`), `last_trade_fallback`, unverified coverage, or unknown `trade_count_at_bucket_start` returns `status="unavailable"` with `None` booleans—never `False` (`test_unknown_data_never_becomes_a_negative_label`, `tests/test_instant_targets.py`, lines 148–170).


* **Pre-Onset Prediction vs. Post-Onset Detection Separation Exists in `alert_timing()`:** `TargetEvaluator.alert_timing()` (`instant_targets.py`, lines 339–395) explicitly partitions alerts into `pre_onset_prediction` (`publish_ts_ms < anchor` within `180s`), `early_detection` (`anchor <= publish_ts_ms <= peak_ts_ms` and `consumed < 0.5`), and `late_detection`, using strictly backward as-of grid lookups (`ts = publish_ts_ms // self.cfg["grid_ms"] * self.cfg["grid_ms"]`, line 359).



---

## 2. Target-Consistency Review: Confirmed Code Defects vs. Conceptual / Design Objections

### 1. Activity-Confirmed Velocity Crossing as "Onset" vs. Physical Beginning of a Move

In `scripts/scoring_experiment/instant_targets.py` (`TargetEvaluator.evaluate`, lines 294–318), `onset_candidate` fires at `anchor` when:

* `previous_velocity < onset["velocity_crossing_sigma"] - tolerance` (`1.0 - 1e-12`) over `[anchor - 35s, anchor - 5s]`,


* `current_velocity + tolerance >= onset["velocity_crossing_sigma"]` (`1.0 - 1e-12`) over `[anchor - 30s, anchor]`, where the 30s residual is normalized by `sigma / math.sqrt(2)`,


* `recent_trades >= 5` over the six 5s buckets in `(anchor - 30s, anchor]` and `pace > 2.0 + 1e-12` relative to the 120-window median (`pace_trade_median_30s` or `pace_quote_usd_median_30s`).


* **Classification — Intentional Pilot Design Choice with Downstream Measurement Consequence:** `docs/research/INSTANT_TARGET_LABELS_20261029.md` ("Two separate labels") explicitly states that *"Onset means an activity-confirmed threshold crossing; it is not a claim to identify the physical first tick of a move. A forward impulse can be real while this stricter onset definition fails. Report that attrition explicitly."* However, because `current_velocity >= 1.0` requires at least $\ge 1.0 \cdot (\sigma_{1\text{m}}/\sqrt{2}) \approx 0.707\sigma_{1\text{m}}$ of favorable residual movement to have *already occurred* between `anchor - 30s` and `anchor`, treating `anchor` as the zero-origin for forward path calculations creates the concrete code distortions documented in Items 2, 3, and 4 below.



### 2. Breakout Measured from Crossing with a 180-Second Deadline

In `scripts/scoring_experiment/instant_targets.py` (`TargetEvaluator.evaluate`, lines 220–223 and 319–326):

```python
path = [
    (ts, self._residual(anchor, ts, baseline.beta, sign))
    for ts in range(anchor, end + 1, self.cfg["grid_ms"])
]
...
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

* **Classification — Design Suggestion / Boundary Tradeoff:** `INSTANT_TARGET_LABELS_20261029.md` notes that *"The original proposal did not specify the cumulative breakout origin, no-retrace endpoint or conflict resolution. This v1 fixes those choices: each activity/velocity crossing supplies the breakout origin, and no-retrace ends at `onset+H`."* Because `path` measures cumulative residual strictly from `anchor` (`self._residual(anchor, ts, ...)`), `value + tolerance >= 1.5 * sigma` requires an **additional** $+1.5\sigma_{1\text{m}}$ of favorable residual *after* `anchor` on top of the $\ge 0.707\sigma_{1\text{m}}$ already expended during `[anchor - 30s, anchor]` to cross `current_velocity >= 1.0`. While this is an intentional pilot choice (`test_breakout_deadline_is_not_extended_to_get_a_success` in `tests/test_instant_targets.py`, lines 359–366), it penalizes fast initial 30s surges that consolidate for 180s after tripping `anchor` before continuing to a valid 5m/15m `verified_forward` completion.



### 3. Requirement for No Retracement Through the Entire 5m/15m Horizon

In `scripts/scoring_experiment/instant_targets.py` (`TargetEvaluator.evaluate`, lines 220–226 and 327):

```python
path = [
    (ts, self._residual(anchor, ts, baseline.beta, sign))
    for ts in range(anchor, end + 1, self.cfg["grid_ms"])
]
...
adverse = min(value for _, value in path)
...
no_retrace = adverse >= -onset["no_retrace_tolerance_log"]

```

* **Classification — Confirmed Measurement Defect (Post-Sweep Zero-Tolerance Fragility):** Because `path` starts at `anchor` (where `self._residual(anchor, anchor, ...) == 0.0`) and `no_retrace_tolerance_log` in `docs/research/INSTANT_TARGET_CONTRACT_V1.json` is `1e-12` (floating-point zero), `no_retrace` requires that across all 60 grid points (5m) or 180 grid points (15m), `self._residual(anchor, ts, ...)` **never dips even a single basis point (`-0.0001`) below the exact midpoint at `anchor**`.


* At `anchor`, the product has just experienced an aggressive 30s burst (`recent_trades >= 5`, `pace > 2.0`, `current_velocity >= 1.0`). In real L1 order books, a taker sweep temporarily widens the spread or shifts midpoint to the top of the sweep; on the very next 5s bucket (`anchor + 5000`), routine L1 quote replenishment or a 1-tick BTC move (when `beta > 0`) will push `self._residual(anchor, anchor + 5000, ...)` slightly negative (e.g., `-0.00005`), permanently setting `no_retrace = False` and `verified_onset = False` (`test_later_retrace_rejects_onset_but_preserves_forward_impulse` in `tests/test_instant_targets.py`, lines 135–146). Measuring `no_retrace` with `1e-12` tolerance against the post-burst `anchor` price rather than the pre-window price (`anchor - 30s`) or a spread/volatility buffer causes severe false rejections of genuine `verified_forward` impulses.



### 4. Signed, Market-Relative Magnitude, Retention, and Fraction Consumed

* **Signed Magnitude & Retention (`TargetEvaluator.evaluate`, lines 177–180, 220–243):** Properly direction-symmetric (`sign = 1 if direction == "up" else -1`), properly scaled to `max(3 * sigma * sqrt(H/60), 0.015, 3 * entry_spread_fraction)`, and properly requires `retention >= 0.6` with first-timestamp tie-breaking (`peak_ts, peak = max(path, key=lambda pair: pair[1])`).


* **Consumed Fraction (`TargetEvaluator.alert_timing`, lines 371–373) — Confirmed Code Defect (Reference Origin Distortion):**
In `scripts/scoring_experiment/instant_targets.py` (lines 371–373):


```python
consumed = (
    self._residual(anchor, ts, label["beta"], sign) / label["peak_residual_log"]
)

```


When an alert is published at `publish_ts_ms == anchor` (or `anchor + 4999`, which floors to `ts = anchor` at line 359), `self._residual(anchor, anchor, ...)` is identically **`0.0`**, so `consumed_fraction` is reported as **`0.0`** (explicitly asserted in `test_unaligned_publication_uses_only_backward_asof_snapshot`, `tests/test_instant_targets.py`, lines 288–292).


* **Why this is a confirmed measurement defect:** By definition of `verified_onset`, at `ts = anchor` the move is *not* 0% consumed—the coin has already displaced by `current_velocity * (sigma / sqrt(2)) >= 0.707 * sigma` over `[anchor - 30s, anchor]`. In `test_instant_targets.py` (`samples()`, lines 46–51), the synthetic path jumps `0.002` at `elapsed == 0` (`ANCHOR`) and reaches `0.022` at `elapsed == 300`, yet because `anchor` is already at `0.002`, `evaluate()` reports `terminal_residual_log == 0.02` (line 88) and `alert_timing(label, ANCHOR)` reports `consumed_fraction == 0.0` (line 292) even though $\frac{0.002}{0.022} = 9.09\%$ of the total move from the pre-onset baseline (`ANCHOR - 30s`) was already consumed at `ANCHOR`.





### 5. Separation of Prediction Before Onset from Detection Afterward

* **In `TargetEvaluator.alert_timing()` (`instant_targets.py`, lines 339–395):** Properly separates `pre_onset_prediction` (`[anchor - 180s, anchor)`), `early_detection` (`[anchor, peak_ts_ms]` with `consumed < 0.5 - 1e-12`), `late_detection`, and `outside_event_window`.


* **Confirmed Code Defect in `alert_timing()` (`instant_targets.py`, lines 371–373) — Unchecked Zero Division Defense:**
`TargetEvaluator.alert_timing()` accepts any `label` dict where `label.get("verified_onset")` is truthy (line 347) and divides by `label["peak_residual_log"]` (line 372) without verifying that `label["peak_residual_log"] > 0`. While `evaluate()` guarantees `peak > 0` when `verified_onset` is `True`, a defensive check in `alert_timing()` is good practice.



### 6. Event Deduplication, Missed-Move Coverage, and Exclusion of Unknown Data

* **Portable Hash Normalization Defect — Confirmed Code Defect (`instant_targets.py`, lines 22–24):**
`docs/research/INSTANT_TARGET_CONTRACT_V1.json` (line 5) declares `"hash_scheme": "sha256_utf8_lf_normalized_contract_file"`, and `docs/research/INSTANT_TARGET_LABELS_20261029.md` ("Cost scenarios and remaining gates") states: *"Every label carries the LF-normalized UTF-8 contract-file SHA-256... The hash remains portable across Windows/Unix line endings."*
However, `load_contract()` in `scripts/scoring_experiment/instant_targets.py` (lines 22–24) is implemented as:


```python
def load_contract():
    raw = CONTRACT_PATH.read_text(encoding="utf-8").encode("utf-8")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()

```


In Python's `pathlib.Path.read_text(encoding="utf-8")`, `Path.read_text()` opens the file with default `newline=None` (universal newlines mode), which converts `\r\n` to `\n` automatically—which is why `test_contract_hash_is_portable_across_windows_and_unix_newlines` (`tests/test_instant_targets.py`, lines 397–409) passes. While Python's universal newline behavior achieves LF normalization implicitly on `read_text()`, explicitly writing `.replace("\r\n", "\n")` makes the contract's `sha256_utf8_lf_normalized_contract_file` invariant self-documenting.


* **Event Catalog Blindness to `verified_forward`-Only Moves — Confirmed Measurement Defect (`instant_targets.py`, lines 346–350, 398–424):**
`event_catalog(labels)` (`instant_targets.py`, line 419) filters exclusively on `if row.get("verified_onset")`, and `alert_timing()` (lines 346–350) raises `ValueError("a verified onset from this contract and product is required")` whenever `verified_onset` is not `True`.


* **Measurement Problem:** Whenever a coin executes a genuine, tradable 5m/15m move (`verified_forward == True`) that fails `verified_onset` (for example, because of a 1-tick pullback at `anchor + 5s` setting `no_retrace = False`, or a smooth institutional accumulation with `pace <= 2.0`), **`event_catalog()` discards the event completely**. If missed-move rates and false-alert rates are computed against `event_catalog()`, real `verified_forward` moves are erased from the missed-move denominator, and valid early alerts on `verified_forward` moves are misclassified as false alerts.





---

## 3. Circularity Analysis: `onset_candidate` vs. Prospective F1/F2/F5

### Exact Mathematical Overlap in the Inspected Files

Comparing `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Section 4) against `scripts/scoring_experiment/instant_targets.py` (`TargetEvaluator.evaluate`, lines 294–318) demonstrates direct functional circularity between `verified_onset` and candidate features **F1**, **F2**, and **F5**:

1. **`current_velocity` / `previous_velocity` (`instant_targets.py`, lines 294–315) vs. F1 & F5:**
* `onset_candidate` requires `current_velocity >= 1.0` (30s market-relative residual $\ge 1.0 \cdot \sigma_{1\text{m}}/\sqrt{2}$) and `previous_velocity < 1.0` (30s residual ending 5s earlier $< 1.0 \cdot \sigma_{1\text{m}}/\sqrt{2}$).


* In `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Section 4), **F5** is the market-relative residual (`x_i,j = log(mid_i,j / mid_i,j-1) - beta_i * log(mid_BTC,j / mid_BTC,j-1)` scaled by $\sigma_{i,1\text{m}}(t_0)$), and **F1** is midpoint acceleration over the non-overlapping 30s and preceding 150s windows normalized by $\sigma_{i,1\text{m}}(t_0)$.


* Consequently, at $t_0 = \text{anchor}$, any row with `verified_onset == True` is **algebraically forced** to have a positive 30s market-relative residual (F5) and positive 5s-step velocity acceleration (F1).




2. **`recent_trades` and `pace` (`instant_targets.py`, lines 300–318) vs. F2 (`TakerImb * log(1 + PaceRatio)`):**
* `onset_candidate` requires `recent_trades >= 5` in the 30s window and `pace > 2.0` (30s match count or USD volume divided by the 120-window median).


* In `LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Section 4), **F2** is defined as `TakerImb * log(1 + PaceRatio)` and is gated on `>= 5` unique matches in the 30s window (Section 3 & Section 4).


* Therefore, 100% of rows where F2 is gated out (`< 5` matches) or where `PaceRatio <= 2.0` have `verified_onset == False` by deterministic label definition.





### How to Evaluate Predictive Contribution Without Circular Advantage

To evaluate F1–F5 without rewarding them for merely re-detecting the `onset_candidate` gate:

1. **Use `verified_forward` as the Primary Point-in-Time Target (`instant_targets.py`, line 246):** Because `verified_forward` depends strictly on the forward interval `(anchor, anchor + H]` and causal `Baseline` ($\sigma_{1\text{m}}, \beta$), it has zero algebraic overlap with pre-anchor velocity (`current_velocity`) or 30s activity (`recent_trades`, `pace`).


2. **Condition Post-Crossing Evaluations on `onset_candidate == True` with Gate Inputs in the Null Baseline:** When evaluating whether F1–F5 separate true onsets (`verified_onset == True`) from false threshold crossings (`onset_candidate == True` but `verified_onset == False`), restrict the sample to `onset_candidate == True` and include `velocity_sigma`, `previous_velocity_sigma`, `pace_multiple`, and `recent_trade_count` (`instant_targets.py`, lines 330–333) in the baseline model. F1 and F2 then only receive credit for information *beyond* the gate (specifically, the preceding 150s baseline context in F1 and the signed `TakerImb` directionality in F2).


3. **Evaluate Lead-Time Discovery Strictly at `publish_ts_ms < anchor` (`pre_onset_prediction`):** When grading against `event_catalog()`, evaluate F1–F5 strictly at timestamps `[anchor - 180s, anchor - 5s]` before `current_velocity >= 1.0` and `pace > 2.0` have simultaneously triggered.



---

## 4. Candidate Mechanism Assessment (F1–F5)

### Standalone vs. Conditional Contribution & Structural Controls

Per `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Sections 4–6):

* **Standalone vs. Marginal Value:** Every feature must be tested standalone (controlling for $\sigma_{1\text{m}}$, `spread_bps`, and liquidity) and via **leave-one-out ablation** from the full five-feature directional model `(F1, F2, F3, F4, F5)`. Because Section 4 defines the smoothed state `S_i,h,j` using market-relative log-return increments `x_i,j` for both `h = 30s` and `h = 180s`, F1 (midpoint acceleration) and F5 (market-relative residual) must be checked for collinearity so F1 measures strictly the *rate-of-change difference* (30s vs. prior 150s) while F5 measures the *market-relative displacement level*.


* **Full Eligible Universe Coverage:** All causally eligible products and 5s grid times—including quiet coins that never enter Top-$K$ (`K=5, 10`) boards (`test_zero_move_is_a_complete_negative_and_is_retained_outside_boards`, `tests/test_instant_targets.py`, lines 381–386)—must remain in the evaluation panel.


* **Liquidity, Market-Wide Moves, and Dependent Observations:** Stratify by trailing 24h USD volume and entry `spread_bps`. Because 5s grid evaluations overlap across 300s/900s horizons and share market-wide shocks within a day, all uncertainty intervals must use the **paired UTC-day block bootstrap** (`LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md`, Section 6), keeping all products, boards, and rankers together within each sampled UTC day.



### F1–F5 Mechanism Evaluation Table

| Feature | Precise Hypothesis | Expected Behavior (Up vs. Down) | Timing Relative to Onset | Appropriate Baseline / Ablation | Supporting Evidence | Rejecting Evidence | Inconclusive Evidence | Data-Quality Checks & Major Confounders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **F1: Midpoint Acceleration** | Positive convexity between the non-overlapping 30s midpoint return and preceding 150s midpoint return (scaled by causal $\sigma_{1\text{m}}(t_0)$ with `0.0015` floor) predicts 5m/15m `verified_forward` continuation better than steady 180s drift.

 | **Up (`d=+1`):** Signed 30s return rate exceeds preceding 150s return rate.<br>

<br>**Down (`d=-1`):** Signed downward 30s return rate exceeds preceding 150s downward rate.

 | **Late pre-onset (`[anchor-30s, anchor)`) and at `anchor`:** Captures the transition from the 150s baseline into the 30s impulse.

 | **Baseline:** 30s velocity (`velocity_sigma`) + F5 market residual.<br>

<br>**Ablation:** Full `[F1..F5]` model minus `F1` evaluated on `verified_forward` and conditional on `onset_candidate == True`.

 | Statistically significant reduction in out-of-sample log-loss and gain in Top-5/Top-10 `verified_forward` precision over F5 + F2 across paired UTC-day bootstrap blocks.

 | High 30s-vs-150s acceleration predicts transient blow-off wicks that fail `minimum_peak_retention` (`0.60`, `test_large_wick_with_good_terminal_magnitude_fails_retention`).

 | Standalone association with `verified_onset` is positive (due to circularity with `velocity_crossing_sigma`), but marginal lift on `verified_forward` after controlling for F2 and F5 spans zero across the 7 validation day-blocks.

 | **Checks:** Require `price_source == "mid"`, non-crossed BBO, quote age $\le 10\text{s}$ at `b`, `b-30s`, `b-180s`, continuous coverage, and $\ge 1$ live match; exclude `last_trade_fallback`.

<br>

<br>**Confounders:** `EXTENDED` coins (`E > 3.5`) accelerating into exhaustion; wide-spread midpoint jumps.

 |
| **F2: Match-Derived Signed Participation & Pace** | Aggressive order-flow imbalance (`TakerImb * log(1 + PaceRatio)` using maker-side-inverted `matches` USD volume, gated on $\ge 5$ matches in 30s) detects informed liquidity consumption that precedes and sustains 5m/15m breakouts.

 | **Up (`d=+1`):** `taker_buy_usd > taker_sell_usd` (`TakerImb > 0`) with elevated `PaceRatio`.<br>

<br>**Down (`d=-1`):** `taker_sell_usd > taker_buy_usd` (`TakerImb < 0`) with elevated `PaceRatio`.

 | **Both before onset (`[anchor-180s, anchor)`) and at `anchor`:** Taker sweeps absorb resting limit orders before midpoint reprices and confirm participation at onset.

 | **Baseline:** Unsigned `pace_multiple` and `recent_trade_count` (`instant_targets.py`, lines 303–311) + F1.<br>

<br>**Ablation:** `[F1..F5]` minus `TakerImb` sign, and `[F1..F5]` minus `F2` entirely.

 | Signed `TakerImb` increases `pre_onset_prediction` lead recall (`publish_ts_ms < anchor`) and lifts conditional `verified_forward` precision among `onset_candidate` rows above unsigned `pace_multiple`.

 | Signed taker flow adds zero marginal lift over unsigned pace, or heavy one-sided taker bursts mark local exhaustion absorbed by passive iceberg liquidity that fails 5m/15m retention. | Step 2.5 feed audit remains unverified on thin products (`INSTANT_TARGET_LABELS_20261029.md` notes ALCX/AURORA had only 4 and 3 paired trades), or 7-day validation block intervals span zero.

 | **Checks:** Deduplicate `(product_id, trade_id)`; exclude initial `last_match` watermark; withhold F2 on unknown maker side or unreconciled match gaps.

<br>

<br>**Confounders:** Thin products excluded by the `< 5` match gate; wash trading; passive iceberg replenishment.

 |
| **F3: Sampled BBO Pressure & Spread** | Time-weighted L1 order-book imbalance (from verified `ticker` BBO sizes) combined with narrow relative spread (`spread_bps`) indicates directional queue support and low friction to clear the $3 \times \text{entry\_spread}$ target barrier.

 | **Up (`d=+1`):** Time-averaged bid size > ask size (`OBI > 0`) with tight/stable `spread_bps`.<br>

<br>**Down (`d=-1`):** Time-averaged ask size > bid size (`OBI < 0`) with tight/stable `spread_bps`.

 | **Before onset (`t < anchor`)** for queuing pressure; **at `anchor**` as a spread/feasibility filter (since `required_terminal_log` requires $\ge 3 \times \text{entry\_spread}$, `instant_targets.py`, line 232).

 | **Baseline:** Entry `spread_bps` alone + F2 signed flow.<br>

<br>**Ablation:** `[F1..F5]` minus `F3` (and separating BBO size imbalance from `spread_bps`).

 | Time-weighted BBO imbalance improves `pre_onset_prediction` detection or filters out illiquid air-pocket spikes that fail net-of-cost return (`cost_scenarios` in `instant_targets.py`, lines 256–261).

 | Visible L1 size imbalance is contrarian (spoofing or passive supply/demand walls opposing the move) or adds zero predictive lift once `spread_bps` and F2 are included. | Sampled `ticker` batching misses sub-5s book updates between trades, leaving F3 noisy with paired UTC-day block confidence intervals overlapping zero.

 | **Checks:** Reconstruct empty healthy buckets with original `quote_ts_ms`; mark durations with quote age $> 10\text{s}$ unavailable; reject crossed books (`ask < bid`).

<br>

<br>**Confounders:** L1-only visibility hiding L2 depth; `ticker` update batching.

 |
| **F4: Compression Followed by Expansion** | Breakouts launching from an actively traded, low-volatility 15m compression regime ($\ge 10$ traded closed 1m candles in prior 15 completed minutes) into a 30s expansion achieve higher 5m/15m retention than moves in already-choppy books.

 | **Symmetric regime amplifier** interacting with directional sign $d \in \{+1, -1\}$: Low prior 15m volatility/range followed by +30s expansion (Up) or -30s expansion (Down).

 | **Pre-onset setup (`t < anchor`)** establishes compression; **inflection near `anchor**` marks expansion.

 | **Baseline:** 60m causal $\sigma_{1\text{m}}$ + F1 acceleration without prior 15m compression conditioning.<br>

<br>**Ablation:** `[F1..F5]` minus `F4`.

 | Conditioning on prior 15m compression (with $\ge 10$ traded candles) increases 5m/15m `retention` and `verified_forward` rate compared to unconditioned F1/F2 spikes.

 | Prior compression provides zero lift or selects stagnant/low-beta products that fail the absolute `0.015` (1.5%) minimum terminal log-return floor (`instant_targets.py`, line 231).

 | Apparent lift in discovery disappears after enforcing the $\ge 10$ traded-candles activity gate or has wide day-block bootstrap intervals spanning zero.

 | **Checks:** Require closed 1m candles available $\le t_0$ and $\ge 10$ traded candles in prior 15m so feed outages or dead books never masquerade as compression.

<br>

<br>**Confounders:** Diurnal quiet sessions; `sigma_floor_1m` (`0.0015`) masking variation in ultra-quiet coins.

 |
| **F5: Market-Relative Movement** | Idiosyncratic coin movement net of synchronous causal BTC return ($r_{\text{coin}} - \beta r_{\text{BTC}}$, scaled by $\sigma_{1\text{m}}$) isolates coin-specific catalysts that persist over 5m/15m and suppresses false alerts during BTC beta sweeps.

 | **Up (`d=+1`):** Positive market-relative residual ($r_{\text{coin}} - \beta r_{\text{BTC}} > 0$).<br>

<br>**Down (`d=-1`):** Negative market-relative residual ($r_{\text{coin}} - \beta r_{\text{BTC}} < 0$).

 | **Both before onset** (diverging from BTC during market moves) **and at `anchor**` (filtering out market-wide beta cascades).

 | **Baseline:** Raw unadjusted percentage-move ranker + `beta_fallback` indicator.<br>

<br>**Ablation:** `[F1..F5]` with F5 vs. replacing F5 with raw unadjusted coin return.

 | Beats the raw percentage-move ranker on `verified_forward` Top-$K$ precision and cuts false alerts/hour during volatile BTC blocks (`test_market_move_is_not_an_idiosyncratic_impulse`).

 | Market-relative adjustment degrades net-of-cost coin returns (`gross_coin_return_bps` minus spread/fees) because lagged altcoin beta continuation dominates idiosyncratic moves. | BTC movement is subdued during the 7 validation days ($\log(\text{BTC}_t/\text{BTC}_0) \approx 0$), making F5 nearly collinear with raw coin return and F1.

 | **Checks:** Require both coin and BTC `quote_ts_ms` within `10000ms` of cutoff and `btc_price_source == "mid"`; track `beta_fallback == True` separately.

<br>

<br>**Confounders:** `beta = 1.0` fallback mis-scaling low/high-beta alts; lead-lag delay where alts react 10s–60s after BTC.

 |

---

## 5. Final Verdict, Ranked Corrections, and Remaining Frozen Definitions

### Verdict on Target Alignment

**`verified_forward` Matches the Intended Task; `verified_onset`, `alert_timing`, and `event_catalog` Contain Three Confirmed Measurement Defects.**

1. **What Matches:** `TargetEvaluator` in `scripts/scoring_experiment/instant_targets.py` faithfully enforces the prospective contract's causal boundaries (`available_ts_ms <= ts`, `max_quote_age_ms <= 10000`, `price_source == "mid"`), fixed 30s/180s input vs. 300s/900s outcome windows, direction symmetry, and strict `pending`/`unavailable` handling. The unconditional `verified_forward` label (`instant_targets.py`, lines 219–263) accurately measures sustained, market-relative 5m/15m moves across all eligible coins (including non-board and zero-move rows).


2. **What Distorts Measurement:**
* **Confirmed Defect 1 — Post-Anchor Origin Reset in `alert_timing()` (`instant_targets.py`, lines 371–373):** Measuring `consumed_fraction` strictly from `anchor` (`self._residual(anchor, ts, ...) / label["peak_residual_log"]`) forces `consumed_fraction == 0.0` at `publish_ts_ms == anchor`, ignoring the $\ge 0.707\sigma_{1\text{m}}$ displacement that already occurred during `[anchor - 30s, anchor]` to trip `current_velocity >= 1.0`.


* **Confirmed Defect 2 — Catalog & Alert-Timing Blindness to `verified_forward`-Only Moves (`instant_targets.py`, lines 346–350, 398–424):** `event_catalog()` drops every genuine 5m/15m impulse where `verified_forward == True` but `verified_onset == False`, and `alert_timing()` raises a `ValueError` on those labels.


* **Confirmed Defect 3 — Post-Sweep Zero-Tolerance `no_retrace` (`instant_targets.py`, line 327; `INSTANT_TARGET_CONTRACT_V1.json`, line 22):** Enforcing `adverse >= -1e-12` relative to the post-burst `anchor` price across 60 to 180 5s grid points rejects genuine sustained breakouts (`verified_forward == True`) whenever a 1-tick spread bounce or BTC tick occurs right after the 30s onset sweep.





---

### Ranked Corrections Needed Before Prospective Outcome Analysis

1. **[Confirmed Defect Fix] Build a `verified_forward` Event Catalog and Allow `alert_timing()` to Grade Forward Events (`scripts/scoring_experiment/instant_targets.py`, `alert_timing` lines 346–350, `event_catalog` lines 398–424):**
* *Measurement Problem Fixed:* Currently, any real 5m/15m move (`verified_forward == True`) that does not satisfy all four `verified_onset` sub-rules is invisible to `event_catalog()` and rejected by `alert_timing()`. Adding a parallel `forward_event_catalog` (or parameterizing `event_catalog(labels, key="verified_forward")`) and using `verified_forward` as the primary point-in-time target eliminates F1/F2/F5 label circularity and ensures missed-move and false-alert denominators account for all real horizon moves.




2. **[Confirmed Defect Fix] Measure `consumed_fraction` (and Optional Breakout Reference) from the Pre-Onset Window Start `anchor - velocity_ms` (`scripts/scoring_experiment/instant_targets.py`, `evaluate` line 220, `alert_timing` lines 371–373):**
* *Measurement Problem Fixed:* Anchoring `consumed_fraction` at `anchor - 30s` (the start of the 30s velocity crossing window) instead of `anchor` stops `alert_timing()` from reporting `0.0` consumed fraction when an alert fires at `anchor` after the 30s onset surge has already happened.




3. **[Confirmed Defect Fix] Anchor `no_retrace` to the Pre-Crossing Baseline (`anchor - 30s`) or Apply a Spread/Sigma Adverse Tolerance (`scripts/scoring_experiment/instant_targets.py`, line 327; `docs/research/INSTANT_TARGET_CONTRACT_V1.json`, line 22):**
* *Measurement Problem Fixed:* Prevents a 1-tick BBO mean-reversion or 1-tick BTC move at `anchor + 5s` (immediately after a `pace > 2.0` aggressive sweep) from setting `no_retrace = False` and disqualifying a sustained 5m/15m `verified_forward` trend.




4. **[Design / Code Hardening] Make LF Normalization Explicit in `load_contract()` (`scripts/scoring_experiment/instant_targets.py`, lines 22–24):**
* *Measurement Problem Fixed:* Changing `CONTRACT_PATH.read_text(encoding="utf-8").encode("utf-8")` to explicitly normalize `.replace("\r\n", "\n")` (or reading bytes and normalizing CRLF to LF) guarantees the `sha256_utf8_lf_normalized_contract_file` contract invariant even if file-reading helpers change.





---

### Remaining Definitions That Must Be Frozen Before Collection or Fitting

In accordance with `remaining_study_gates` in `docs/research/INSTANT_TARGET_CONTRACT_V1.json` (lines 49–55) and `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (Sections 2–6), the following specifications must be frozen before setting `"fitting_allowed": true`:

1. **Step 2.5 All-Product Feed Side & Coverage Audit Completion:** Resolve the sparse-trade coverage audit on thin USD products (`INSTANT_TARGET_LABELS_20261029.md` notes ALCX/AURORA had only 4 and 3 paired trades in the 1-hour capture, leaving the all-product gate `false`).


2. **Exact Mathematical Formulas for F1–F5 & F1/F5 Separation:** Freeze the exact boxcar vs. decayed-sum (`S_i,h,j`) equations for each of F1–F5, including whether F1 uses raw midpoint log returns or market-residual increments `x_i,j`, and the exact L1 time-weighting and staleness mask for F3.


3. **Live Stage Numeric Cutoffs (`IGNITING`, `CONFIRMED`, `FADING/ABSORBED`):** Freeze the exact live thresholds separating `IGNITING`, `CONFIRMED`, and `FADING/ABSORBED` downstream of the hard `EXTENDED` gate (`E > 3.5` or `abs(r_24h) > 10%` with trailing 24h volume `< $1M`).


4. **Multi-Event Alert Association & Operational Denominators:** Freeze the protocol for associating a single published alert (`t_alert`) when multiple events overlap across 5m/15m horizons or when `verified_forward == True` and `verified_onset == False`, alongside exact denominators for `false_alerts_per_hour` and `missed_move_rate`.


5. **Discovery Sample-Size Readiness Minima:** Freeze the minimum number of deduplicated discovery episodes per direction (`up`, `down`) and horizon (`300s`, `900s`) required across Days 1–7 before fitting the two five-weight directional models.
