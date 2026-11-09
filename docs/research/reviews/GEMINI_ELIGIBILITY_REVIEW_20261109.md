### 1. Source Disclosure and Verdict

All 15 numbered source sections in the attached packet (`Moonwalking-Gemini-Eligibility-Sources-20261109-17b87ac.txt`, branch `codex/instant-radar-20261028`, source commit `17b87ac261cae7011b168ca58228905f055748ff`) were read in full with zero unavailable or truncated blobs:

* **Source 01:** `docs/research/INSTANT_BATCHED_SOURCE_PILOT_RESULTS_20261108.md` (Listed SHA-256: `39e8da74...6231a`, 4,781 bytes) — Batched real-source coverage and latency results for implementation `c9d79be`.
* **Source 02:** `docs/research/INSTANT_BATCHED_SOURCE_PILOT_PROTOCOL_20261108.md` (Listed SHA-256: `28cdfc70...4e939e`, 3,095 bytes) — Protocol for the `batched-256` 67-minute capture and +5s fixed as-of cohort evaluation.
* **Source 03:** `docs/research/results/instant_batched_source_pilot_20261108/PLAN.json` (Listed SHA-256: `935c8018...39b53ca`, 698 bytes) — Pre-capture plan pinning commit `c9d79beb4665a1f05e08588819b44450e79fb169` and bounds.
* **Source 04:** `docs/research/results/instant_batched_source_pilot_20261108/CHECKS.json` (Listed SHA-256: `2b6b66d5...87fa21`, 2,915 bytes) — Verification artifact reporting 166,035 packet digests, 80 outbox digests, and 1,316 passed targeted tests.
* **Source 05:** `docs/research/results/instant_batched_source_pilot_20261108/ATTEMPT_01.json` (Listed SHA-256: `97141e2d...2baa29`, 120,295 bytes) — Full telemetry, per-channel latencies, coverage probes at `0ms` and `5000ms` offsets, and all 80 diagnostic rows.
* **Source 06:** `docs/research/INSTANT_REAL_INDEXED_PILOT_RESULTS_20261107.md` (Listed SHA-256: `fd839e31...cb4785f`, 3,581 bytes) — Prior stopped attempt (`single-128` overflow at 20m 35.553s and ALCX sequence-2 pre-ack snapshot failure).
* **Source 07:** `docs/research/INSTANT_TIMED_BASELINE_20261106.md` (Listed SHA-256: `5f38f7da...ebad89`, 2,639 bytes) — Specification for `build_timed_baseline` (volatility/beta and 120-bin activity pace).
* **Source 08:** `docs/research/INSTANT_TIMED_FEATURES_20261107.md` (Listed SHA-256: `198db049...7cf1b76`, 3,598 bytes) — Specification for `build_timed_features` (F1–F5 formulas, F3 piecewise boundaries, F4 candle rules).
* **Source 09:** `scripts/scoring_experiment/instant_timed_baseline.py` (Listed SHA-256: `f7a753d3...6637f101586a43`, 6,286 bytes) — Python implementation of `_volatility`, `_pace`, and `build_timed_baseline`.
* **Source 10:** `scripts/scoring_experiment/instant_timed_features.py` (Listed SHA-256: `4a100cf6...2e2eb0b`, 11,389 bytes) — Python implementation of `_price_point`, `_move`, `_participation`, `_book_pressure`, `_candle_range`, and `build_timed_features`.
* **Source 11:** `docs/research/INSTANT_DELAYED_DECISION_20261107.md` (Listed SHA-256: `69ac0074...46252f5ed9633b31087a9ff5`, 3,583 bytes) — Specification of `prepare_decision`, `observe_publication`, and `grade_publication` in `instant_delayed_decision.py`.
* **Source 12:** `docs/research/INSTANT_DIRECTIONAL_EXPOSURE_20261104.md` (Listed SHA-256: `61933e86...3bf2f`, 5,207 bytes) — Specification of `instant_directional_exposure.exposure_report` and per-board denominators.
* **Source 13:** `docs/research/INSTANT_DIRECTIONAL_EXPOSURE_CONTRACT_V1_DRAFT.json` (Listed SHA-256: `6bc66818...987d3189a920`, 1,795 bytes) — Contract rules for explicit four-flag eligibility and ranker intersections.
* **Source 14:** `docs/research/INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md` (Listed SHA-256: `ec241844...63d1e`, 14,739 bytes) — Consolidated study freeze candidate, target definitions, and F1–F5 mechanism hypotheses.
* **Source 15:** `docs/research/INSTANT_METHOD_REVIEW_TRIAGE_20261106.md` (Listed SHA-256: `eba23a69...a04`, 11,385 bytes) — Triage of prior methodology review, C1–C4 guardrails, and five-step freeze order.



**Verification Disclosure (Reported vs. Computed):**
All SHA-256 digests, byte counts, and test passes (1,316 targeted tests, 166,035 packet digests, 80 outbox digests, 11 historical hashes) are **reported values** read from the packet headers and `CHECKS.json` (Source 04); I did not execute `pytest`, compute independent SHA-256 hashes over raw files, or inspect the external artifacts linked in Source 01 (`OBSERVED.jsonl`, `CLOCK_BEFORE.txt`, `CLOCK_AFTER.txt`) beyond their summarized values in Sources 01, 04, and 05. However, I **independently verified** the cross-section arithmetic and structural invariants across Sources 01, 03, 04, 05, 09, and 10:

1. Frame counts in `ATTEMPT_01.json` (Source 05) sum to `166,033` committed data frames (`1` subscriptions + `4` snapshots + `4` last_match + `13,542` ticker + `122,864` l2update + `13,538` match + `16,080` heartbeat), matching `batched_packet_clocks_verified: 166033` and `166,035` total journal records when adding `connection_opened` and `connection_closed` (Source 04).


2. In `ATTEMPT_01.json` (Source 05), `first_ack_ts_ms` is `1794136397012`. Adding `warmup_ms: 3720000` (62m, Source 03) yields `1794140117012`, making the first 5s grid point `1794140120000` (Cohort 1 of 10 in `diagnostic_rows`, running through `1794140165000`). *(Note: `coverage.warmup.first_post_warmup_cutoff_ts_ms` in Source 05 reports `1794140130000` because it adds `3720000` to `inventory.first_cutoff` `1794136400000` plus an extra step, whereas the 10 diagnostic cohorts properly start at `1794140120000` per Source 02 protocol)*.


3. In `ATTEMPT_01.json` (Source 05), ALCX `F5` readiness is reported as `"stale_book_observation"` on the first 4 rows (`1794140120000` and `1794140125000`) and `"volatility_baseline_unavailable"` on the remaining 16 rows (`1794140130000`–`1794140165000`), because `_market_relative` in `instant_timed_features.py` (Source 10) checks `coin_move` and `btc_move` before `baseline["status"] != "ready"`. At `1794140120000` and `1794140125000`, ALCX's endpoint quote was stale, whereas from `1794140130000` onward its endpoint quotes were fresh (`ready`) so the check fell through to `"volatility_baseline_unavailable"`. Similarly, ALCX `F1` and `F4` report `"stale_book_observation"` at `1794140150000` (2 rows) and `"volatility_baseline_unavailable"` on the other 18 rows.



**Distinction Between Pilot Measurements and Policy Proposals:**

* **What the November 8 Pilot Measured (Source 01, Source 05):** A single 67-minute, 4-product (`BTC-USD`, `SOL-USD`, `ALCX-USD`, `AURORA-USD`) capture on `batched-256` that resolved the November 7 `single-128` queue overflow and pre-ack snapshot bug (Source 06). It measured: (a) `0 / 532` trade windows proven at `cutoff + 0ms` across 133 probes per product, but `532 / 532` (100%) proven by `cutoff + 5000ms` with `ready_proof_lag_from_cutoff` p95 of `929–936ms` and max `1,003ms`; (b) quote readiness at `+0ms` vs `+5000ms` (`130/133` to `133/133` for BTC due to 3 `quote_row_processing_incomplete` at `+0ms`; `133/133` SOL; `109/133` ALCX; `133/133` AURORA); (c) full 30s book-window readiness (`133/133` BTC/SOL, `47/133` ALCX, `132/133` AURORA); (d) feature readiness across 10 post-warmup cutoffs (80 directional rows): BTC and SOL 100% ready on baselines and F1–F5; ALCX 0/20 volatility baseline, 0/20 F1/F2/F4/F5, 12/20 F3; AURORA 20/20 baselines and F1/F3/F5, 0/20 F2 (`nonpositive_pace_median`), 0/20 F4 (`too_few_traded_candles`); (e) local processing and delivery timing: `prepare_ms` p95 `70.2ms` (max `107.1ms`), `outbox_ms` p95 `20.2ms` (max `26.5ms`), 8-row serial cohort completion max `655.2ms`, and cutoff-to-local-reader max `5,678ms` (which includes the fixed `5,000ms` evidence offset); and (f) opposite ticker/match sides on all paired trades (`11,175` BTC, `2,354` SOL, `5` ALCX, `4` AURORA). It did **not** measure predictive performance, forward outcomes, public network delivery, or multi-hour/multi-day regime stability.


* **What This Review Proposes:** A versioned, two-clock delayed-decision eligibility policy (`instant-delayed-eligibility-v1-candidate`) that separates planned-universe inventory (`universe_member`) from cutoff-anchored evidence verification (`health_verified`) and ranker-specific feature readiness (`candidate_eligible`), paired with a proposed evidence wait offset and decision age budget to replace the unfrozen 2,500ms draft.

**Recommended Eligibility Policy (One-Paragraph Verdict):**
Every planned `product × cutoff × direction` slot in the declared inventory must be permanently retained in the denominator (`universe_member = True`), while positive decision eligibility is evaluated under an explicit delayed-decision protocol (`instant-delayed-eligibility-v1-candidate`) that decouples the content cutoff `b` from the evidence knowledge clock `t_asof`. Because the November 8 pilot proved that `0 / 532` trade windows were verified at `b + 0ms` while `532 / 532` verified by `t_asof` with a maximum proof lag of `1,003ms` (p95 `929–936ms`, Source 05), any policy requiring proof at `b + 0ms` yields 0% eligibility, whereas waiting for the pilot's diagnostic `+5,000ms` offset unnecessarily inflates decision age. **Proposal:** Set a predeclared evidence-wait schedule of $\Delta_{\text{asof}} = 1,500\text{ ms}$ (`t_asof = b + 1500ms`, or event-driven trigger upon watermarks reaching `b` capped at `b + 1500ms`), and a maximum local decision-publication age budget of $\Delta_{\text{pub\_max}} = 2,500\text{ ms}$ (`t_pub <= b + 2500ms`), with an alternative conservative schedule keeping the pilot's tested $\Delta_{\text{asof}} = 5,000\text{ ms}$ and $\Delta_{\text{pub\_max}} = 6,000\text{ ms}$ if zero-code-change parity with the pilot runner is preferred. Under either clock proposal, keep existing feature mathematical thresholds from `instant_timed_baseline.py` (Source 09) and `instant_timed_features.py` (Source 10) unchanged as **proposals to lock** (`MAX_QUOTE_AGE_MS = 10,000ms`, `MAX_HEARTBEAT_GAP_MS = 5,000ms`, `RETURN_COUNT = 60` closed 1m returns, `PACE_COUNT = 120` 30s bins with `pace_quote_usd_median_30s > 0`, `MIN_MATCHES = 5` in `[b-30s, b)`, `MIN_TRADED_CANDLES = 10` of `15` closed 1m bins, `SIGMA_FLOOR = 0.0015`), require all five features (`F1`–`F5`) and both baselines to be `"ready"` for primary full-vector ranker eligibility (`candidate_eligible = True`), and record partial/thin products (`ALCX-USD`, `AURORA-USD`) as explicit exclusions in the full-study exposure report while routing their ready features (`F3` for ALCX; `F1, F3, F5` for AURORA) exclusively to secondary single-feature/subset ablation cohorts. **Validation:** Validate $\Delta_{\text{asof}}$ and $\Delta_{\text{pub\_max}}$ via one outcome-blind, multi-session 24-hour shadow capture before freezing the study, verifying that proof-lag p99.9 stays $\le 1,500\text{ ms}$ and cohort serial preparation plus outbox commit stays $\le 1,000\text{ ms}$ across UTC volume regimes.

---

### 2. Decision Table: Membership, Feature Readiness, Ranker Eligibility, and Gradability

#### 2A. Stage-Gate Separation Across the Decision Lifecycle

| Lifecycle Stage | Governing Function / Module | Required Conditions | Clock Constraint | Effect of Failure / Missingness |
| --- | --- | --- | --- | --- |
| **1. Planned-Universe Membership** (`universe_member`) | `manifest.inventory` (Source 05); `exposure_report` (Source 12, 13) | Product and 5s grid cutoff `b` (`first_cutoff <= b <= stop_cutoff`) predeclared in `PLAN.json` before socket open (`inventory_recorded_ts_ms <= asof`); both `up` and `down` explicitly emitted with identical `universe_member`. | Recorded prior to capture (`t_plan < b`). | Unpaired or omitted rows raise `ValueError` in `exposure_report`. Thin products (`ALCX-USD`, `AURORA-USD`) remain `universe_member = True` permanently. |
| **2. Warmup Completion** (`warmup_complete`) | `build_timed_baseline` (Source 09); `PLAN.json` (Source 03) | `b >= first_ack_ts_ms + 3,720,000` (62 minutes post-acknowledgment), ensuring `sigma_start = floor((b - 35000)/60000)*60000 - 3600000 >= GRID_MS` and `pace_start = b - 3630000 >= 0`. | Deterministic function of `b` and `first_ack_ts_ms`. | Row is retained in universe; excluded with primary reason `warmup_incomplete` (`warmup_complete = False`). |
| **3. Transport & Baseline Health** (`health_verified`) | `recorder._trade_window`, `recorder._quote_at` (Source 09, 10) | By `t_asof`: (a) active connection & heartbeat (`<= 5,000ms` gap); (b) fresh anchor quote at `b` (`age <= 10,000ms`, valid BBO `bid < ask`); (c) fresh BTC anchor quote at `b`; (d) strict receipt-ID proof chains covering baseline windows and `[b-30s, b)`. | Evidence known at `t_avail <= t_asof`. | Row is excluded with `health_verified = False` (retaining specific sub-reason: `stale_book_observation`, `trade_coverage_not_yet_proven`, etc.). |
| **4. Individual Feature Readiness** (`F1`..`F5 == "ready"`) | `build_timed_features` (Source 10) | Feature-specific input, baseline, and activity minima satisfied using only market events with `receipt_ts_ms < b` known by `t_asof`. | `evidence_available_ts_ms <= t_asof`. | Individual feature returns `status="unavailable"` with explicit `reason` and `evidence_available_ts_ms = null`. |
| **5. Full-Vector Ranker Eligibility** (`candidate_eligible`) | `prepare_decision` (Source 11); versioned adapter to `exposure_report` (Source 12) | For the primary 5-feature ranker: `universe_member`, `warmup_complete`, and `health_verified` are `True`, AND `volatility == "ready"`, `pace == "ready"`, and all five features `F1`–`F5 == "ready"`. *(Subset/single-feature diagnostic rankers require only their consumed feature(s) + required baselines).* | Frozen at `t_prep` (`b <= t_asof <= t_feat <= t_prep`). | Row is excluded from primary ranker (`candidate_eligible = False`), never scored by the 5-feature model, and counted in exclusion denominators. |
| **6. Decision Age & Delivery** (`age_eligible`) | `observe_publication` (Source 11); local outbox reader (Source 01, 05) | Chronology `b <= t_asof <= t_feat <= t_prep <= t_pub <= t_obs` holds, AND `t_pub - b <= delta_pub_max` (**Proposal:** `2,500ms` under `+1.5s` as-of, or `6,000ms` under `+5.0s` as-of). | Verified at `t_obs` when committed to outbox. | If `t_pub > b + delta_pub_max`, decision is flagged `late_publication` (ineligible for live/operational alert credit, logged in latency failure stratum). |
| **7. Own-Direction Outcome Gradability** (`gradable_300s`, `gradable_900s`) | `grade_publication` (Source 11); `exposure_report` (Source 12, 13) | Row is `decision_eligible`, `t_grade_asof >= b + H` (`H in {300s, 900s}`), own-direction `cutoff_verified_forward` is non-null (paired coin & BTC quotes at 5s grid in `(b, b+H]`, continuous receipt-ID proof from `b-5s` to `b+H`, no anchor contradiction, no mid-packet `asof`). | Evaluated at `t_grade_asof >= b + H`. | Reported as `pending` (if `< b+H`) or `unavailable` (with reason). Never flips `decision_eligible` to `False` and never counts as `pointwise_failure_H`.

 |

---

#### 2B. Baseline and Feature-Level Specification (`F1`–`F5`)

All thresholds below reflect the implemented code in `instant_timed_baseline.py` (Source 09) and `instant_timed_features.py` (Source 10). Retaining these exact numerical values for the study is a **proposal**, to be validated as described in Section 4.

| Component | Required Raw Inputs (`receipt_ts_ms < b`, known by `t_asof`) | Benchmark / Baseline Dependencies | Explicit `"unavailable"` Reasons (Code String -> Root Cause) | Legitimate Zero (`status="ready"`, `value=0.0`) vs. Unavailable |
| --- | --- | --- | --- | --- |
| **Baseline: Volatility & Beta** (`_volatility`, Source 09) | 61 paired coin and `BTC-USD` midpoint quotes at 1m boundaries `sigma_start` to `sigma_end = floor((b-35000)/60000)*60000` (forming 60 log returns); receipt-ID trade proofs for both products over `[sigma_start - 5000ms, sigma_end]`. | `BTC-USD` 61 minute-close quotes and trade proof chain over `[sigma_start - 5000ms, sigma_end]`. | • `insufficient_history`: `sigma_start < 5000ms`<br>

<br>• `window_not_closed`: `sigma_end > asof`<br>

<br>• `trade_coverage_not_yet_proven` (or proof gap reason) on coin or BTC<br>

<br>• `stale_book_observation` / `book_state_unavailable` / `quote_row_processing_incomplete` at any of the 61 closes (coin or BTC, with `missing_close_ts_ms`)<br>

<br>• `nonfinite_baseline`: `sigma` or `beta` is `NaN`/`Inf` | **Zero `sigma_1m`:** When all 60 coin closes are identical and fresh, `sigma_1m = 0.0` (`status="ready"`), which downstream features clamp via `SIGMA_FLOOR = 0.0015` (**Proposal**).<br>

<br>**Beta Fallback:** When all 60 BTC returns are identical (`variance == 0`), `status="ready"` with `beta = 1.0` and `beta_fallback = True` (not unavailable). |
| **Baseline: Activity Pace** (`_pace`, Source 09) | First-receipt matches for `product` in 120 half-open 30s bins `[b - 3630s, b - 30s)`; single continuity-epoch receipt-ID proof chain covering the 60m interval. (Maker side is ignored). | None (product-only). | • `insufficient_history`: `pace_start < 0`<br>

<br>• `window_not_closed`: `pace_end > asof`<br>

<br>• `trade_coverage_not_yet_proven` (or proof gap reason) in `[b-3630s, b-30s)`<br>

<br>• `invalid_quote_amount`: `DecimalException` or non-finite median | **Verified Empty Bins / Zero Median:** Proved empty 30s bins legitimately contribute `0` to `counts` and `Decimal(0)` to `amounts`. If $\ge 60$ of 120 bins have 0 volume, `_pace` returns `status="ready"` with `pace_quote_usd_median_30s = "0"` (seen on `ALCX-USD` and `AURORA-USD` in Source 05). |
| **F1: Acceleration** (`_acceleration`, Source 10) | Coin midpoint quotes at `b - 180s`, `b - 30s`, and `b` (`age <= 10,000ms` at each endpoint). | `baseline["volatility"] == "ready"` (`sigma_used = max(sigma_1m, 0.0015)`). Indirectly depends on `BTC-USD` because `_volatility` requires paired BTC closes. | • Any endpoint quote failure (`stale_book_observation`, `book_state_unavailable`, `quote_row_processing_incomplete`) at `b-180s`, `b-30s`, or `b`<br>

<br>• `volatility_baseline_unavailable` (when `recent` move is ready but `vol["status"] != "ready"`, e.g., ALCX in Source 05)<br>

<br>• `nonfinite_feature` | **Legitimate `0.0`:** All 3 endpoint quotes and volatility baseline are `"ready"`, and `r_coin_30s == r_coin_prior150s / 5` (e.g., flat price or constant linear log-drift across `b-180s`, `b-30s`, `b`). |
| **F2: Signed Participation** (`_participation`, Source 10) | Certified trade window `[b - 30s, b)` with $\ge 5$ first-receipt matches (`MIN_MATCHES = 5`, **Proposal**), every match having known `taker_side in {"buy", "sell"}`, and total quote USD $> 0$. | `baseline["pace"] == "ready"` AND `Decimal(pace_quote_usd_median_30s) > 0`. | • `insufficient_history` or trade proof gap (`trade_coverage_not_yet_proven`)<br>

<br>• `invalid_quote_amount`: non-finite USD sum<br>

<br>• `pace_baseline_unavailable`: `_pace` not ready<br>

<br>• `nonpositive_pace_median`: `median <= 0` (blocked ALCX & AURORA on 20/20 rows in Source 05)<br>

<br>• `invalid_volume_pace`: non-finite ratio or underflow `total > 0 and ratio == 0`<br>

<br>• `too_few_matches`: `len(trades) < 5`<br>

<br>• `unknown_match_side`: any `trade.taker_side is None`<br>

<br>• `nonpositive_window_quote_amount`: `total <= 0` | **Legitimate `0.0`:** Window is certified, `pace_median > 0`, `len(trades) >= 5`, all sides known, `total > 0`, and buyer-initiated USD exactly equals seller-initiated USD (`amounts["buy"] == amounts["sell"]`, so `imbalance == 0.0`). Verified empty `[b-30s, b)` is **never** `0.0`; it is `"unavailable"` (`too_few_matches`). |
| **F3: Sampled Book Pressure** (`_book_pressure`, Source 10) | Receipt-ordered L1 book states and transport heartbeats across `[b - 30s, b)` (carrying state from $\le b-30\text{s}$, excluding events at `b`). Every subsegment `[left, right)` must have valid BBO, matching `connection_id` heartbeat, book `right - observation_ts_ms <= 10,000ms`, and heartbeat `right - receipt_ts_ms <= 5,000ms`. | None (no baseline or BTC dependency). | • `insufficient_history`<br>

<br>• `book_state_unavailable`: `state is None or state.best is None or state.reason`<br>

<br>• `heartbeat_unavailable`: missing heartbeat or `connection_id` mismatch<br>

<br>• `stale_book_span`: any positive-duration segment exceeds `10,000ms` quote age (blocked ALCX on 8/20 rows in Source 05)<br>

<br>• `stale_heartbeat_span`: heartbeat gap $> 5,000\text{ms}$ | **Legitimate `0.0`:** Continuous valid, fresh book and heartbeat coverage across all 30,000ms of `[b-30s, b)` where the time-weighted integral of `(bid_size - ask_size)/(bid_size + ask_size)` sums to `0.0` (e.g., symmetric depth `bid_size == ask_size` throughout). |
| **F4: Active Compression / Expansion** (`_compression`, Source 10) | Coin midpoint quotes at `b - 30s` and `b`; certified trade window over 15 UTC-aligned 1m buckets ending at `candle_end = floor((b - 30s)/60000)*60000` with $\ge 10$ buckets containing $\ge 1$ trade (`MIN_TRADED_CANDLES = 10`, **Proposal**). | `baseline["volatility"] == "ready"` (`sigma_used = max(sigma_1m, 0.0015)`). | • Endpoint quote failure at `b-30s` or `b` (`stale_book_observation`, etc.)<br>

<br>• `volatility_baseline_unavailable` (blocked ALCX on 18/20 rows in Source 05)<br>

<br>• Trade proof failure in 15m candle window<br>

<br>• `too_few_traded_candles`: `traded_candles < 10` (blocked AURORA on 20/20 rows in Source 05)<br>

<br>• `invalid_candle_range` / `nonfinite_feature` | **Legitimate `0.0`:** Volatility baseline is ready, $\ge 10$ of 15 candles have verified trades (up to 5 verified empty candles allowed and ignored in `high`/`low`), quotes at `b-30s` and `b` are fresh, and directional 30s velocity is $\le 0$ (`sign * move <= 0`, so `expansion = max(velocity, 0) == 0.0`). |
| **F5: Market-Relative Movement** (`_market_relative`, Source 10) | Synchronized coin AND `BTC-USD` midpoint quotes at `b - 180s` and `b` (`age <= 10,000ms`). | `baseline["volatility"] == "ready"` (supplies both `sigma_used` and `beta`, plus `beta_fallback` flag) and `BTC-USD` 180s return. | • Coin quote failure at `b-180s` or `b` (e.g., ALCX first 4 rows in Source 05)<br>

<br>• `BTC-USD` quote failure at `b-180s` or `b`<br>

<br>• `volatility_baseline_unavailable` (e.g., ALCX last 16 rows in Source 05)<br>

<br>• `nonfinite_feature` | **Legitimate `0.0`:** Coin quotes, BTC quotes, and volatility baseline are all `"ready"`, and `r_coin_180s == beta * r_btc_180s` (always `0.0` when `product == "BTC-USD"` since `coin_move == btc_move` and `beta == 1.0`, unless `beta_fallback` or floating-point rounding occurs).

 |

**Architectural Note on Missing BTC Evidence (`_volatility` Coupled Dependency):**
In `instant_timed_baseline.py` (Source 09), `_volatility` loops over `dict.fromkeys((product, BENCHMARK))` and returns a single `"unavailable"` dict if `BTC-USD` is missing a minute close or trade proof—even if the altcoin's own 61 closes are 100% fresh (`sigma_1m` could have been computed alone). Under the current code (`17b87ac`), a missing `BTC-USD` baseline close therefore blocks not only `F5` (which genuinely needs `beta`), but also `F1` and `F4` (which only need `sigma_1m`).

* **Primary Proposal (Zero-Code-Change):** Retain the current coupled behavior in `instant_timed_baseline.py` because the primary study cohort requires full `F1`–`F5` vectors anyway (where `F5` already requires `BTC-USD`).
* **Alternative Proposal (For Single-Feature Diagnostic Cohorts):** If Codex wants `F1` and `F4` single-feature ablations to survive a `BTC-USD` quote outage, split `_volatility` into `sigma_status` (coin-only) and `beta_status` (coin + BTC) in a v2 baseline contract.

---

### 3. Timing, Causal Clocks, and Exposure Accounting

#### 3A. Six-Clock Causal Sequence (`instant-delayed-eligibility-v1-candidate`)

To preserve strict causality while accommodating delayed receipt-ID proofs (Source 11, Source 15 C1), every row in the delayed-decision pipeline must record and enforce the monotonic six-clock chain:

$$b \le t_{\text{asof}} \le t_{\text{feat}} \le t_{\text{prep}} \le t_{\text{pub}} \le t_{\text{obs}} < t_{\text{grade\_asof}}$$

1. **Observation Content Cutoff ($b$ / `cutoff_ts_ms`):** The 5-second grid boundary (`b % 5000 == 0`). **Hard Content Rule:** Only market frames with `receipt_ts_ms < b` may enter `F1`–`F5` trade windows (`[b-30s, b)`), F3 book integrals (`[b-30s, b)`), or endpoint quotes at `b` (where `_quote_at(pid, b, asof)` selects the last valid book state with `receipt_ts_ms <= b` and `b - observation_ts_ms <= 10,000ms`). Market frames with `receipt_ts_ms > b` are strictly excluded from feature values.


2. **Evidence Knowledge As-Of ($t_{\text{asof}}$ / `knowledge_asof_ts_ms`):** The recorder timestamp at which the ledger prefix `(known_packet_count, known_packet_prefix_sha256)` is frozen for decision evaluation (`t_asof = b + delta_asof_ms`).


* *How Post-Cutoff Proofs Qualify Pre-Cutoff Observations:* In Coinbase's feed, verifying that no trades were dropped in `[b-30s, b)` requires observing the first post-cutoff heartbeat or match frame (`receipt_ts_ms >= b`) whose monotonic sequence/trade-ID closes the watermark across `b`, AND waiting for the batched writer to commit that frame to SQLite (`available_ts_ms`). In the November 8 pilot (Source 05), `F2` `evidence_available_ts_ms` was consistently `b + 862ms` to `b + 897ms` across all 10 cohorts (e.g., `1794140120888` at cutoff `1794140120000`), and `F1`/`F3`/`F4`/`F5` `evidence_available_ts_ms` occasionally reached `b + 556ms` (e.g., at cutoffs `1794140135000` and `1794140150000` when the batch containing the last pre-cutoff book update committed at `+555–556ms`). So long as `evidence_available_ts_ms <= t_asof`, the pre-cutoff observation is causally verified as-of `t_asof` without leaking post-cutoff prices or volumes.




3. **Feature Computation Completed ($t_{\text{feat}}$ / `computation_completed_ts_ms`):** Recorder clock read at the end of `build_timed_features` after baseline and F1–F5 evaluation (Source 10).


4. **Decision Snapshot Prepared ($t_{\text{prep}}$ / `decision_completed_ts_ms`):** Clock read in `prepare_decision` after canonical JSON serialization and `decision_sha256` hashing (Source 05, Source 11). In the pilot, `prepare_ms` (`t_prep - cohort_start_ts_ms`) had p95 `70.2ms` and max `107.1ms`.


5. **Publication Commit Observed ($t_{\text{pub}}$ / `commit_observed_ts_ms`):** Clock read when the SQLite outbox transaction durably commits the decision row (Source 05: `outbox_ms` p95 `20.2ms`, max `26.5ms`; whole 8-row cohort serial completion `cohort_serial` max `655.16ms`, meaning the 8th row committed at `b + 5,652ms`).


6. **Consumer Observation ($t_{\text{obs}}$ / `consumer_seen_ts_ms`) & Later Grading ($t_{\text{grade\_asof}}$):** Separate process read time (`cutoff_to_reader_seen` max `5,678ms` in Source 05) and post-maturity grading time (`t_grade_asof >= b + H` for $H \in \{300\text{s}, 900\text{s}\}$ in `grade_publication`, Source 11).



#### 3B. Versioned Adapter for Delayed Decisions, Late Proofs, and Contradictions

* **Why a Versioned Adapter Is Required:** `instant_directional_exposure.exposure_report` (`instant-directional-exposure-v1-draft`, Sources 12, 13, 15 C1) enforces `available_ts_ms <= ts_ms <= asof_ts_ms` (`ts_ms = b`). Under real websocket streaming, `available_ts_ms` for trade proof is always $> b$ (`+862ms` to `+1,003ms` in Source 05). Never falsify `available_ts_ms` by setting it to `b`. Instead, introduce `instant-directional-exposure-v2-delayed-draft` (or an explicit `delayed_decision_adapter`), which validates:


1. `b <= knowledge_asof_ts_ms <= decision_completed_ts_ms <= commit_observed_ts_ms <= b + delta_pub_max_ms <= report_asof_ts_ms`
2. For every required component $k$, `evidence_available_ts_ms[k] <= knowledge_asof_ts_ms`.


* **Handling Proofs Arriving After the Decision Deadline ($t_{\text{avail}} > t_{\text{asof}}$ or $t_{\text{pub}} > b + \Delta_{\text{pub\_max}}$):**
* **Case 1 (Proof arrives after $t_{\text{asof}}$):** At $t_{\text{asof}}$, the snapshot in `prepare_decision` is immutably frozen with `trade_coverage_not_yet_proven` (or `quote_row_processing_incomplete`), setting `health_verified = False` and `candidate_eligible = False`. Even if the proof arrives 200ms later (at $t_{\text{asof}} + 200\text{ms}$), the decision row for slot $b$ is **never retroactively mutated or made eligible**. In diagnostics, a post-hoc audit column (`retrospective_proof_lag_ms`) may log that the proof arrived at $+1,700\text{ms}$, quantifying the exact coverage cost of $\Delta_{\text{asof}}$.


* **Case 2 (System stall pushes $t_{\text{pub}} > b + \Delta_{\text{pub\_max}}$):** All features were `"ready"` at $t_{\text{asof}}$, but writer/CPU contention delayed `commit_observed_ts_ms` past the publication deadline. The adapter marks `health_verified = True`, `features_ready = True`, but `candidate_eligible = False` with primary exclusion reason `decision_age_budget_exceeded` (`late_publication`).


* **Handling Later Evidence Contradicting an Immutable Decision:**
Once `prepare_decision` commits `decision_sha256` at $t_{\text{pub}}$, the decision record and its `decision_eligible = True` status are **permanently immutable**. If subsequent frames arriving during $(t_{\text{asof}}, b + H]$ reveal a sequence gap, out-of-watermark receipt ID, or anchor quote contradiction in `grade_publication` (Source 11):


1. `decision_eligible` **remains `True**` (decision exposure and alert burden denominators are never shrunk by post-decision events, per Source 12 and Source 15 Step 4).


2. `grade_publication` returns `status = "unavailable"`, `cutoff_verified_forward = None`, and `reason = "anchor_quote_contradicted"` or `"forward_trade_proof_invalidated"`.


3. In the exposure report, the row is counted in `eligible_rows` and `ungradable_unavailable_rows`, outside both `pointwise_success_H` and `pointwise_failure_H`.





#### 3C. Denominators for Coverage, Exclusions, Time Exposure, and Ranker Comparisons

Let $P$ be the planned product set ($|P|=4$ in pilot), $B$ be the set of planned 5s cutoffs ($|B|=10$ post-warmup in pilot; $133$ total probes), and $D = \{\text{up}, \text{down}\}$.

* **Planned Slot Universe (Per Board $d \in D$):** $N_{\text{planned}, d} = |P| \times |B|$. Both `up` and `down` boards must have identical $N_{\text{planned}, \text{up}} = N_{\text{planned}, \text{down}}$ (`40` rows per board, `80` total rows in the pilot cohort window).


* **Exclusive Flag Precedence for Exclusions (Per Board $d$):** Every planned slot $(p, b, d)$ is partitioned into exactly one of five mutually exclusive buckets (following Source 12 flag precedence):
1. `excluded_not_universe_member`: $\neg\text{universe\_member}$ (0 for planned inventory)
2. `excluded_warmup_incomplete`: $\text{universe\_member} \land \neg\text{warmup\_complete}$
3. `excluded_health_unverified`: $\text{universe\_member} \land \text{warmup\_complete} \land \neg\text{health\_verified}$ (sub-classified by first failed health check: `stale_book_observation`, `trade_coverage_not_yet_proven`, `volatility_baseline_unavailable`, `missing_benchmark_evidence`)
4. `excluded_candidate_ineligible`: $\text{universe\_member} \land \text{warmup\_complete} \land \text{health\_verified} \land \neg\text{candidate\_eligible}$ (sub-classified by feature/age reason: `nonpositive_pace_median`, `too_few_traded_candles`, `too_few_matches`, `unknown_match_side`, `stale_book_span`, `decision_age_budget_exceeded`)
5. `decision_eligible` ($E_d$): All four flags `True`.



$$\text{Coverage Rate}_d = \frac{|E_d|}{N_{\text{planned}, d}}, \qquad \text{Exclusion Rate}_d = 1 - \text{Coverage Rate}_d$$




* **Time Exposure Denominators (Never Summed Across Concurrent Products as Wall-Clock, Source 12 & 13):**
* **Eligible Product-Hours (Board $d$):** $\text{ProductHours}_d = |E_d| \times \frac{5}{3600}\text{ hours}$.


* **Healthy Board Wall-Clock Hours (Board $d$):** Union of cutoffs where at least one product is eligible on board $d$:

$$\text{BoardHours}_d = \left|\{b \in B : \exists p \in P \text{ s.t. } (p, b, d) \in E_d\}\right| \times \frac{5}{3600}\text{ hours}$$


* **Either-Board Wall-Clock Hours:**

$$\text{EitherBoardHours} = \left|\{b \in B : \exists p \in P, d \in D \text{ s.t. } (p, b, d) \in E_d\}\right| \times \frac{5}{3600}\text{ hours}$$




* **Outcome Gradability Partition (Never Shrinking Decision Exposure):**
For each horizon $H \in \{300\text{s}, 900\text{s}\}$ and board $d$, the fixed set $E_d$ is partitioned into:

$$E_d = G_{d,H} \cup U^{\text{pending}}_{d,H} \cup U^{\text{unavail}}_{d,H} \cup U^{\text{missing}}_{d,H}$$



where $G_{d,H}$ is the set of own-direction gradable rows (`cutoff_verified_forward` $\in \{\text{True}, \text{False}\}$), and $G_{d,H} = S_{d,H} \cup F_{d,H}$ (pointwise successes and failures). Ungradable burden is reported explicitly alongside hit rates as $\frac{|U_{d,H}|}{|E_d|}$.


* **Natural vs. Identical Ranker Comparisons (Source 12, 13):**
Given a set of rankers $\mathcal{R}$ (e.g., $\mathcal{R} = \{\text{Full\_F1\_F5}, \text{Control\_Velocity}, \text{Subset\_F1\_F3\_F5}\}$) where each ranker $r \in \mathcal{R}$ scores subset $M_{r,d} \subseteq E^{(r)}_d$:
* **Natural Coverage of Ranker $r$ (at Horizon $H$):** Evaluated on $M_{r,d} \cap G_{d,H}$, alongside its natural decision coverage $\frac{|M_{r,d}|}{N_{\text{planned},d}}$ and natural ungradable rate $\frac{|M_{r,d} \setminus G_{d,H}|}{|M_{r,d}|}$.


* **Identical (Paired) Comparison Set (across Ranker Roster $\mathcal{R}$ at Horizon $H$):**

$$I_{\mathcal{R}, d, H} = G_{d,H} \cap \bigcap_{r \in \mathcal{R}} M_{r,d}$$



Every ranker in $\mathcal{R}$ is evaluated on the exact same product $\times$ cutoff $\times$ direction rows $I_{\mathcal{R}, d, H}$, guaranteeing that missing features on thin products cannot create sample-selection bias between a full model and a simpler comparator.





---

#### 3D. Four Worked Row Dispositions

| Worked Case | Pilot Reference / Scenario | Clocks & Input Evidence State | Flags (`universe`, `warmup`, `health`, `candidate`) | Primary 5-Feature Ranker Disposition | Subset / Ablation Ranker Disposition | Later Grading & Denominator Accounting |
| --- | --- | --- | --- | --- | --- | --- |
| **1. Complete BTC / SOL Row** | `diagnostic-1794140120000-SOL-USD-up` (Source 05) | `b = 1794140120000`, `t_asof = 1794140125000`. Availabilities: `F1,F4: -135ms` (`1794140119865`), `F5: -113ms` (`1794140119887`), `F3: +0ms` (`1794140120000`), `F2: +888ms` (`1794140120888`). `t_prep = +5314ms`, `t_pub = +5324ms`, `t_obs = +5334ms`. | `(True, True, True, True)` | **Eligible (`True`).** Scored by primary 5-feature ranker; `decision_sha256 = f9cf3ba9...` committed to outbox. | **Eligible (`True`)** for all single-feature and subset rankers; enters identical intersection $I_{\mathcal{R}, \text{up}, H}$. | Adds `1` to $N_{\text{planned,up}}$, `1` to $ |
| **2. ALCX Gap Row** | `diagnostic-1794140150000-ALCX-USD-up` (Source 05) | `b = 1794140150000`, `t_asof = 1794140155000`. Endpoint quote at `b` is stale (`>10s`); book span in `[b-30s, b)` has stale gap; `volatility` baseline is `stale_book_observation`; `pace` is `ready` but `median == 0`. `F1,F4,F5: stale_book_observation`, `F2: nonpositive_pace_median`, `F3: stale_book_span`. *(Note: on cohorts 1–6 where ALCX F3 was `ready`, `F3` had `avail = b`, while `F1,F4,F5` failed volatility baseline).* | `(True, True, False, False)` *(On cohorts 1–6 where endpoint quote at `b` was fresh, `health_verified` for F3-only is `True`, but full-vector `health_verified` is `False` due to `volatility_baseline_unavailable`).* | **Excluded (`False`).** Primary exclusion bucket: `excluded_health_unverified` (sub-reason: `stale_book_observation` at `1794140150000`; `volatility_baseline_unavailable` on cohorts 3–6). | **Excluded (`False`)** at `1794140150000` for all rankers. *(On cohorts 1–6, eligible **only** for the standalone `F3`-only diagnostic ranker).* | Permanently retained in $N_{\text{planned,up}}$ (`universe_member = True`). Adds `0` to $ |
| **3. AURORA Partial Row** | `diagnostic-1794140120000-AURORA-USD-up` (Source 05) | `b = 1794140120000`, `t_asof = 1794140125000`. Both `volatility` and `pace` baselines are `"ready"`. `F1` (`-137ms`), `F3` (`+0ms`), and `F5` (`-113ms`) are `"ready"`. `F2` is `"nonpositive_pace_median"` (`pace_quote_usd_median_30s == 0`) and `F4` is `"too_few_traded_candles"` (`<10` of 15 1m bins traded). `t_prep = +5572ms`, `t_pub = +5581ms`. | `(True, True, True, False)` for primary 5-feature ranker. | **Excluded (`False`) from Primary 5-Feature Study.** Primary exclusion bucket: `excluded_candidate_ineligible` (sub-reasons logged: `F2: nonpositive_pace_median`, `F4: too_few_traded_candles`). | **Eligible (`True`)** for predeclared secondary diagnostic rankers that consume only `{F1, F3, F5}` (and their `current_velocity_sigma` / `raw_signed_180s` controls). | Retained in $N_{\text{planned,up}}$. Excluded from primary $E_{\text{up}}$ and primary identical intersection $I_{\mathcal{R}_{\text{full}}, \text{up}, H}$, but included in the `{F1, F3, F5}` ablation intersection. |
| **4. Missing BTC Benchmark on Otherwise Ready Coin** | Synthetic / Counterfactual on `SOL-USD` at cutoff `b` | `SOL-USD` has fresh quotes at all 61 baseline closes, `b-180s`, `b-30s`, `b`, continuous 30s book (`F3 == "ready"`), $\ge 5$ signed trades (`F2 == "ready"`), and $\ge 10$ traded candles. However, `BTC-USD` has `quote_row_processing_incomplete` or `stale_book_observation` at `b` (or at one of the 61 baseline closes). | `(True, True, False, False)` for primary 5-feature ranker. | **Excluded (`False`).** Under current `instant_timed_baseline.py` (Source 09) and `instant_timed_features.py` (Source 10):<br>

<br>• If BTC fails at `b`: `F5` fails with `BTC-USD` quote reason (`F1, F2, F3, F4` remain `"ready"`).<br>

<br>• If BTC fails at a baseline close: `_volatility` fails with `product_id="BTC-USD"`, blocking `F1, F4, F5` (`volatility_baseline_unavailable`) while `F2, F3` remain `"ready"`. | **Eligible (`True`)** for `F2` and `F3` standalone rankers (and `F1, F4` rankers if BTC failed only at `b` rather than a baseline close). | Retained in $N_{\text{planned}}$. Logged under `excluded_health_unverified` with explicit attribution `benchmark_dependency_unavailable (BTC-USD)` so altcoin book health is not conflated with benchmark outage. |

---

### 4. Cohort Choice, Thin-Product Qualification, and Next Validation Check

#### 4A. Declaring the Initial Research Universe Before Outcome Inspection

1. **Two-Tier Preregistered Cohort Architecture (Weighing Complete `F1`–`F5` Core vs. Feature-Specific Diagnostic Cohorts):**
* **Tier 1 — Primary Complete-Vector Core Cohort (`F1`–`F5` Required):** Requires all five features (`F1`–`F5`) and both baselines (`volatility`, `pace`) to be `"ready"` at `(b, t_asof)`.
* *Why this must be the primary study cohort:* Allowing a linear/ordinal ranker to score partial vectors by zero-imputing missing `F2` or `F4` violates the Source 14 guardrail (*"do not insert epsilon/neutral scores to manufacture availability"*) and confounds missingness indicators with directional signal (since `0.0` in `F2` means balanced buy/sell flow during active trading, whereas `nonpositive_pace_median` on AURORA means an inactive hour). Furthermore, fitting separate weights for $2^5 - 1 = 31$ missingness patterns across a small product universe will severely overfit. Under the November 8 pilot evidence, `BTC-USD` (20/20 rows) and `SOL-USD` (20/20 rows) qualify for Tier 1 at 100% of tested cutoffs, while `ALCX-USD` (0/20) and `AURORA-USD` (0/20) have 0% active rows in Tier 1.




* **Tier 2 — Predeclared Feature-Specific Diagnostic & Ablation Cohorts:** Because the study already requires mechanism-specific ablations (Source 14 Section 3, Source 15 Table), predeclare three lower-dimensional diagnostic cohorts that evaluate on every row where their specific inputs and required controls are `"ready"`:
* `Cohort_F3_BookPressure`: Requires `F3 == "ready"` and cutoff spread control (`cutoff_spread_bps` ready). In the pilot, this admits `BTC-USD` (20/20), `SOL-USD` (20/20), `AURORA-USD` (20/20), and `ALCX-USD` (12/20).


* `Cohort_F1_F3_F5_QuoteAndBook`: Requires `volatility == "ready"` and `F1, F3, F5 == "ready"` (plus `current_velocity_sigma` and `raw_signed_180s` controls). In the pilot, this admits `BTC-USD` (20/20), `SOL-USD` (20/20), and `AURORA-USD` (20/20).


* `Cohort_F2_Flow` and `Cohort_F4_Compression`: Evaluated on rows with `F2 == "ready"` or `F4 == "ready"`, respectively (`BTC-USD` and `SOL-USD` in the pilot).




* *Reporting Rule:* All four products (`BTC-USD`, `SOL-USD`, `ALCX-USD`, `AURORA-USD`) stay in the planned inventory $P$ for Tier 1 and Tier 2. Tier 1 is the sole gate for the composite 5-feature ranker; Tier 2 cohorts test individual feature mechanisms across a broader liquidity spectrum without contaminating the 5-feature model.




2. **How a Thin Product Qualifies Later Through a Predeclared, Data-Only Rule:**
Thin products (`ALCX-USD`, `AURORA-USD`, or newly added symbols) must **not** be manually toggled in or out of the study based on single-hour inspection or outcome checks. Instead, apply a **Two-Level Dynamic Data-Only Qualification Rule**:
* **Slot-Level Qualification (Automatic & Causal):** Every 5s cutoff $b$, `build_timed_baseline` and `build_timed_features` evaluate the exact predeclared mathematical gates (`pace_quote_usd_median_30s > 0`, `traded_candles >= 10`, `verified_match_count >= 5`, continuous $\le 10\text{s}$ book age) using data prior to $b$. If `AURORA-USD` enters an active trading regime where at least 61 of the prior 120 30s bins have trades (`pace_quote_usd_median_30s > 0`), at least 10 of the prior 15 minutes have trades (`F4 == "ready"`), and `[b-30s, b)` has $\ge 5$ matches (`F2 == "ready"`), that slot $(p, b, d)$ automatically sets `candidate_eligible = True` and enters Tier 1 for that cutoff—with zero human intervention and zero forward-outcome leakage.


* **Product-Level Stratum Qualification (Proposal for Weight Fitting vs. Monitoring-Only):** To prevent a product that is only eligible on 1% of slots (burst-only selection bias) from distorting pooled discovery weights, predeclare an **Outcome-Blind Discovery Duty-Cycle Minimum (Proposal):** A product in the planned inventory is included in the **pooled weight-fitting sample** only if, across the outcome-blind discovery capture window, it achieves:
1. Passed product-specific feed-side certification ($\ge 100$ paired `ticker`/`match` events with $100\%$ opposite maker/taker side match, **Proposal**), AND
2. Full-vector `candidate_eligible == True` on at least $\theta_{\text{duty}} = 25\%$ of post-warmup cutoffs (**Proposal**, with $10\%$ vs. $50\%$ sensitivity strata).
Products below $\theta_{\text{duty}}$ remain in the coverage/exclusion tables and are evaluated in a separate `"thin_burst_stratum"` out-of-sample, never silently dropped.





---

#### 4B. Smallest Further Outcome-Blind Validation Check

Before freezing the study rules or enabling prospective outcome collection, run **one predeclared, outcome-blind 24-hour multi-session shadow capture** (`instant-batched-24h-readiness-gate-v1`) on the `batched-256` profile.

* **Why One 67-Minute Session Leaves Key Decisions Unsupported:**
1. *Diurnal & Busy-Period Tail Latency:* The November 8 pilot ran from `11:13` to `12:20 UTC` on a Sunday morning (`2026-11-08`, Source 03), recording a queue high-water of `97 / 256` and max proof lag of `1,003ms` (Source 01, 05). A single Sunday hour does not bound weekday US-open burst rates, SQLite `DELETE` + `EXTRA` commit stalls during high-volume cascades, or 24-hour memory/storage growth (67m used `158.1 MiB` of the `240 MiB` soft byte stop in Source 02/05, meaning a multi-hour capture requires segment rotation verification).


2. *Thin-Product Feed-Side Gate:* `ALCX-USD` had only `5` trades and `AURORA-USD` had `4` trades (Source 01, 05), leaving `feed_gate_pass: false`.


3. *Clock Drift Evolution:* Host clock offset against `time.windows.com` drifted from `+1.143..+1.159s` before capture to `+1.285..+1.346s` after 67 minutes (`~165ms/hour` drift in Source 01). Over 24 hours, uncorrected host drift could exceed `3.5s`.


4. *As-Of Offset Tightening:* In the pilot, `ATTEMPT_01.json` only probed `asof_offset_ms` at `0` and `5000`. While `ready_proof_lag_from_cutoff` max was `1,003ms` (proving `1,500ms` would have sufficed for trade windows), `quote_row_processing_incomplete` occurred on 3 BTC probes at `0ms` and `evidence_available_ts_ms` reached `+897ms` on `F2`. Evaluating multi-point offsets (`1500ms`, `2500ms`, `5000ms`) across 24 hours is required before locking $\Delta_{\text{asof}}$ and $\Delta_{\text{pub\_max}}$.




* **Smallest Outcome-Blind Validation Protocol (3 x 67-Minute Stratified Captures or 1 Segmented 24h Run, Zero Outcome Calculation):**
If segment rotation beyond `240 MiB` is not yet in scope, run **three predeclared, isolated 67-minute `batched-256` captures** across distinct market regimes (Session A: US equity open `14:00–15:07 UTC`; Session B: Asia open `00:00–01:07 UTC`; Session C: European open `07:00–08:07 UTC`), logging coverage probes at offsets `{0ms, 1500ms, 2500ms, 5000ms}` and running `prepare_decision` at the candidate offset.
* **Pass Conditions (Proposal):**
* Zero queue overflows (`sampled_high_water < 256`, `pending_ingress_frames == 0`, `journal_quick_check == "ok"` across all 3 sessions).
* At the selected $\Delta_{\text{asof}}$ (`1,500ms` candidate or `5,000ms` fallback), $\ge 99.5\%$ of `BTC-USD` and `SOL-USD` probes have `trade_window == "ready"` and `quote == "ready"`.
* $\ge 99.5\%$ of eligible cohorts complete `commit_observed_ts_ms <= b + delta_pub_max`.
* Across cumulative paired `ticker`/`match` frames, $100\%$ have opposite maker/taker sides, with $\ge 100$ cumulative paired matches per product required to certify a product's feed gate.


* **Fail Conditions:**
* Any `batched-256` queue overflow (`sampled_high_water >= 256`), SQLite corruption, or digest mismatch.
* Any single paired `ticker`/`match` frame showing identical (non-opposite) side attribution (`opposite < paired`).
* Proof lag p99 $> \Delta_{\text{asof}}$ on liquid core products (`BTC-USD`, `SOL-USD`).


* **Inconclusive Conditions:**
* Transport disconnect before reaching the 62-minute warmup cutoff (requires predeclared reconnect/retry rule, not silent discard).
* Zero side-attribution errors on `ALCX-USD` / `AURORA-USD`, but cumulative paired trade count across the 3 sessions remains $< 100$ (certifies the feed gate for `BTC-USD` and `SOL-USD` so they can advance, while keeping `ALCX-USD` / `AURORA-USD` in the `unverified_thin_feed` coverage stratum).





---

#### 4C. Status Matrix Across the Four Readiness Gates

| Gate | Current Status After Nov 8 Pilot (`17b87ac` / `c9d79be`) | What the Nov 8 Pilot Established | What Remains Open / Unsupported by One Session |
| --- | --- | --- | --- |
| **1. Engineering Feasibility** | **Demonstrated for Single 67m Session** (`batched-256`) | Fixed the Nov 7 `single-128` overflow (`97/256` high-water) and pre-ack snapshot bug (`seq 3` ALCX book accepted); verified 166,035 packet digests, 80 outbox digests, `57.1ms` median decision prep, and `100%` local consumer delivery within `5.678s` (including `5s` offset).

 | Multi-session busy-period stability (US open burst rates), segment rotation past the `240 MiB` / `250,000`-packet soft stop, and host NTP clock-drift bounding (`~165ms/hr` drift observed in Source 01).

 |
| **2. Full Feed Certification** | **Inconclusive (`feed_gate_pass: false`)** | Paired `11,175` BTC and `2,354` SOL trades with `100%` opposite ticker/match sides, plus `4,017–4,019` strict verified 1s intervals per product (Source 01, 05).

 | Thin-product side sample had only `5` ALCX and `4` AURORA trades (Source 01, 05); scoped receipt-ID watermark proofs verify interval continuity within a connection epoch, not full-exchange cross-channel certification.

 |
| **3. Eligibility for Prospective Outcome Collection** | **Blocked Pending Policy Freeze & Adapter (`eligibility_producer_implemented: false`)** | Confirmed that `build_timed_baseline`, `build_timed_features`, and `prepare_decision` deterministically classify all 80 product $\times$ cutoff $\times$ direction rows with explicit missingness reasons and evidence timestamps.

 | Requires: (a) implementing the versioned delayed-decision adapter for `exposure_report` (resolving C1 `available_ts_ms > b`); (b) locking $\Delta_{\text{asof}}$ and $\Delta_{\text{pub\_max}}$; and (c) passing the multi-session outcome-blind check. |
| **4. Readiness to Fit and Validate** | **Strictly Off (`fitting_allowed: false`, `study_frozen: false`)** | Zero outcomes were evaluated and zero weights were fitted (`CHECKS.json`, Source 04).

 | Requires completing $\ge 14$ valid shadow days of prospective collection after study freeze (with 60m purge, mature 300s/900s labels, frozen ranker roster, cooldowns, and predeclared power/extension rules per Source 14 & Source 15 Step 5).

 |
