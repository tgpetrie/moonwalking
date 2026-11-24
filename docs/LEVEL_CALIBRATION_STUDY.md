# Level and Stop Parameter Calibration Study

Date: 2026-09-08
Status: Complete. Findings are actionable; no parameter was fitted.
Scope: the constants in `backend/position_levels.py`, `backend/sell_side_intelligence.py`,
and `backend/entry_signal_intelligence.py`.

## Why this study exists

Every threshold in the level stack was chosen by feel: the `0.20 x ATR` support
buffer, the `0.10 x ATR` limit gap, `ATR(14)`, the 49-candle window, the
`1.5x` volume gate, and the `15 / 85` range-position bands. `MW_SPEC.md` forbids
random thresholds and silent tuning, and `MW_BACKLOG.md` P2.5 requires
evidence-based thresholds rather than values tuned by feel. This study asks a
narrow question: **do those numbers do what the product says they do?**

It deliberately does not ask "what values maximise returns." Section 5 explains
why that question cannot be answered honestly with the data available.

## Method

- **Data**: 320,325 decision points. 40 Coinbase USD spot pairs ranked by
  24h quote turnover, ~8,750 completed 1-hour candles each, 362 days ending
  2026-09-08, pulled from `api.exchange.coinbase.com` in 300-candle pages.
- **Exact replication**: the study reimplements `compute_levels` and
  `build_sell_plan` verbatim, including the simple-mean ATR (the shipped `_atr`
  averages the last 14 true ranges rather than applying Wilder smoothing) and
  the shipped `volume_ratio` definition (latest candle over the median of the
  prior window).
- **No look-ahead**: at each decision point the window is the 49 completed
  candles, and the "live quote" is the OPEN of the first not-yet-completed
  candle. This mirrors what the route actually sees.
- **Forward horizon**: 24 hours, matching `sell_plan_outcomes.py`.
- **Inference**: stationary block bootstrap (Politis-Romano) over **time**, in
  72-hour blocks, where a block contains all 40 coins at those hours. Coins
  moving together in the same hour are close to one observation, not forty; see
  section 5.

## 1. Findings that are mechanical, certain, and fixable

These do not depend on any market hypothesis. They are statements about whether
the code does what its own labels claim.

### 1.1 The "structure broken" test can never be true

```
P(price <= structure_support)   measured over 320,325 points : 0.000000
P(price <= support)             the honest test              : 0.002572
```

`structure_support` is assigned `support if support < price else band_low`, so
it sits below `price` by construction. Any later test of `price <= structure_support`
is dead code. This affects the `Invalidated - wait` branch in
`entry_signal_intelligence.py`, which can currently only fire from a live signal
warning, never from broken structure. **Fix: test against the measured `support`.**

### 1.2 The 0.20 x ATR buffer is not a buffer

Its stated purpose is to sit far enough below support that ordinary noise does
not trip it. Measured against real penetrations of the 49-hour low:

```
P(price dips below the 49h support within 24h)      0.383   CI [0.344, 0.420]
penetration depth below support, in ATR units:
  q25 0.82   q50 1.84   q75 3.46   q90 5.93   q95 8.44
  P(depth <= 0.20 ATR | dipped)   0.067      <-- 93.3% of penetrations exceed it
  P(depth <= 1.00 ATR | dipped)   0.301
  P(depth <= 2.00 ATR | dipped)   0.531
```

The median penetration is **1.84 ATR, roughly nine times the buffer**. This
matches the directional-change scaling law (Glattfelder, Dupuis & Olsen,
*Quantitative Finance*, 2011; arXiv:0809.1040), which finds across ~192M FX ticks
that the expected overshoot past a threshold is of the same order as the
threshold itself. Whatever the right buffer is, it is O(1 ATR), not O(0.2 ATR).

Osler's order-flow work sharpens this into a second, independent objection:
stop-loss orders cluster *just beyond* salient levels while take-profit orders
cluster *at* them (Osler, *Journal of Finance* 58(5), 2003; *JIMF* 24(2), 2005).
The region immediately past support is where resting stops sit and where breaks
accelerate. A 0.20 ATR offset places the suggested stop inside that zone.

### 1.3 The `price - 1 x ATR` floor silently replaces the structural stop

```
P(floor binds, all states)                    0.101   CI [0.090, 0.112]
P(floor binds | range_position <= 15)         0.587   CI [0.565, 0.608]
```

In the near-support state — exactly where the UI tells the user the level
structure is what matters — **the displayed stop is a flat volatility stop 59% of
the time**, while the explanation still says "recent structural support is X."
The overall rate is low (10%) because price is usually far above the 49h low, so
this is specifically a near-support labelling defect, not a global one.

(A random-walk simulation predicted 86% overall. That was wrong, and the
disagreement is informative: real `(49h range)/ATR` is q50 7.41 versus 7.66
simulated, so the divergence comes from where price actually sits within the
range, not from the volatility scale.)

### 1.4 The 15 / 85 range flags are not selective

```
P(range_position <= 15)  "near support"       0.166   CI [0.148, 0.185]
P(range_position >= 85)  "near resistance"    0.111   CI [0.095, 0.128]
P(either flag fires)                          0.277
empirical 5th / 95th percentile of range_position:   5.77 / 92.12
```

The flags fire on **27.7% of all observations**. A cue that fires more than a
quarter of the time is not marking an unusual condition. If the intent is a 5%
tail, the empirical cuts are approximately **5.8 / 92.1**, and they should be
computed per coin rather than shared, since the distribution differs by coin.

### 1.5 The 1.5x volume gate is the 69th percentile

```
P(volume_ratio >= 1.5)                        0.307   CI [0.295, 0.319]
volume_ratio percentiles:  q50 0.99   q75 1.74   q90 3.01   q95 4.29   q99 8.88
```

"Above-baseline volume" fires on nearly a third of candles; 1.5x sits at the
69th percentile of its own distribution. The multiple appears in trading blogs
but I found no study testing it. The rank form — top decile within the reference
window — does have peer-reviewed support (Gervais, Kaniel & Mingelgrin,
"The High-Volume Return Premium", *Journal of Finance* 56(3), 2001) and is
strictly better specified.

## 2. Choosing the stop multiple, measured

`stop = support - k x ATR`, floor removed so the structural stop stays structural:

```
    k   median risk%   P(stopped in 24h)   P(dip absorbed)   P(up at 24h | stopped)
 0.20        3.73             0.357              0.067                0.221
 0.50        4.10             0.322              0.158                0.197
 0.75        4.42             0.294              0.231                0.177
 1.00        4.73             0.268              0.301                0.158
 1.50        5.37             0.220              0.426                0.125
 2.00        6.00             0.179              0.531                0.100
 3.00        7.27             0.116              0.697                0.066

 baseline P(price above entry at 24h) = 0.463
```

Two readings matter. First, moving from k=0.20 to k=1.00 costs **one percentage
point of risk** (3.73% to 4.73%) and buys a drop in stop-outs from 35.7% to 26.8%
while absorbing 30% of dips instead of 6.7%. Second, `P(up at 24h | stopped)` is
far below the 46.3% baseline at every k and falls as k rises — so across this
sample the stop was exiting ahead of further weakness rather than cutting
recoveries short. That is the behaviour a protective stop is supposed to have,
and it is the one genuinely reassuring result in this study.

Wilder's own Volatility System used ATR(7) with a multiple of 2.8-3.1 from a
structural anchor, and LeBeau's Chandelier Exit uses 3 x ATR(22). Both are
long-standing conventions without published validation, but both are an order of
magnitude away from 0.20.

## 3. Does any of it predict anything? No.

The entry classifier was replicated over the same 320,325 points and tested
against the base rate, with time-blocked bootstrap CIs.

**Directional test — P(price higher in 24h):**

```
label                        share   P(up)   vs base   95% CI on difference
Breakout watch                4.4%   0.437   -0.0269   [-0.086, +0.032]
Support reclaim               4.7%   0.503   +0.0394   [-0.010, +0.088]
Pullback watch               35.1%   0.476   +0.0120   [-0.030, +0.058]
Too extended / poor reward   35.4%   0.446   -0.0175   [-0.064, +0.032]
No entry signal              20.4%   0.469   +0.0059   [-0.042, +0.055]
BASELINE                    100.0%   0.463
```

**Fair test — realized reward-to-risk (MFE/|MAE|) and drawdown, since the tool
claims risk framing rather than direction:**

```
label                        MFE/|MAE|   vs base   95% CI on difference   |MAE|%   vs base
Breakout watch                   5.020   +0.084    [-0.892, +1.222]        4.057   +0.368
Support reclaim                  5.026   +0.102    [-0.723, +0.911]        3.753   +0.050
Pullback watch                   4.946   +0.036    [-0.677, +0.749]        3.799   +0.096
Too extended / poor reward       4.909   -0.001    [-0.805, +0.842]        3.545   -0.155
No entry signal                  4.814   -0.084    [-0.846, +0.722]        3.679   -0.018
BASELINE                         4.913                                     3.694
```

**Every confidence interval includes zero, on both tests.** Not one label
separates forward outcomes from the base rate. `Support reclaim` has the largest
directional effect (+3.9pp, CI -1.0 to +8.8pp) — the same magnitude as Osler's
+4.6pp bounce edge over random levels (*FRBNY Economic Policy Review* 6(2), 2000),
which is real but small — and it does not even show lower drawdown than baseline.

This is not an argument for deleting the feature. It is an argument that the
feature is a **descriptive risk frame and must never be presented as an edge**.
The existing `outcome_validated: false` disclosure is, on this evidence, exactly
correct and should be strengthened rather than relaxed.

## 4. What changes on this evidence

Mechanical fixes, justified without any market hypothesis:

1. Test broken structure against `support`, not `structure_support` (1.1).
2. Raise the support buffer to `k = 1.0 x ATR` as a **declared convention**
   citing the overshoot scaling law, replacing 0.20 (1.2, section 2).
3. Stop letting the floor silently replace the structural stop: either suppress
   the suggestion when structural risk exceeds the cap, or label the output
   "volatility stop" when the floor binds (1.3).
4. Replace the 15/85 constants with per-coin empirical tail quantiles, or state
   plainly in the UI that the band marks the outer quarter of the recent range
   rather than an unusual condition (1.4).
5. Replace `volume_ratio >= 1.5` with a top-decile rank within the window,
   citing GKM 2001 for the rank form (1.5).
6. Rename the `0.10 x ATR` limit gap a **slippage allowance** and set it from
   order-book depth, not from volatility. The distance between a stop trigger
   and a marketable limit is a liquidity quantity; ATR is the wrong unit.

Product-language fixes:

7. No entry or protection label may imply a measured probability of success.
   Section 3 is the evidence that none exists in this data.

## 5. Why we are not fitting these parameters

The tempting next step — sweep the grid, pick the best k — is not available
honestly, and the reason is worth recording.

Crypto returns share a large common component. Makarov & Schoar
(*Journal of Financial Economics* 135(2), 2020) find the common component of net
order flow explains around 50% of returns at hourly frequency. Applying the Kish
design effect, `n_eff = n / (1 + (m-1) x ICC)`, 40 coins at ICC 0.5 is
approximately **2 independent series**, and that number is nearly invariant to
adding more coins — it converges to 1/ICC.

So one year across 40 coins is roughly **2 coin-years of independent data**, not
40. Under the Minimum Backtest Length result (Bailey, Borwein, Lopez de Prado &
Zhu), targeting a Sharpe of 1.0 gives `ln(N_max) = Y x SR^2 / 2 = 1`, so
**N_max is about 3 configurations for the entire project**. A five-value sweep of
k has already spent more than the budget.

The correct response is not to fit more carefully. It is to **declare parameters
as conventions with cited reasoning, fix the ones that are mechanically wrong,
and reserve the trial budget** until there is materially more independent data.
Hudson & Urquhart (*Annals of Operations Research* 297, 2021) tested 14,919 rules
on crypto including support-resistance and channel breakout classes: in-sample
everything worked, and Bitcoin's best in-sample rule returned -0.10% annualised
out of sample at Sharpe -0.05. Support-resistance was the *weakest* of the five
rule classes they tested.

## 6. What would change the answer

- **More independent data.** Not more coins — more time, and ideally regimes.
  Three years would raise the trial budget to roughly 20 configurations.
- **A repeat-touch level definition.** Kavajecz & Odders-White
  (*Review of Financial Studies* 17(4), 2004) define support as the lowest price
  attained at least twice in the reference window, and allow the level to be
  **undefined**. Their evidence is that S/R levels coincide with limit-order-book
  depth peaks — which supports using levels for execution, not forecasting. A
  single-touch min/max, as shipped, is the weakest definition available.
- **Round-number levels as a first-class feature.** Osler's FX cascade results
  and Urquhart's Bitcoin price-clustering work (*Economics Letters* 159, 2017)
  both point at round numbers as the mechanism. This has better evidential
  support than a 49-bar min/max.
- **The forward recorder reaching a usable sample.** `sell_plan_outcomes.sqlite`
  currently holds 6 plans, 2 completed, against a 20-completed gate. At the
  current rate that gate is months away, and 20 is a floor for a directional
  read rather than a target.

## Reproducing

Fetcher and analysis scripts used for this study are standalone and depend only
on numpy plus the public Coinbase Exchange candles endpoint. Universe selection,
the exact replication of the shipped math, and the bootstrap are described in
Method above. Every number in this document came from that run; none was carried
over from the literature except where cited.

## References

- Glattfelder, Dupuis & Olsen (2011), "Patterns in high-frequency FX data:
  discovery of 12 empirical scaling laws", *Quantitative Finance*; arXiv:0809.1040
- Osler (2000), "Support for Resistance", *FRBNY Economic Policy Review* 6(2)
- Osler (2003), "Currency Orders and Exchange Rate Dynamics", *Journal of Finance* 58(5)
- Osler (2005), "Stop-loss orders and price cascades", *JIMF* 24(2)
- Kavajecz & Odders-White (2004), "Technical Analysis and Liquidity Provision",
  *Review of Financial Studies* 17(4)
- Gervais, Kaniel & Mingelgrin (2001), "The High-Volume Return Premium",
  *Journal of Finance* 56(3)
- Kaminski & Lo (2014), "When do stop-loss rules stop losses?",
  *Journal of Financial Markets* 18
- Makarov & Schoar (2020), "Trading and arbitrage in cryptocurrency markets",
  *Journal of Financial Economics* 135(2)
- Hudson & Urquhart (2021), "Technical trading and cryptocurrencies",
  *Annals of Operations Research* 297
- Urquhart (2017), "Price clustering in Bitcoin", *Economics Letters* 159
- Bailey, Borwein, Lopez de Prado & Zhu, "The Probability of Backtest Overfitting"
- Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio",
  *Journal of Portfolio Management* 40(5)
- Wilder (1978), *New Concepts in Technical Trading Systems*, Trend Research
