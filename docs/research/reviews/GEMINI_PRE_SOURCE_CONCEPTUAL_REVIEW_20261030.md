**Source Inspection & Availability Disclosure**
No repository files could be directly inspected. The repository (`[https://github.com/tgpetrie/moonwalking](https://github.com/tgpetrie/moonwalking)`), both commits (`941f47a` and `cb7034a`), and the five specified files (`docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md`, `docs/research/INSTANT_TARGET_CONTRACT_V1.json`, `docs/research/INSTANT_TARGET_LABELS_20261029.md`, `scripts/scoring_experiment/instant_targets.py`, and `tests/test_instant_targets.py`) are unavailable via public web index or workspace context. Consequently, this review evaluates the architectural contract, target properties, and F1–F5 feature designs as explicitly parameterized in your specification against the mathematical requirements of a true early-warning system.

---

## 1. Target Definition & Measurement Assessment

### 1. Activity-Confirmed Velocity Crossing vs. Physical Beginning of a Move

Defining "onset" ($t_{\text{onset}}$) via an activity-confirmed velocity crossing conflates the **confirmation** of a regime change with its **physical initiation** ($t_{\text{start}}$). By the time 30s or 180s price velocity and trade activity cross a fixed threshold, the initial liquidity absorption and microstructure inflection have already occurred.

* **Measurement Distortion:** Using $t_{\text{onset}}$ as the temporal anchor shifts the target forward in time. A model trained to predict $t_{\text{onset}}$ is rewarded for anticipating threshold crossings, whereas a model evaluated *at* $t_{\text{onset}}$ is performing mid-move continuation filtering, not early-warning discovery.
* **Structural Fix:** Retain $t_{\text{onset}}$ strictly as an event *trigger* to identify candidate episodes, but define a separate physical origin $t_{\text{start}} \le t_{\text{onset}}$ by looking backward from $t_{\text{onset}}$ to the last local extremum or volatility-compression boundary prior to the directional impulse.

### 2. Breakout Measured from Crossing with a 180-Second Deadline

Measuring the breakout excursion relative to the price at $t_{\text{onset}}$ ($P(t_{\text{onset}})$) within a 180s window ($[t_{\text{onset}}, t_{\text{onset}} + 180\text{s}]$) penalizes moves that expended their sharpest impulse *triggering* the onset threshold.

* **Measurement Distortion:** If a coin surges rapidly over 20 seconds to trip the velocity/activity gate and then consolidates slightly before continuing over 5m/15m, measuring breakout strictly from $P(t_{\text{onset}})$ within 180s understates the move's true magnitude and risks misclassifying clean impulsive moves as failed breakouts. Conversely, late-stage exhaustion spikes that barely trip the gate and reverse at +185s may pass a naive excursion check if not paired with retention.

### 3. No-Retracement Requirement Through the Entire 5m/15m Horizon

Requiring strictly zero retracement (e.g., never breaching $P(t_{\text{onset}})$ or a tight drawdown floor across the full 300s or 900s window) creates severe survivorship bias against volatile, high-beta microstructure moves.

* **Measurement Distortion:** In live order books, genuine impulsive breakouts frequently experience rapid liquidity vacuum pullbacks (e.g., retracing 30%–50% of the initial 30s spike to test the breakout level) before resuming trend over 5m and 15m. A hard binary no-retracement constraint across the full horizon relabels legitimate multi-wave trends as negatives (`0`), forcing the target to select only low-volatility, monotonic drifts rather than explosive radar movers.
* **Structural Fix:** Replace binary zero-retracement over 5m/15m with a continuous **Maximum Adverse Excursion (MAE)** bound scaled to pre-onset volatility, or evaluate path retention via time-weighted average price (TWAP) relative to the onset baseline rather than single-tick minimum/maximum bounds.

### 4. Signed, Market-Relative Magnitude, Retention, and Fraction Consumed

* **Signed & Market-Relative Magnitude:** Essential. Measuring returns net of a synchronous market benchmark ($\Delta r_{i,\text{rel}} = r_i - \beta_i r_m$ or cross-sectional median return) prevents the target from labeling passive beta sweeps during BTC/ETH volatility shocks as coin-specific breakouts.
* **Retention:** Comparing terminal 5m/15m net return to peak excursion ($\text{Retention} = \frac{\Delta P_{\text{terminal}}}{\Delta P_{\text{max}}}$) properly separates sustained repricing from transient pump-and-dump spikes or single-print fat fingers.
* **Fraction Consumed:** Measuring how much of the total 5m/15m move already occurred prior to $t_{\text{onset}}$ ($\text{Consumed} = \frac{P(t_{\text{onset}}) - P(t_{\text{start}})}{P(t_{\text{peak}}) - P(t_{\text{start}})}$) is critical for auditing whether the radar is firing early enough to be actionable. However, if $t_{\text{start}}$ is not tracked independently of $t_{\text{onset}}$, "fraction consumed at onset" collapses to zero by definition, blinding the evaluation to late triggers.

### 5. Separation of Prediction Before Onset from Detection Afterward

An early-warning radar operates across two distinct regimes that must never be pooled in evaluation:

* **Pre-Onset Prediction ($t < t_{\text{onset}}$):** Evaluates whether features observed during quiet or early accumulation phases predict that a valid onset + sustained 5m/15m move will occur within the next $\Delta t$ seconds.
* **At/Post-Onset Continuation ($t \ge t_{\text{onset}}$):** Evaluates whether an already-triggered velocity/activity spike will achieve breakout and 5m/15m retention rather than mean-reverting.
Pooling samples from $t < t_{\text{onset}}$ and $t \ge t_{\text{onset}}$ contaminates lead-time metrics and inflates apparent classification power via post-trigger momentum.

### 6. Event Deduplication, Missed-Move Coverage, and Unknown Data Exclusion

* **Event Deduplication:** Continuous sliding evaluation generates clusters of overlapping triggers for a single physical move. Without cooldown locking or episode coalescing (grouping contiguous crossings into a single event anchored at the *first* valid trigger), high-duration moves dominate the loss function and violate sample independence.
* **Missed-Move Coverage (False Negatives of the Onset Gate):** If labels are only generated when the activity-confirmed velocity crossing fires, any clean 5m/15m market-relative move that accelerates smoothly *below* the instantaneous velocity/activity threshold is invisible to the dataset. The target denominator must include **unconditional horizon movers** across all eligible coins (including coins that never enter a board), otherwise the system only measures precision among threshold crossings and ignores recall against total market opportunity.
* **Exclusion of Unknown Data:** Stale BBO quotes, websocket disconnects, or missing match buckets must be explicitly masked (`NaN` / excluded from both numerator and denominator) rather than forward-filled as zero velocity or zero participation. Forward-filling missing ticks creates artificial compression (corrupting F4) followed by synthetic jump velocity upon reconnection (corrupting F1/onsets).

---

## 2. Circularity Analysis: Onset Definition vs. F1/F2 Evaluation

### The Mechanism of Circularity

If target onset $t_{\text{onset}}$ is defined by a rule of the form:


$$\text{Onset}(t) = \mathbb{I}\left(\vert{}\text{Velocity}_{30\text{s/180s}}(t)\vert{} > \tau_v \;\land\; \text{Activity}_{30\text{s/180s}}(t) > \tau_a\right)$$


and the candidate predictors include **F1 (midpoint acceleration)** and **F2 (match-derived signed participation and pace)** computed over the same 30s/180s windows, **algebraic coupling** occurs:

1. **Unconditional Pool Inflation:** In a full-universe panel (all eligible ticks across all coins), F1 and F2 are direct mathematical components or first differences of the exact variables gating $Y=1$. Therefore, F1 and F2 will show massive unconditional ROC-AUC / PR-AUC simply because $Y=1$ *cannot exist* unless velocity and activity are already elevated.
2. **Range Restriction & Berkson's Paradox (Conditional Pool):** Conversely, if evaluation is restricted strictly to $t = t_{\text{onset}}$, both F1 and F2 are truncated from below by $\tau_v$ and $\tau_a$. Conditioning on a collider (the threshold crossing) distorts the covariance between F1, F2, and subsequent 5m/15m continuation.

### How to Evaluate Predictive Contribution Without Circular Advantage

To isolate true predictive value from definitional overlap, apply four strict separation protocols:

1. **Temporal Lead-Lag Separation (Pre-Onset Horizon):**
Evaluate F1–F5 strictly at $t \le t_{\text{onset}} - \delta$ (e.g., $\delta \in \{15\text{s}, 30\text{s}, 60\text{s}\}$ prior to the crossing) against an onset-free baseline of quiet market ticks matched on time-of-day and liquidity tier. At $t_{\text{onset}} - \delta$, the threshold condition has *not* yet been satisfied, removing deterministic truncation.
2. **Onset-Gate Conditioning (Post-Trigger Continuation Baseline):**
When evaluating at $t = t_{\text{onset}}$, define the binary target solely as **conditional outcome success**: $Y_{\text{cond}} = \mathbb{I}(\text{Breakout}_{180\text{s}} \land \text{Retention}_{5\text{m}/15\text{m}} \mid \text{Onset}=1)$. Set the null baseline model to include the exact onset velocity and activity values ($V_{\text{onset}}, A_{\text{onset}}$). F1 and F2 earn credit *only* for their partial deviance reduction / log-loss improvement above the $(V_{\text{onset}}, A_{\text{onset}})$ baseline.
3. **Onset-Free Outcome Labeling (Total Recall Audit):**
Construct an auxiliary ground-truth label $Y_{\text{pure}}$ defined purely by future 5m and 15m market-relative return and path retention from $t_0$, *without* requiring a prior velocity/activity onset crossing. Evaluate F1–F5 directly against $Y_{\text{pure}}$ across all eligible coins to measure how much real move discovery is captured vs. missed by the onset gate itself.
4. **Orthogonal Residualization:**
Project F1 (second derivative / acceleration) and F2 (signed flow imbalance) onto the raw unsigned activity and first-order velocity used in the onset rule, and test the predictive power of the orthogonal residuals.

---

## 3. Candidate Mechanism Review (F1–F5)

### Evaluation Architecture: Standalone vs. Marginal Contribution & Confounders

Before interpreting the feature matrix below, all five mechanisms must be governed by a unified statistical testing structure:

* **Standalone vs. Conditional (Marginal) Value:** Each feature must be tested twice: first in isolation (plus liquidity/market controls) to verify its physical mechanism, and second via **drop-one ablation** from the full F1–F5 specification (and sequential step-in addition) to prove it adds non-redundant conditional mutual information. For example, F1 (midpoint acceleration) often proxies F2 (aggressive order flow) and F5 (relative velocity); F1 only justifies inclusion if it improves out-of-sample log-loss or top-$K$ precision after F2, F3, F4, and F5 are already in the model.
* **Universe Coverage (Non-Board Coins):** Evaluation panels must retain all eligible coins at every timestamp—including dormant or mid-tier coins that never enter a top-mover board—to compute valid false-positive rates and missed-move denominators.
* **Liquidity Stratification:** Microstructure mechanics differ sharply between deep books and thin books. All hypotheses must be stratified by rolling baseline quote depth / dollar volume (e.g., terciles) so a feature that merely flags illiquid tick-jumping is not mistaken for an alpha signal.
* **Market-Wide Shocks:** During synchronous market sweeps, F1, F2, and F3 trigger simultaneously across dozens of coins. Models must either condition on cross-sectional market state or evaluate F1–F4 strictly against **market-relative** outcomes (separating beta spillover from idiosyncratic alpha).
* **Dependent Observations:** Overlapping 30s/180s feature windows and 5m/15m outcome horizons induce severe serial and cross-sectional autocorrelation. Standard errors, $p$-values, and ablation differences must use **two-way cluster-robust covariance** (clustered by `coin_id` and `timestamp_bucket` / episode) or block-bootstrapping across non-overlapping time blocks.

### Feature Evaluation Matrix

| Feature | Precise Hypothesis | Expected Behavior (Up vs. Down) | Timing Relative to Onset | Appropriate Baseline / Ablation | Supporting Evidence | Rejecting Evidence | Inconclusive Evidence | Data-Quality Checks & Major Confounders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **F1: Midpoint Acceleration** | Positive second-order rate of change in midpoint price ($\frac{v_{30\text{s}} - v_{180\text{s}}}{\Delta t}$) indicates convex urgency that increases the probability of a sustained 5m/15m market-relative move beyond first-order velocity alone. | **Up:** $v_{30\text{s}} > v_{180\text{s}} > 0$ (convex upward ramp).<br>

<br>**Down:** $v_{30\text{s}} < v_{180\text{s}} < 0$ (convex downward plunge).<br>

<br>Symmetric in magnitude along move sign $s \in \{+1, -1\}$. | Primarily **near or at onset** ($t \approx t_{\text{onset}}$); weak early lead ($t \ll t_{\text{onset}}$) except when transitioning out of F4 compression. | **Baseline:** Raw 30s and 180s velocity levels ($v_{30\text{s}}, v_{180\text{s}}$) + liquidity tier.<br>

<br>**Ablation:** Full model `[F1..F5]` minus `F1` (specifically testing overlap with F2 pace and F5 relative return). | Statistically significant reduction in out-of-sample log-loss and gain in PR-AUC for 5m/15m retention when added to $(v_{30\text{s}}, v_{180\text{s}}, \text{F2}, \text{F5})$, confirmed across liquidity strata. | Acceleration shows negative or zero marginal lift over first-order velocity, or correlates positively with post-onset mean reversion (exhaustion blow-offs). | Standalone association is positive, but marginal lift over F2 + F5 has cluster-robust confidence intervals spanning zero due to collinearity with onset velocity. | **Checks:** Verify midpoint is not skewed by one-sided stub quotes or wide-spread vacuums; check timestamp monotonicity.<br>

<br>**Confounders:** Tick-size granularity on low-priced coins; spread widening masquerading as midpoint drift. |
| **F2: Match-Derived Signed Participation & Pace** | High trade arrival pace combined with one-sided aggressor flow (taker buy vs. sell volume imbalance over 30s vs. 180s baseline) reveals informed liquidity consumption that precedes and sustains price displacement. | **Up:** Net positive signed volume imbalance (taker buys $\gg$ taker sells) + elevated trade count/notional pace.<br>

<br>**Down:** Net negative signed volume imbalance (taker sells $\gg$ taker buys) + elevated pace. | **Both before and at onset:** Order flow absorption against resting limit orders appears before midpoint breaks out ($t < t_{\text{onset}}$) and confirms genuine participation at $t \ge t_{\text{onset}}$. | **Baseline:** Unsigned volume/trade count (onset activity gate) + F1 velocity.<br>

<br>**Ablation:** Full model `[F1..F5]` minus signed imbalance component, and minus F2 entirely. | Signed participation predicts onset before price crosses $\tau_v$, and conditional on onset, separates sustained 5m/15m trends from low-volume vacuum spikes above unsigned activity. | Signed flow adds no predictive lift over unsigned trade pace, or heavy one-sided volume marks local exhaustion tops/bottoms that fail the 5m/15m retention rule. | Works in aggregate but fails when stratified by liquidity tier, or clusters entirely within a few market-wide liquidation cascades where degrees of freedom are too small. | **Checks:** Audit trade-sign inference (exact exchange maker/taker flag vs. tick-rule fallback); handle bundled batch prints.<br>

<br>**Confounders:** Wash trading, automated iceberg replenishment, and cross-exchange arbitrage sweeps. |
| **F3: Sampled BBO Pressure & Spread** | Persistent top-of-book depth imbalance ($\frac{Q_{\text{bid}} - Q_{\text{ask}}}{Q_{\text{bid}} + Q_{\text{ask}}}$) paired with tight or tightening relative spread indicates directional queuing pressure and low friction for continuation. | **Up:** Bid-heavy BBO imbalance ($>0$) with compressed or stable spread (or rapid ask depletion).<br>

<br>**Down:** Ask-heavy BBO imbalance ($<0$) with compressed or stable spread (or rapid bid depletion). | **Strictly before onset ($t < t_{\text{onset}}$)** for early warning; **at onset**, spread behavior switches from predictive trigger to liquidity-vacuum filter (filtering out illiquid air-pockets). | **Baseline:** Historical coin-specific spread median + F2 match flow.<br>

<br>**Ablation:** Full model `[F1..F5]` minus `F3`. | Pre-onset BBO pressure improves lead-time recall at $t_{\text{onset}} - 30\text{s}$, or spread filtering at onset eliminates false breakouts that fail 5m/15m retention without cutting true positives. | BBO imbalance is inverted (spoofing/passive absorption where large visible size opposes the true move) or noisy under discrete sampling, yielding zero marginal lift over F2. | BBO imbalance shows weak standalone correlation at 30s windows, or sampling cadence misses sub-second book updates, leaving confidence bounds wide and overlapping zero. | **Checks:** Verify BBO snapshot sampling frequency and staleness; remove crossed/locked book artifacts.<br>

<br>**Confounders:** Spoofing/flickering quotes, L1-only visibility hiding L2/L3 liquidity walls, and minimum tick-size spread floors. |
| **F4: Compression Followed by Expansion** | A regime of abnormally low 180s price range/volatility and quiet spread (compression) transitioning into a 30s volatility/range breakout (expansion) yields higher 5m/15m follow-through than moves launching from already-choppy states. | **Direction-agnostic amplifier** (unsigned regime multiplier interacting with sign of F1/F2/F5): Low 180s dispersion followed by sharp +30s expansion for **Up**, or sharp -30s expansion for **Down**. | **Pre-onset setup ($t < t_{\text{onset}}$)** establishes compression; **transition into onset ($t \approx t_{\text{onset}}$)** marks expansion. | **Baseline:** Unconditional 30s volatility/velocity without normalizing by 180s pre-state.<br>

<br>**Ablation:** Full model `[F1..F5]` minus `F4` (testing interaction terms $\text{F4} \times \text{F1}$ and $\text{F4} \times \text{F2}$). | Conditioning on high $\frac{\text{Range}_{30\text{s}}}{\text{Range}_{180\text{s}}}$ (with genuinely active trading, not dead feeds) increases 5m/15m retention rate and reduces retracement failures relative to unconditioned velocity spikes. | Moves originating from prior compression show no better retention than continuation moves in already-volatile regimes, or compression simply selects illiquid dead coins. | Positive lift appears in raw data but vanishes once dead-tick periods (zero-trade stasis) and time-of-day diurnal volatility cycles are controlled for. | **Checks:** Crucial check to distinguish active tight consolidation (trades occurring within narrow band) from feed dropouts or zero-trade illiquidity.<br>

<br>**Confounders:** Stablecoins/pegged assets, low-activity overnight sessions, and denominator explosions when $\text{Range}_{180\text{s}} \to 0$. |
| **F5: Market-Relative Movement** | Idiosyncratic price displacement over 30s/180s decoupling from the simultaneous cross-sectional market return ($r_i - r_m$) isolates genuine coin-specific catalysts that persist over 5m/15m, whereas pure market-beta moves mean-revert or offer no cross-sectional edge. | **Up:** Coin 30s/180s return significantly exceeds synchronous market median/benchmark return ($\Delta r_{\text{rel}} > 0$).<br>

<br>**Down:** Coin 30s/180s return significantly underperforms market benchmark ($\Delta r_{\text{rel}} < 0$). | **Both before onset** (early relative strength/weakness during market dips/rallies) **and at onset** (filtering out broad market beta flushes). | **Baseline:** Raw unadjusted coin return ($r_i$) + F1.<br>

<br>**Ablation:** Full model `[F1..F5]` minus `F5` (or replacing market-adjusted features with raw unadjusted features). | Replacing or augmenting raw velocity with market-relative velocity improves 5m/15m cross-sectional rank correlation (IC) and suppresses false radar floods during BTC/ETH volatility spikes. | Market-relative adjustment degrades 5m/15m target prediction because synchronous beta cascades actually exhibit higher continuation than idiosyncratic moves under the target definition. | During low-volatility market regimes ($r_m \approx 0$), F5 is collinear with F1 ($r_i - r_m \approx r_i$), leaving insufficient high-dispersion market events in the sample to separate F5 from F1. | **Checks:** Verify timestamp synchronization across all universe coins when computing benchmark $r_m$; ensure no lookahead leak in cross-sectional median.<br>

<br>**Confounders:** Differing beta sensitivities ($\beta_i \neq 1$), lead-lag effects where illiquid alts react to BTC with a 10s–60s delay. |

---

## 4. Final Verdict & Required Actions

### Verdict on Target Alignment

**Partially Aligned (Conditional Continuation Matches; Early-Warning Discovery Does Not).**
As specified, the implemented target architecture measures **post-trigger momentum continuation**, not **pre-onset early warning**. Because onset is anchored to an activity-confirmed velocity crossing, Breakout is measured forward from that crossing, and retracement is strictly forbidden across 5m/15m:

1. The system evaluates whether an already-moving coin keeps moving monotonically, rather than predicting a move before it becomes obvious.
2. Features F1 and F2 enjoy a built-in definitional advantage in any unconditional evaluation because they mirror the onset gate.
3. The strict zero-retracement rule over 5m/15m rejects genuine high-volatility breakouts that experience normal microstructure pullbacks.

### Ranked Corrections Needed Before Prospective Outcome Analysis

1. **Decouple Evaluation Pools into Pre-Onset (Lead) vs. Conditional Post-Onset (Continuation):**
* *Measurement Problem Fixed:* Eliminates the circularity between the velocity/activity onset trigger and F1/F2, and stops post-trigger momentum from masquerading as early-warning lead time.


2. **Add an Unconditional Horizon-Mover Audit Across All Eligible Coins (Including Non-Board Coins):**
* *Measurement Problem Fixed:* Measures false negatives of the onset gate itself. Without tracking coins that achieve 5m/15m market-relative displacement *without* tripping the exact 30s/180s onset threshold, total recall is unmeasurable.


3. **Anchor "Fraction Consumed" and Move Magnitude to Physical Initiation ($t_{\text{start}}$) in Addition to $t_{\text{onset}}$:**
* *Measurement Problem Fixed:* Measuring breakout solely from $P(t_{\text{onset}})$ ignores the portion of the impulse spent tripping the threshold, penalizing fast initial surges and hiding how late the trigger fired.


4. **Replace Binary Zero-Retracement over 5m/15m with Volatility-Scaled Maximum Adverse Excursion (MAE) or TWAP Retention:**
* *Measurement Problem Fixed:* Prevents normal order-book pullbacks and retests from mislabeling sustained 5m/15m trends as failures (`0`), removing bias toward slow, low-volatility drifts.


5. **Enforce Episode Coalescing / Cooldown Locking and Two-Way Clustered Inference:**
* *Measurement Problem Fixed:* Prevents a single sustained 15-minute move or a single market-wide BTC shock from generating hundreds of correlated tick-level observations that artificially shrink standard errors and over-weight long-duration episodes.



### Definitions That Must Be Frozen Before Data Collection or Model Fitting

Before running prospective scoring or fitting any weights on incoming data, freeze the following exact specifications in the versioned contract:

* **Eligible Universe & Non-Board Inclusion Rule:** The exact minimum rolling dollar-volume, price floor, and listing-age criteria that define an "eligible coin" at timestamp $t$, evaluated identically whether the coin is on a display board or not.
* **Market Benchmark Construction ($r_m$):** Whether market-relative adjustments (in both the target and F5) use the cross-sectional equal-weighted median of eligible coins, a volume-weighted index, or a beta-adjusted BTC/ETH reference, along with exact synchronization tolerances.
* **Missing-Data & Staleness Masking Rules:** The exact millisecond threshold after which an unchanged BBO or empty match window is flagged as `UNKNOWN`/`STALE` (e.g., websocket drop vs. genuine quiet book) and excluded from F4 compression and target labels.
* **Episode Coalescing Window ($\Delta t_{\text{cooldown}}$):** The exact refractory period (e.g., 300s or 900s matching the outcome horizon) during which subsequent velocity crossings on the same coin are merged into the active episode rather than scored as independent events.
* **Regularization Floors for Ratios (F3 & F4):** The exact epsilon ($\epsilon$) or baseline volatility floor added to the denominator of F4 ($\text{Range}_{180\text{s}}$) and F3 spread normalization so zero-range stasis in low-tick-size assets does not produce infinite feature values.
