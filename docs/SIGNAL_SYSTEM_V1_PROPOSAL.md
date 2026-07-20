# Moonwalkings Signal System V1 Proposal

Status: Relative calibration proposed; event-evolution foundation active

Date: 2026-07-14

This document defines a realistic path from the current deterministic alert engine to a relative, explainable, and lower-noise signal system. It is intentionally separate from the executable v0 rules in `backend/alerts_engine.py`.

## Product objective

Moonwalkings should answer three questions at a glance:

1. What is becoming unusual now?
2. Is the move confirmed by participation, market context, or external attention?
3. Is this early, confirmed, extended, or failing?

The dashboard should not ask the user to interpret twenty detector names. Detectors become evidence. The UI publishes one primary state, at most one modifier, and a compact confidence value.

## Audit findings that motivated v0.2

### Current alignment

- Frontend price fallbacks now use the backend moonshot, breakout, dump, and crater thresholds.
- The Legend describes the running v0 engine rather than the older frontend-only `8%` and `12%` thresholds.
- This is implementation alignment, not proof that the thresholds are well calibrated.

### Pre-v0.2 alert quality baseline

- A live sample produced 35 alerts in approximately 17 minutes.
- The retained March alert database contains 20,949 alerts across roughly four active days.
- The largest historical families were whale, breakout, volatility expansion, breadth failure, and stealth.
- Several symbols repeated five or six times inside the short live sample.
- The sampled raw stream was suitable as detector telemetry, but it was too noisy to be treated directly as a meaningful user notification feed.

### Gaps found in the pre-v0.2 audit

- Fixed percentage thresholds do not adjust for each asset's normal volatility.
- The `500` whale floor is measured in base-token units and is not comparable across assets.
- A prior quiet hour can make the 1-hour percentage ratio look extreme.
- The return-history detectors are updated at the worker poll cadence, currently about eight seconds. Labels such as `10m` and `5m_vs_20m` therefore do not yet represent true wall-clock windows.
- Return history is initially padded with zeros, which can exaggerate early volatility-expansion and squeeze ratios.
- Market breadth uses return values from the displayed mover cohorts while cached prices add many symbols without returns. The displayed universe and the measured breadth universe are therefore not fully aligned.
- `Stealth` currently infers accumulation or distribution from the sign of a small price move. Without trade-side or order-book information, that directional conclusion is too strong.
- Detector TTL values are included in alert objects, while the canonical active endpoint applies its own default 120-second active window.
- The floating Alerts control previously provided only an in-app unread counter; that audit finding led to the delivery layer described below.

### Implemented in v0.2

- Raw Pulse detections are grouped into per-symbol Signal Events with an evolution path, confidence explanation, and Notify slice.
- Return history and fast/slow EMA detectors advance once per wall-clock minute without zero padding.
- Full-universe cached symbols receive 1m/3m returns before breadth is computed.
- Whale and liquidity-shock notional gates use quote USD rather than universal base-token units.
- Alert-specific expiration is canonical; the endpoint TTL is only a legacy fallback.
- Minute-volume retention defaults to 48 hours, with 90-day hourly quote-volume rollups and explicit coverage.
- Opt-in browser notifications and configurable email, Telegram, or Discord delivery are available for eligible event transitions.

## User-facing state model

The board should expose four primary states:

| State | Meaning | Delivery |
|---|---|---|
| Building | Unusual relative movement is emerging but lacks confirmation. | Board only |
| Breakout | Relative movement is unusual and has at least one independent confirmation. | Board and Alerts Center |
| Moonwalking | Rare, high-confidence move with strong confirmation and healthy data quality. | Board, Alerts Center, optional notification |
| Risk | Downside impulse, rejection, exhaustion, or reversal invalidates a clean continuation. | Board, Alerts Center, optional notification |

Optional modifiers:

| Modifier | Meaning |
|---|---|
| Flow | Unusually large quote-volume participation |
| Quiet Flow | Unusually large participation without commensurate price displacement |
| Social | Coin-specific attention or sentiment is unusually strong relative to its own history |
| Derivatives | Open interest, funding, liquidation, or taker-flow context confirms or warns against the move |

`Whale` may remain friendly UI language, but its technical description should remain `aggregated flow` until trade-level data can identify individual large prints.

## Relative measurements

### Price surprise

For each asset and each window, calculate a robust scale from historical returns:

```text
price_scale = max(1.4826 * MAD(historical returns), liquidity_floor)
price_surprise = current_return / price_scale
```

Use separate baselines for 1-minute, 3-minute, and 15-minute returns. Prefer seven complete days; require at least 24 hours before calling a baseline mature.

Also calculate the cross-sectional percentile among eligible Coinbase USD assets for the same timestamp. A signal must be unusual both for itself and within the current market.

Bootstrap liquidity floors, pending backtesting:

| Median hourly USD turnover | 1m absolute floor | 3m absolute floor |
|---:|---:|---:|
| At least $5m | 0.25% | 0.60% |
| $500k to $5m | 0.40% | 0.90% |
| $50k to $500k | 0.65% | 1.40% |
| Below $50k | Do not notify | Do not notify |

These floors prevent a tiny statistical scale from turning negligible movements into high-confidence alerts. They are bootstrap values and must be validated.

### Volume surprise

Convert Coinbase base volume to quote notional per candle:

```text
quote_volume_usd = base_volume * typical_price
```

For one-minute flow, compare `log1p(quote_volume_usd)` against the asset's historical one-minute distribution using median and MAD.

For the 1-hour banner, publish both:

```text
previous_hour_ratio = rolling_60m_quote_volume / prior_60m_quote_volume
typical_hour_ratio = rolling_60m_quote_volume / median_comparable_hour_volume
```

The comparable baseline should use recent historical hours, preferably the same UTC hour-of-day, with a general seven-day median as fallback. A percentage is published only when coverage and denominator checks pass.

### Market-relative context

Compute returns for the full eligible universe before selecting board rows. Market breadth, cross-sectional percentiles, and relative strength must all use the same eligibility set.

Minimum eligibility:

- Coinbase USD spot product is online and tradeable.
- Price is fresh.
- Required return baseline is present.
- Median hourly quote turnover is at least $50k for notification eligibility.
- Stablecoins and wrapped duplicates are placed in an explicit exclusion or comparison group.

### Social context

Keep attention and sentiment separate:

- Attention surprise: current mention count relative to the asset's own historical mention distribution.
- Weighted sentiment: sentiment multiplied by unique/social volume and normalized against history.
- Trending rank: a discovery fact, not a sentiment score.
- Followers, subscribers, or watchlist users: audience reach, never `social_volume_24h`.

Require a minimum sample count before publishing sentiment direction. Missing credentials remain unavailable.

## Bootstrap v1 signal definitions

These are proposed starting points for shadow evaluation, not immediate production truth.

| Signal | Proposed relative definition |
|---|---|
| Building | Directional price surprise at least `1.5`, cross-sectional percentile at least `75`, and absolute liquidity floor passed. Board only. |
| Breakout | Price surprise at least `2.5`, cross-sectional percentile at least `90`, plus one confirmation: volume surprise at least `2.0`, 1-hour volume at least `1.5x` typical, sustained top-cohort rank, or verified external catalyst. |
| Moonwalking | Price surprise at least `4.0`, cross-sectional percentile at least `98`, confidence at least `85`, plus strong flow (`volume surprise >= 3.0`) or two independent confirmations. |
| Cooling | Negative price surprise at most `-1.5` and lower cross-sectional quartile. Board only until confirmed. |
| Critical Risk | Negative price surprise at most `-4.0`, lower-two-percent cross-sectional rank, and volume/risk confirmation. |
| Flow | One-minute quote-volume surprise at least `4.0`, quote volume above the asset's historical 99th percentile, and a minimum current notional gate. |
| Quiet Flow | Quote-volume surprise at least `3.0`, absolute price surprise at most `1.0`, and the condition persists for at least two of three complete minutes. Direction remains neutral without signed flow. |
| Reversal Risk | A prior directional move at least `2.5` surprise is followed by an opposite one-minute move at least `1.5` surprise plus peak retracement, rank decay, opposing flow, or volume fade. |
| Fakeout | A recorded Breakout state occurred, then price returned inside the pre-breakout range within ten minutes. This requires event state, not simultaneous opposite 1m/3m percentages alone. |
| Social Heat | Coin-specific attention surprise at least `2.5` with adequate samples. Sentiment direction is shown only when weighted sentiment is available. |

## Confidence and delivery

Confidence is an explanation score, not a probability of profit.

Proposed components:

| Component | Maximum points |
|---|---:|
| Price surprise and cross-sectional rank | 30 |
| Quote-volume confirmation | 25 |
| Market breadth and relative strength | 15 |
| Persistence or structure confirmation | 15 |
| Verified social, derivatives, on-chain, or event confirmation | 15 |

Data quality is a gate before scoring:

- Mature price baseline or an explicit warming state.
- At least 55 of 60 complete volume minutes for a full rolling-hour comparison.
- Fresh price and volume timestamps.
- Sufficient quote turnover.
- No inferred social direction from an attention proxy.

Delivery tiers:

| Confidence/state | Surface |
|---|---|
| Below 45 | Internal detector telemetry only |
| 45 to 64 | Board state only |
| 65 to 84 | Board and Alerts Center |
| At least 85 | Board, Alerts Center, optional notification |
| Critical confirmed risk | Optional notification regardless of bullish score |

Notification hygiene:

- Notify on state transition, not every poll.
- One active notification per symbol.
- Re-notify only if confidence improves by at least 10 points, direction changes, or the previous state expired and a new event forms.
- Default per-symbol notification cooldown: 15 minutes.
- Default global notification budget: no more than six per hour, with watchlist signals taking priority.

## One-hour volume data plan

### Existing assets to preserve

- Coinbase one-minute candles are already fetched.
- SQLite stores `product_id`, minute timestamp, base volume, and close.
- The banner correctly avoids substituting price or 24-hour volume for missing 1-hour volume.
- A bootstrap median exists for warmup when enough older minutes are available.

### Required storage changes

Use two retention levels:

1. Raw one-minute candles: retain 48 hours for live microstructure and precise replay.
2. Hourly aggregates: retain at least 90 days for typical-volume baselines and calibration.

Hourly aggregate fields:

```text
product_id
hour_ts
base_volume
quote_volume_usd
minute_coverage
open
high
low
close
return_1h
source
```

Backfill historical hourly candles in bounded Coinbase request windows. Coinbase documents a maximum of 300 candles per request and warns that intervals without trades may be absent, so coverage must be stored explicitly.

### Display fallback hierarchy

1. Full: 60 complete current minutes and a mature historical comparison.
2. Bootstrap: at least 55 current minutes and a robust historical median; label the baseline as bootstrap.
3. Current only: show current rolling volume without a comparative percentage.
4. Unavailable: no trustworthy current window.

Never backsolve a prior value merely to populate a percentage.

## External confirmation priorities

### First: derivatives context

Open interest, funding, liquidation, and taker-flow data distinguish spot demand from leveraged crowding. This is often more immediately useful than slow on-chain data for a short-window dashboard. CoinGlass currently documents these endpoint families.

### Second: social attention and sentiment

Santiment documents five-minute social-volume metrics and weighted sentiment normalized by mention volume. This matches the proposed separation of attention and sentiment.

### Third: tick trades and order books

Kaiko documents normalized tick-level trades and order-book products. This would let Moonwalkings replace aggregate `Whale` inference with large-print, taker-side, liquidity-wall, and slippage evidence.

On-chain data remains valuable as slower context, especially exchange inflows/outflows and holder behavior, but should not dominate a one-minute signal.

## At-a-glance UI contract

Each board row shows:

```text
SYMBOL  [primary state] [optional modifier] [confidence]
```

Examples:

```text
SOL  Breakout  Flow  78
INJ  Building  Social  58
ARB  Risk  82
```

The row must not show more than one primary state and one modifier.

Clicking the row opens a `Why now` proof strip:

```text
Price: 97th percentile, 3.2x normal
Flow: 2.4x typical hour, full 60/60 coverage
Market: breadth supportive, relative strength +1.8
External: social attention +2.7 robust deviations; sentiment unavailable
Invalidation: loses breakout range or confidence falls below 65
```

This proof strip is the unique product advantage: a simple surface with inspectable evidence underneath.

## Implementation sequence

### Phase 0: truth and noise controls

- Label current rules `v0 heuristic`.
- Stop calling poll-count windows `minutes`.
- Separate detector telemetry from user alerts and notifications.
- Make active lifetime honor a single canonical expiry contract.
- Record every signal transition, evidence snapshot, configuration version, and data-quality state.

### Phase 1: correct historical foundation

- Compute full-universe returns before board selection.
- Store quote-volume USD and coverage.
- Retain 48 hours of minute data and 90 days of hourly aggregates.
- Add bounded Coinbase backfill with rate-limit handling.
- Remove audience reach from social-volume fields.

### Phase 2: shadow relative engine

- Run v0 and v1 in parallel without exposing v1 notifications.
- Store v1 state transitions and forward outcomes at 5m, 15m, and 60m.
- Measure maximum favorable excursion, maximum adverse excursion, continuation, reversal, and alert rate.
- Segment results by liquidity and volatility regime.

### Phase 3: calibrated release

- Select thresholds against explicit alert budgets and quality targets.
- Publish a versioned rule set and changelog.
- Replace fixed frontend fallback logic with backend-provided state and proof.
- Enable notifications only for validated high-confidence transitions.

## Acceptance targets

- Alerts Center: target 6 to 20 meaningful events per hour across the full universe during normal conditions.
- Optional notifications: target 0 to 6 per hour, prioritizing watchlist assets.
- No symbol repeats without a new state, material confidence increase, or direction change.
- At least 95% of displayed alerts include mature or explicitly labeled bootstrap data.
- Every signal exposes input freshness, baseline coverage, rule version, and a human-readable proof.
- Social sentiment never appears without a real coin-specific provider and adequate samples.
- Volume gates use quote notional or asset-relative percentiles, never a universal base-unit threshold.

## Source references

- [Coinbase Exchange candle documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
- [Santiment social-volume documentation](https://academy.santiment.net/metrics/social-volume/)
- [Santiment weighted-sentiment documentation](https://academy.santiment.net/metrics/sentiment-metrics/weighted-sentiment-metrics/)
- [CoinGlass API overview](https://docs.coinglass.com/reference/endpoint-overview)
- [Kaiko tick-trade documentation](https://docs.kaiko.com/rest-api/data-feeds/level-1-and-level-2-data/level-1-tick-level/all-trades)
