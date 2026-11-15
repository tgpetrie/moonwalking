# Elliott Wave / ABC Engine — Local Audit & v2 Calibration Notes (2026-11-15)

## 1. Local Formal Code Audit (`bonsai-2:27b` on `backend/elliott_wave_engine.py`)

### Causality & Non-Repainting Verification
* **Strictly Causal (`Zero Lookahead`):** Verified across `_atr_series`, `_zigzag`, `confirm`, `_extreme`, `_after`, and `resample_candles`. Every calculation at bar `i` reads only `0..i`. Passing `candles[:k+1]` produces the exact prefix of pivots confirmed at or before bar `k` close.
* **Trend-Relative (`q = sgn * price`) Symmetry:** Wave B retracement (`0.236 <= b_ret < 1.0`), Wave C Fibonacci target zone (`0.618` to `1.618` of Wave A projected from Wave B, floored at prior origin `qo`), and confluence factors (`RSI(14)`, `MACD`, `Volume contraction <= 0.85`, `Bollinger reclaim`, `EMA(9) reclaim`) hold symmetrically for both bullish (`sgn = +1`) and bearish (`sgn = -1`) structures.

### Minor Edge Cases Flagged for v2 Engine Polish
1. **Prior Impulse Slice Overlap (`_abc_complete` / `_abc_in_progress`):** `pre = pivots[:-3]` (complete) and `pivots[:-2]` (in-progress) overlap with `o` and `p0` of the ABC tail. Slicing `pivots[:-5]` and `pivots[:-4]` cleanly separates the preceding 6-pivot impulse from the ABC correction.
2. **In-Progress Wave 5 Tie Rejection (`_impulse`):** `after[1] - q[4] >= len3` when `len3 < len1` rejects an in-progress Wave 5 when `len5 == len3`, whereas the Elliott rule only prohibits Wave 3 from being *strictly* the shortest (`len3 < len1 and len3 < len5`). Changing `>=` to `>` aligns the in-progress check with `_impulse_ok`.
3. **Redundant `max()` in `_c_zone`:** `ext_a = max(floor, qb - 1.618 * a_len)` simplifies to `floor` since `floor = max(qo, qb - 1.618 * a_len)`.
4. **Impulse Confidence Ceiling:** `_impulse` only evaluates `_higher_tf_factor` (max weight `0.30`), capping active 5-wave impulse confidence at `0.4 * 1.0 + 0.6 * 0.30 = 0.58` (`"medium"`).

---

## 2. Diagnostic Findings on the v1 Walk-Forward Run (`RESULTS.json`)

### Why Part A (`1h/bullish/complete`) Was Underpowered (`n_confluence = 17`)
* **`factor_states` Breakdown (`1h/bullish/complete`, `n = 133`):**
  * `higher_tf_trend`: `{'opposed': 101, 'present': 20, 'absent': 12}` — 75.9% of 1h bullish ABC pullbacks pulled price below the 4h `EMA(20)` at Wave C, incurring a `-0.30` penalty that blocked confluence (`<= 0.40 < 0.50`).
  * `prior_impulse`: `{'absent': 132, 'present': 1}` — requiring 6 prior ZigZag pivots to satisfy all hard 5-wave rules fired on `< 1%` of setups.
* **`factor_states` Breakdown (`1h/bullish/zone`, `n = 336`):**
  * `ema_reclaim`: `{'absent': 330, 'present': 6}` — `walk_events` triggered `zone` on the very first falling bar entering the C-zone and locked the key in `seen`, preventing triggers on the subsequent reclaim/turn bar.
* **Pooled `1h/all/complete` (`bullish + bearish`, `atr_mult = 2.2`):**
  * Pooling both directions on the unmodified v1 engine yields `n = 271` (`>= 100`) and `n_confluence = 83` (`>= 50`, `status = "read"`), where confluence beats non-confluence on 24h target hit rate by **`+18.61` percentage points (`[+0.59%, +31.22%]`, 95% block-bootstrap lower bound `> 0`)** (`59.0%` vs `40.4%`) and **`+0.326 R`**.

---

## 3. v2 Candidates for Sealed Post-Nov 13 Confirmation

### Candidate A: Wave C Zone Reclaim Trigger (`1h/bullish/reclaim`)
* **Mechanism:** Wait for Wave C to enter the `[0.618, 1.618]` Fibonacci zone and trigger on the first turn/reclaim bar closing in the trend direction (`close > open` and `close > prev_close` with `ema_reclaim`, `bollinger_reclaim`, or prior-bar C extreme), placing the stop `0.15%` beyond the Wave C extreme and target at Wave B.
* **Confluence Rule:** Require non-opposing 4h trend (`higher_tf_trend != "opposed"`) plus multi-factor local confirmation (excluding unconfirmed in-zone MACD histogram divergence, which exhibited negative selection on slow bleed-downs).
* **In-Sample Performance (Oct 13 – Nov 12, 2026):**
  * `n = 262` (`>= 100`), `n_confluence = 65` (`>= 50`), **`status = "read"`**, **`confluence_beats_random_placebo = True`**.
  * **Median Planned Reward-to-Risk:** **`2.50:1`** (vs `0.88:1` on `complete`).
  * **24h Target Hit Rate vs. Random Placebo:** **`+16.1` percentage points (`[+4.3%, +32.6%]`)**.
  * **24h Return (`R_24h`) vs. Random Placebo:** **`+0.539 R` (`[+0.145 R, +1.138 R]`)**.

### Candidate B: 1h Structure Conditioning on 3m Gainers (`1h_abc_clean`)
* **Mechanism:** Condition `confirmation_3m_up/up` (`A1` dollar-gated flags) on aligned `1h` live ABC structure while vetoing 15m/1h/4h `impulse_complete` blow-off tops (which suffered an `18.26%` crasher rate on 1h) and opposing `15m` ABC resistance.
* **In-Sample Performance (Oct 13 – Nov 12, 2026):**
  * **`flags = 549`** (`34` runners, `39` crashers).
  * **Runner Lift (`dP`):** **`+3.83` percentage points** over A1.
  * **Crasher Change (`dC`):** **`-0.20` percentage points** vs A1.
  * **Net Daily Improvement (`dN`):** **`+4.04` points (`[-1.14, +9.38]`)**, positive in both halves of the month (**`H1 = +7.04`**, **`H2 = +1.22`**, `same_sign_in_both_halves = True`).
