**Source Inspection & Availability Confirmation**
All eight complete file sections in the V2 source packet (snapshot `cc3b6a64e7db96f55a6008a8f387b97d5468763f`, implementation `8b5b26614de74459000ae29d39d71abe34567007`) were readable and directly inspected alongside the 2026-10-30 review-acceptance handoff (`1da6f4e` / Black-formatted `92fb51d`):

1. `docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md` (SHA-256 `b43b781f626790097bfa2da5cdfa64db16a3ab1b143622b40a229301dae4a442`)
2. `docs/research/INSTANT_TARGET_CONTRACT_V1.json` (SHA-256 `35d9b8a286d051aff08148a2af9987b379d65e92d57c3bea76112be52cfca7a4`)
3. `docs/research/INSTANT_TARGET_CONTRACT_V2_DRAFT.json` (SHA-256 `d1700f552868ceda7ed825af98b3db7d07a5d4e6b2f523733f271d585ca8c0d3`)
4. `docs/research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md` (SHA-256 `f1634d6de38a483a075ae4b3f8b7102cc87d0782ba10ae16b1a945b6ed1446a9`)
5. `scripts/scoring_experiment/instant_targets.py` (SHA-256 `53cd1776be9b1b830fe5b2a7b45d6febba2ec725688ed7f4e2bcc798d8edc810` at `8b5b266`; subsequently patched at `92fb51d` to reject V1 labels in `forward_event_catalog`)
6. `tests/test_instant_targets.py` (SHA-256 `e602c8930bd9226588a0b248be32d4a0550b83638ab79635d12921a087c613ff`)
7. `tests/test_instant_targets_v2.py` (SHA-256 `2f0ab6f9ae35b5397bd644f1eb4185f0d809f5f3e7db303e5528c98ed8b8866e`)
8. `docs/research/results/instant_target_review_20261030/REPRODUCTIONS.json` (SHA-256 `ad6889f26e9a68987fa5f7ef8646556818d9d03a86b67c12c9913dc1fca64d31`)

**Scope & Original-Proposal Limitation:**
The original unamended proposal is absent from this conversation and packet. Accordingly, this review evaluates consistency strictly against the corrected prospective proposal (`docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md`) and makes no claim of fidelity to the unamended original text.

---

## 1. V2 Target Architecture & Resolution of V1 Limitations

### 1. Primary `verified_forward` Target vs. Secondary `verified_onset` Diagnostic

In `INSTANT_TARGET_CONTRACT_V2_DRAFT.json` (`targets.primary_pointwise: "verified_forward"`) and `TargetEvaluator.evaluate()` (`scripts/scoring_experiment/instant_targets.py`), every causally eligible 5s grid point across all products (including non-board and zero-move rows) receives a complete `verified_forward` evaluation without requiring the 30s velocity crossing (`velocity_crossing_sigma: 1.0`), 30s match pace (`> 2.0`), 180s breakout deadline, or `no_retrace` gate.

* **What This Resolves:** In V1, using `verified_onset` as the primary target coupled the label to 30s velocity and activity thresholds. Making `verified_forward` the primary pointwise target decouples the outcome label `(anchor, anchor + H]` from the pre-anchor 30s trigger window, while retaining `verified_onset` and `onset_candidate` strictly for secondary attrition and gate-conditioned continuation analysis.
* **Remaining Selection / Shared-Control Nuance:** As correctly noted in `INSTANT_TARGET_REVIEW_TRIAGE_20261030.md`, `verified_forward` still shares causal scale parameters (`sigma_1m`, `beta`, and entry `spread_bps` in `required_terminal_log`) with the candidate features. Evaluation must therefore stratify or control for baseline volatility, spread, and `beta_fallback` regimes rather than assuming `verified_forward` is statistically independent of feature scaling.

### 2. Separate `forward_event_catalog` and Explicit Absence of Physical Onset

`forward_event_catalog(labels)` (`instant_targets.py`) deduplicates `verified_forward == True` episodes over `[anchor, anchor + H)` per `(product_id, direction, horizon_seconds)` and stamps `"catalog_kind": "forward_window_not_physical_impulse"`.

* **What This Resolves:** As proven in `test_forward_catalog_retains_real_moves_with_small_retracement` (`tests/test_instant_targets_v2.py`) and `REPRODUCTIONS.json` (`one_bps_adverse_dip`), a 1 bp adverse dip at `ANCHOR + 5000` sets `verified_onset = False` and leaves `event_catalog([label])` empty, whereas `forward_event_catalog([label])` retains the episode.
* **Why Forward-Window Anchors Are Not Physical Onset (Hidden Timing Shift):** Neither a `forward_event_catalog` anchor nor `anchor - 30s` (`pre_window_reference_ts_ms`) represents the physical initiation of a move (`physical_onset_defined: False`). Furthermore, because `forward_event_catalog` selects the **earliest** 5s grid `anchor` whose `[anchor, anchor + H]` window satisfies `terminal >= threshold` and `retention >= 0.6`, a sharp 30-second impulse that starts at $t_{\text{phys}}$ will often qualify in `forward_event_catalog` at an earliest anchor $t_{\text{cat}} \approx t_{\text{phys}} - H + 30\text{s}$ (up to 4.5 minutes *before* the physical move on a 300s horizon, or 14.5 minutes early on a 900s horizon, provided price was flat during $[t_{\text{cat}}, t_{\text{phys}}]$). `forward_alert_timing()` properly avoids calling `publish_ts_ms < anchor` "pre-onset prediction," labeling it `"before_forward_window_anchor"` instead.

### 3. Named Pre-Window (`anchor - 30s`) and Post-Anchor Consumed Fractions

In `TargetEvaluator._v2_alert_timing()` (`instant_targets.py`), the unqualified `consumed_fraction` key is removed (`unqualified_consumed_fraction_allowed: false`) and replaced by two named metrics:

* `post_anchor_consumed_fraction`: `self._residual(anchor, ts, beta, sign) / peak_residual_log`
* `pre_window_consumed_fraction`: `self._residual(anchor - 30000, ts, beta, sign) / pre_window_peak_residual_log`, where `pre_window_peak_residual_log` is the maximum residual from `anchor - 30000` across `[anchor - 30000, anchor + H]`.
* **What This Resolves:** At `publish_ts_ms = ANCHOR` on the standard synthetic ramp (`REPRODUCTIONS.json`), V2 reports both `post_anchor_consumed_fraction = 0.0` and `pre_window_consumed_fraction = 0.002 / 0.022 = 0.090909...` (9.09%), while explicitly flagging `pre_window_reference_is_physical_origin: False`.

---

## 2. Code Defects vs. Design Choices (S1–S3) & Unsupported Claims

### Confirmed Code Defect in `8b5b266` (Already Patched in `1da6f4e` / `92fb51d`)

* **Path & Function:** `scripts/scoring_experiment/instant_targets.py` $\rightarrow$ `forward_event_catalog(labels)`
* **Defect & Counterexample in `8b5b266`:** In `8b5b266`, `forward_event_catalog(labels)` delegates directly to `event_catalog(labels, target="verified_forward")` without checking `row.get("contract_version") == "instant-target-v2-draft"` or `row.get("evaluator_sha256")` presence. Passing a V1 label (`label = TargetEvaluator(samples()).evaluate(ANCHOR, baseline(), "up", 300, ANCHOR + 300000)`) into `forward_event_catalog([label])` returns a catalog entry stamped `"catalog_kind": "forward_window_not_physical_impulse"`, which subsequently crashes in `forward_alert_timing()` with `ValueError`.
* **Status:** Already fixed and verified in `1da6f4e` / `92fb51d` per the review-acceptance handoff. Do not re-open.

### Additional Edge-Case Defect Demonstrated in `8b5b266` / `92fb51d`: Strict-Trigger Timing Reference Peak Mismatch (Coupled to S1)

* **Path & Function:** `scripts/scoring_experiment/instant_targets.py` $\rightarrow$ `TargetEvaluator._v2_alert_timing(self, label, publish_ts_ms, strict_trigger=True)`
* **Mechanism & Numerical Counterexample:**
When `strict_trigger=True` (via `engine.alert_timing(label, publish_ts_ms)` in V2), `early` is evaluated as:
```python
early = (
    publish_ts_ms <= label["pre_window_peak_ts_ms"]
    and fraction
    < self.cfg["events"]["early_detection_consumed_fraction_strictly_below"]
    - self.cfg["comparison_tolerance"]
)

```


Consider the exact path in `test_pre_window_peak_includes_the_pre_trigger_path` (`tests/test_instant_targets_v2.py`), modified so `onset_candidate` and `verified_onset` are `True` at `ANCHOR = 3_780_000`:
* At `ts = ANCHOR - 30_000` (`3_750_000`), residual move is `0.0`.
* At `ts = ANCHOR - 10_000` (`3_770_000`), a pre-trigger wick reaches log residual `+0.04` (`price = 100 * exp(0.04)`).
* At `ts = ANCHOR - 5_000` (`3_775_000`), residual settles to `+0.0005` (so `previous_velocity` over `[3_745_000, 3_775_000]` is $0.0005 / (0.0015/\sqrt{2}) = 0.4714 < 1.0$).
* At `ts = ANCHOR` (`3_780_000`), residual steps to `+0.002` (so `current_velocity` over `[3_750_000, 3_780_000]` is $0.002 / (0.0015/\sqrt{2}) = 1.8856 \ge 1.0$), and from `ANCHOR` to `ANCHOR + 300_000` it ramps monotonically from `+0.002` to `+0.022` (`terminal_residual_log = 0.02`, `peak_ts_ms = ANCHOR + 300_000`).
* Here, `verified_onset` is **`True`**. However, across `[ANCHOR - 30_000, ANCHOR + 300_000]`, the maximum residual relative to `ANCHOR - 30_000` is the pre-trigger wick at `pre_window_peak_ts_ms = ANCHOR - 10_000` (`0.04` > `0.022`).
* When `engine.alert_timing(label, ANCHOR)` is called for an alert published **at the exact trigger `ANCHOR**`, `publish_ts_ms <= label["pre_window_peak_ts_ms"]` evaluates `3_780_000 <= 3_770_000` $\rightarrow$ **`False`**, and `lead_to_pre_window_peak_seconds` is **`-10.0`**, classifying an alert at the trigger with only $0.002 / 0.04 = 5\%$ (or $8.9\%$ in Codex's S1 probe) of the move consumed as **`"late_after_activity_trigger"`**.


* **Resolution for Freeze Candidate (Addressing S1, S2, S3):**
1. **S1 Decision (Peak Search Interval for `pre_window`):** Keep `pre_window_reference_ts_ms = anchor - 30_000` as the **price baseline** for the numerator `self._residual(anchor - 30_000, ts, beta, sign)`, but restrict the peak timestamp and denominator search to the **post-anchor forward horizon `[anchor, anchor + H]**` (so `pre_window_peak_ts_ms == peak_ts_ms`, and `pre_window_peak_residual_log = self._residual(anchor - 30_000, peak_ts_ms, beta, sign)`). This measures the exact fraction of the *forward event's peak* already consumed since `anchor - 30s` without letting a transient pre-trigger wick at `anchor - 10s` invert `publish_ts_ms <= peak_ts_ms` and misclassify every post-trigger alert as late.
2. **S2 Decision (`sigma` vs. `pace` Cutoff Alignment):** Retain the current V2 distinction (`sigma` ending at `floor((anchor - 35_000) / 60_000) * 60_000` and 30s `pace` ending at `anchor - 30_000`). Both are strictly causal at `anchor`; `sigma_1m` is constrained by closed 1-minute candle boundaries whereas 30s `pace` operates on 5s micro-bars and must immediately precede the `[anchor - 30s, anchor)` window.
3. **S3 Decision (Explicit Reason for Null `pre_window_consumed_fraction`):** Add `"pre_window_consumed_fraction_reason"` to `_v2_alert_timing()` output, set to `label.get("pre_window_reference_reason")` when `pre_window_reference_status != "ready"`, `"nonpositive_pre_window_peak"` when `reference_peak <= 0` (as in `test_reference_may_have_no_positive_peak_for_an_independent_forward_move`), and `None` when populated.



---

## 3. F1–F5 Candidate Mechanism Review (Under V2 Target Architecture)

Per `INSTANT_TARGET_REVIEW_TRIAGE_20261030.md` and `INSTANT_TARGET_CONTRACT_V2_DRAFT.json`:

* **No Overstated Algebraic Guarantees:** As demonstrated in `test_crossing_does_not_algebraically_force_positive_F1_acceleration` (`fast = 0.002`, `prior / 5 = 0.0024`, acceleration `= -0.0004 < 0`) and `test_trade_count_pace_can_trigger_while_volume_pace_is_below_two` (`pace_multiple = 3` via trade count while USD volume pace is `60 / 100 = 0.6 < 2`), `onset_candidate` does not algebraically guarantee positive F1 or volume-pace $> 2$. Nevertheless, gate contamination still exists whenever predictors and triggers share inputs, which is why primary evaluation uses `verified_forward` and gate-conditioned continuation includes the gate inputs (`velocity_sigma`, `previous_velocity_sigma`, `pace_multiple`, `recent_trade_count`) in the null comparator.
* **Metric & Inference Discipline:** Any probability metric (such as log-loss or Brier score) requires a separately declared probabilistic calibration model; ordinal `score_0_100` rankings alone must be evaluated via rank/top-$K$ hit rates and matched-coverage precision, not uncalibrated log-loss. A paired UTC-day block bootstrap confidence interval spanning zero is **inconclusive** (insufficient power/regimes over 7 validation days), never proof of zero effect.

| Feature | Testable Hypothesis | Expected Direction (Up vs. Down) | Pre-Trigger vs. Post-Trigger Role | Comparator / Ablation | Supporting Evidence | Rejecting Evidence | What Stays Inconclusive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F1: Midpoint Acceleration** | Comparing the 30s midpoint return rate against the preceding non-overlapping 150s return rate (scaled by causal $\sigma_{1\text{m}}$ ending at $\lfloor(\text{anchor}-35\text{s})/60\text{s}\rfloor$) provides incremental prediction of 5m/15m `verified_forward` impulses beyond current 30s velocity and F5. | **Up (`d=+1`):** $r_{30\text{s}} - (r_{\text{prior }150\text{s}}/5) > 0$.<br>

<br>**Down (`d=-1`):** $-r_{30\text{s}} - (-r_{\text{prior }150\text{s}}/5) > 0$. | **Pre-trigger (`publish_ts_ms < anchor`):** Detects early convex turn before `velocity_sigma >= 1.0`.<br>

<br>**Post-trigger (`onset_candidate == True`):** Tests whether convex ramp-ups continue better than decelerating crossings (like `F1_counterexample`). | **Comparator:** Current 30s velocity (`velocity_sigma`) + F5 market residual.<br>

<br>**Ablation:** Full 5-feature model minus F1 on all-grid `verified_forward` and within `onset_candidate == True`. | Positive incremental lift in Top-$K$ (`K=5, 10`) `verified_forward` hit rate (at matched coverage/false-alert burden) and probabilistic log-loss (if a calibrated probability mapping is declared) across paired UTC-day blocks. | Statistically robust negative incremental lift (convex 30s spikes mean-reverting below the 0.60 retention threshold more often than steady 180s ramps). | Paired UTC-day block interval spans zero, or high collinearity with F5/velocity under limited discovery episodes prevents separating 30s-vs-150s convexity from 30s level. |
| **F2: Match-Derived Signed Participation & Pace** | Signed taker imbalance (`TakerImb * log(1 + PaceRatio)` from deduplicated `matches` with maker-side inversion, gated on $\ge 5$ matches in 30s) predicts 5m/15m `verified_forward` continuation better than unsigned trade count or volume pace alone. | **Up (`d=+1`):** `taker_buy_usd > taker_sell_usd` (`TakerImb > 0`) with elevated `PaceRatio`.<br>

<br>**Down (`d=-1`):** `taker_sell_usd > taker_buy_usd` (`TakerImb < 0`) with elevated `PaceRatio`. | **Pre-trigger:** Detects one-sided liquidity absorption before midpoint crosses $1.0\sigma$.<br>

<br>**Post-trigger:** Separates buy-driven vs. sell-driven activity crossings (since `onset_candidate` uses unsigned `recent_trades` and `pace`). | **Comparator:** Unsigned `pace_multiple` and `recent_trade_count` + F1/F5.<br>

<br>**Ablation:** Replace signed `TakerImb` with $+1$ (unsigned pace only), and drop F2 from `[F1..F5]`. | Signed `TakerImb` improves Top-$K$ `verified_forward` precision and gate-conditioned continuation (`verified_forward | onset_candidate`) over unsigned `pace_multiple`. | Unsigned pace/count explains all predictive lift, or heavy one-sided taker flow predicts post-sweep exhaustion (`retention < 0.60`). |
| **F3: Sampled BBO Pressure & Spread** | Observation-age-aware, time-weighted L1 order-book size imbalance from verified `ticker` quotes adds directional predictive value for `verified_forward` beyond entry `spread_bps` feasibility and F2 match flow. | **Up (`d=+1`):** Time-weighted L1 bid size > ask size with narrow/stable `spread_bps`.<br>

<br>**Down (`d=-1`):** Time-weighted L1 ask size > bid size with narrow/stable `spread_bps`. | **Pre-trigger:** Captures passive L1 queue buildup before trades execute.<br>

<br>**Post-trigger:** Filters out wide-spread air pockets that fail `3 * entry_spread_fraction` or net-of-cost bps scenarios. | **Comparator:** Entry `spread_bps` alone (which directly enters `required_terminal_log`) + F2.<br>

<br>**Ablation:** Separate L1 size imbalance from `spread_bps`; drop L1 size imbalance from `[F1..F5]`. | L1 size imbalance adds incremental Top-$K$ precision or pre-trigger recall after controlling for entry `spread_bps` and F2. | All apparent F3 value comes solely from tight `spread_bps` lowering `required_terminal_log`, or visible L1 size imbalance is contrarian (passive walls/spoofing blocking continuation). | Sampled `ticker` batching misses intra-5s L1 queue changes, or paired UTC-day block confidence intervals span zero. |
| **F4: Compression Followed by Expansion** | Moves launching from an active, low-dispersion prior 15m candle regime ($\ge 10$ traded closed 1m candles available $\le t_0$) into a 30s expansion achieve higher `verified_forward` follow-through and retention than moves from already-volatile regimes. | **Direction-symmetric regime modifier** interacting with sign $d \in \{+1, -1\}$: Low prior 15m volatility/range followed by directional 30s expansion. | **Pre-trigger:** Identifies coiled active consolidation before expansion.<br>

<br>**Post-trigger:** Conditions continuation probability of a 30s velocity crossing on prior 15m quietness. | **Comparator:** 60m causal `sigma_1m` + F1 acceleration without prior 15m compression conditioning.<br>

<br>**Ablation:** Full `[F1..F5]` model minus F4. | Active prior 15m compression increases `verified_forward` hit rate and 5m/15m `retention` beyond baseline `sigma_1m` and F1. | Compression adds negative or zero incremental value over F1 (e.g., selecting low-volatility coins that fail the absolute `0.015` log-return floor). | Few qualifying compression-to-expansion episodes occur within the 7-day validation window, or lift vanishes once dead-book/outage intervals are masked via the $\ge 10$ traded-candles rule. |
| **F5: Market-Relative Movement** | Causal BTC-beta-adjusted coin return ($r_{\text{coin}} - \beta r_{\text{BTC}}$, scaled by $\sigma_{1\text{m}}$) improves cross-sectional `verified_forward` selection and net-of-cost coin returns over raw unadjusted coin returns. | **Up (`d=+1`):** Positive market-relative residual.<br>

<br>**Down (`d=-1`):** Negative market-relative residual. | **Pre-trigger:** Detects idiosyncratic divergence during BTC moves.<br>

<br>**Post-trigger:** Prevents market-wide BTC volatility shocks from flooding the Top-$K$ board with passive beta movers. | **Comparator:** Raw percentage-move ranker (`gross_coin_return_bps` basis) + `beta_fallback` stratification.<br>

<br>**Ablation:** Replace market-relative residual in `[F1..F5]` with raw coin log return. | Market-relative F5 outperforms the raw percentage-move ranker on both `verified_forward` precision and net-of-cost simple returns (`cost_scenarios`) across paired UTC-day blocks. | Beta subtraction degrades executable net-of-cost coin returns (`net_coin_return_bps`) even while fitting the residual-defined `verified_forward` target. | Subdued BTC movement during the 7-day validation period leaves $r_{\text{coin}} - \beta r_{\text{BTC}} \approx r_{\text{coin}}$, or high `beta_fallback == True` rates obscure true beta adjustment. |

---

## 4. Consolidated Freeze Candidate & Remaining Study Gates

### Consolidated V2 Target Freeze Candidate (Resolving S1, S2, S3)

To close the target-definition loop before moving to the remaining study gates, freeze `INSTANT_TARGET_CONTRACT_V2.json` and `instant_targets.py` with the following exact specification:

1. **Keep `92fb51d` V2 Contract & Provenance Guardrails:** `verified_forward` is the primary pointwise target; `forward_event_catalog` rejects V1 labels and mixed `evaluator_sha256` hashes; `verified_onset` is a secondary diagnostic only.
2. **Freeze S1 (Pre-Window Peak Search Window):** In `TargetEvaluator.evaluate()`, compute `pre_window_peak_ts_ms` and `pre_window_peak_residual_log` by maximizing `self._residual(reference, ts, baseline.beta, sign)` over `ts in range(anchor, end + 1, step)` (the forward horizon `[anchor, anchor + H]`, measured from the price origin `reference = anchor - velocity_ms`). This preserves the `[anchor - 30s, anchor]` run-up in the numerator and denominator while guaranteeing `pre_window_peak_ts_ms >= anchor`, eliminating the S1 anomaly where a pre-trigger wick at `anchor - 10s` forces an alert at `anchor` to be labeled `"late_after_activity_trigger"`.
3. **Freeze S2 (Causal Baseline Cutoffs):** Keep `sigma_end_rule = floor((anchor_ms - 35_000) / 60_000) * 60_000` (closed 1m candle boundary prior to both velocity windows) and `pace_end_ts_ms = anchor_ms - 30_000` (5s micro-bar boundary immediately prior to the active 30s window).
4. **Freeze S3 (Explicit Reason on Null Pre-Window Consumed Fraction):** In `_v2_alert_timing()`, include `"pre_window_consumed_fraction_reason"` with deterministic values: `None` (when valid), `label["pre_window_reference_reason"]` (when `[anchor - 30s, anchor]` fails `_quality`), or `"nonpositive_pre_window_peak"` (when `reference_peak <= 0`).

### Remaining Definitions Required Before Study Collection & Fitting

Even after freezing the V2 target code above, the following five study gates in `INSTANT_TARGET_CONTRACT_V2_DRAFT.json` (`remaining_study_gates`) must be specified and locked before enabling `operational_false_alert_and_missed_move_rates_enabled` or `fitting_allowed`:

1. **Event-Association & Exposure Protocol (Operational Denominators):**
* **Many-to-Many Alert/Window Assignment:** A single Top-$K$ entry at `t_alert` (under the 15m per-coin shared cooldown) can fall inside `[anchor - 180s, anchor + H]` for both a 5m and 15m `forward_event_catalog` window, or multiple alerts across coins can occur during one market episode. Freeze the exact matching rule: evaluate 5m and 15m horizons in separate tables, associate each `forward_event_catalog` window with the **first** qualifying Top-$K$ entry for `(product_id, direction)` inside `[anchor - 180s, anchor + H]`, and classify a Top-$K$ alert as a **False Alert** for horizon $H$ if and only if `verified_forward` at the alert's aligned grid cutoff $b = \lfloor t_{\text{alert}} / 5000 \rfloor \times 5000$ is `False` AND $t_{\text{alert}}$ does not fall within `[anchor - 180s, anchor + H]` of any cataloged `verified_forward` window for `(product_id, direction, H)` (with `unavailable` rows excluded from both numerator and denominator, never counted as false alerts).
* **Exposure Denominators:** Freeze `false_alerts_per_hour` denominator as **verified collector-healthy wall-clock hours** (excluding intervals with feed-health downtime or immature trailing $H$), and `missed_move_rate` denominator as the count of deduplicated `forward_event_catalog` windows for `(product_id, direction, H)` across the **entire causally eligible universe** (including eligible coins that never enter a board) that had verified feed coverage during `[anchor - 180s, anchor + H]`.


2. **Exact F1–F5 Mathematical Formulas & Live Stage Thresholds:**
* Freeze whether F1 and F5 use the boxcar `[b-30s, b)` / `[b-180s, b-30s)` log returns or the unnormalized decayed sums `S_i,h,j` (`h=30s, 180s`).
* Freeze the exact L1 observation-age time-weighting formula for F3, the exact 15m candle dispersion metric for F4, and the numeric cutoffs separating `IGNITING`, `CONFIRMED`, and `FADING/ABSORBED` downstream of the hard `EXTENDED` gate (`E > 3.5` or `abs(r_24h) > 10%` with `< $1M` trailing 24h USD volume).


3. **Recorder & Universe Contract:**
* Implement and verify the `micro_bars_5s` sparse recorder, read-time reconstruction of healthy zero-trade buckets, and upstream `Baseline` builder proving that the 120 non-overlapping 30s pace windows end at `anchor - 30s` and the 60 closed 1m returns end at `floor((anchor - 35s)/60s)*60s`.


4. **Step 2.5 Feed Side & Coverage Audit Gate (`hour_gate_pass`):**
* Currently `false` because `ALCX` and `AURORA` had only 4 and 3 paired trades in the completed 1-hour sample. Either complete an extended diagnostic capture sufficient to verify thin-product side/coverage or restrict F2/study eligibility strictly to products passing reconciled match coverage.


5. **Discovery Readiness Minima & Probabilistic Calibration Declaration:**
* Freeze the minimum required count of deduplicated `forward_event_catalog` episodes per `(direction, horizon)` in Days 1–7 before fitting the two 5-weight models, and declare the exact link/calibration function if any probability metric (log-loss/Brier) is used alongside Top-$K$ ranking metrics.



---

## 5. Final Verdict

* **V2 Target Evaluator Code (`92fb51d` + S1/S2/S3 dispositions above):** **READY FOR TARGET-CONTRACT FREEZE** once the explicit dispositions for S1 (forward-horizon peak search from the `anchor - 30s` price baseline) and S3 (`pre_window_consumed_fraction_reason`) are committed and hashes regenerated.
* **Prospective Study Collection & Model Fitting:** **BLOCKED** (`fitting_allowed: false`, `operational_false_alert_and_missed_move_rates_enabled: false`) pending completion of the five remaining study gates above: (1) freezing the multi-event alert-association and exposure denominator rules, (2) freezing exact F1–F5 formulas and live stage thresholds, (3) implementing and verifying the 5s recorder and `Baseline` builder contract, (4) passing the Step 2.5 feed side/coverage audit gate, and (5) collecting $\ge 14$ valid shadow days meeting discovery readiness minima.