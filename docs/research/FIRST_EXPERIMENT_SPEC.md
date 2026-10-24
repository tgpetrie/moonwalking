# First experiment specification: does Hyperliquid funding add out-of-sample information beyond price and volume?

Written 2026-10-24 on branch `claude/data-source-plan` (docs only). **This is a
specification. The experiment has not been built or run.** The only measurements taken
for it were availability checks (one request per coin to find each coin's earliest
funding record; rows discarded; results in `~/.moonwalking/analysis/hl_first_funding.json`).

Legend: **[V]** verified by direct check on 2026-10-24; **[U]** unverified; **[A]**
planning assumption; **[H]** hypothesis, not a finding.

## 1. Why this experiment, and why it is the smallest useful one

* It needs **no account, no key and no money**: Coinbase candles that already exist and
  Hyperliquid's keyless public funding history.
* It tests the one derivatives input BHABIT collects but cannot show history for, and
  its result decides whether funding stays in Stage A collection or is dropped from
  active evaluation (`TRIAL_READY_PLAN.md`, section 3).
* **Prior [H]: low.** A pre-registered study on `origin/claude/render-history-data`
  (Study 3a, not re-verified here) found that funding at the close of +10% days did not
  separate spikes that hold from spikes that fade (Spearman with the 7-day outcome
  -0.02 in discovery, +0.07 in test). That study looked only at **event days**, used Binance
  and Hyperliquid, and compared to volatility-matched peers. **This experiment asks a
  different question:** across **every coin-day**, does funding add anything beyond price
  and volume? A null here is the expected, and still useful, result.
* **It does not repeat** that study's replicating finding (perp *listing* status), because
  every coin in this sample has a perp by construction.

## 2. Hypothesis (pre-registered) [H]

**H2.** The 30-day rolling z-score of a coin's daily-mean funding rate, known at the close
of day d, predicts the coin's BTC-residual, volatility-scaled return over the next 24
hours and 7 days, **incrementally to a price-and-volume baseline (M0)**.
Direction is not fixed in advance (crowding could mean reversal or continuation); the test
is two-sided.

## 3. Data needed (exact)

| Input | Source | Fields | Span | Status |
|---|---|---|---|---|
| Daily Coinbase candles for the 133 covered coins and for `BTC-USD` | The 494-file daily panel (survivorship-free; currently in another session's scratchpad) | UTC day start, open, high, low, close, volume | Funding start per coin (earliest 2023-05-12) to 2026-10-17 | **[V] exists; must be copied to a stable folder first** |
| Hourly Coinbase candles (cross-check only) | `candle_archive.sqlite` | as above, hourly | 2025-10 to 2026-10-12 | **[V] exists**; used only to cross-check the daily panel on the overlap |
| Hyperliquid funding history | `POST https://api.hyperliquid.xyz/info`, `{"type":"fundingHistory","coin":<name>,"startTime":<ms>}` | `coin`, `fundingRate`, `premium`, `time` | First record to 2026-10-17, 500 hourly rows per request, paged forward | **[V] endpoint works** |
| Perp identity map | `{"type":"meta"}` universe (234 markets) | name, scaling prefix (`k...` for 1000x contracts) | Current | **[V]** |

**Covered coins:** 133 of 407 (33%) [V]. **Funding history length [V]:** 123 coins have at
least 365 days; **94 have funding from before 2025-01-01** (the discovery/test split date
below); earliest record 2023-05-12; median first record 2024-02-14.

**Volume of data [V, computed from each coin's measured first record]:**
* **5,594 requests** at 500 rows each, **2,760,051 hourly rows**, about **103 minutes** at 1.1 s per request.
* Storage: about **250 MB** in SQLite and about **190 MB** of raw cached JSON (at an assumed 90 and 70 bytes per row [A]). Total well under 1 GB, on the local disk only.
* **114,927 coin-days** in total: 36,249 before 2025-01-01 and **78,678 from 2025-01-01**; about **120 coins per daily cross-section** in the test period.

## 4. Universe and point-in-time handling

* **Universe:** the 133 coins, subject to the **identity check** below. Primary
  results on all that pass; sensitivity on the 91 that also have at least 95% hourly
  candle coverage [V].
* **Identity check (before any funding is joined to returns):** for each pair, daily
  closes over 30 overlapping days must agree with Coinbase within 5% after the contract
  multiplier (the same rule as Study 3a). Pairs that fail, and ticker collisions that
  study found (for example AI, EDGE, CVC, HNT, RAY, AERGO, LOOM, QUICK, BOND, JUP, WAL),
  are excluded and **listed**. RNDR and RENDER stay separate.
* **Survivorship:** the daily panel includes delisted products, so coins that were
  delisted after trading on Hyperliquid are kept where they have both series; the hourly
  archive is survivorship-biased and is used only for cross-checks.
* **Listing date:** a coin enters the cross-section only after it has **at least 30 days**
  of its own funding and price history (needed for the rolling windows).
* **When a value is "known".** Decision time for day d is **00:00 UTC of day d+1**. A funding
  print is used only if its `time` is at or before that instant. **[U] The exact meaning of
  the `time` field (whether the rate covers the hour before or after it) is not confirmed
  from Hyperliquid's documentation; the prior study used the 24 hours ending at the daily
  close.** The primary analysis therefore adds a **one-day extra lag** to the feature as
  the conservative case, and the zero-lag version is reported as a sensitivity run.
* **Entry:** the open of day d+1 (not the close of day d). Labels are measured from
  that open.
* **Past-only statistics:** every rolling mean, standard deviation, beta and z-score uses
  data strictly before the decision time. No full-sample normalisation.

## 5. Variables

**Labels (two, pre-registered):**
* `y24`: the coin's return from the open of d+1 to the open of d+2, minus beta times BTC's
  return over the same interval, divided by the coin's trailing 30-day standard deviation
  of daily returns. Beta is the trailing 90-day regression slope on BTC (past only).
* `y7`: the same from the open of d+1 to the open of d+8.

**Baseline M0 (price and volume only, all known at the decision time):** volatility-
normalised returns over 1, 7 and 30 days; trailing 30-day realised volatility; today's
volume divided by its trailing 20-day median; trailing 90-day BTC beta; BTC-residual 7-day
return; a thin-coin flag (trailing 20-day median dollar volume below $1M, as in the
prior study). Model: ridge regression, refit walk-forward (below).

**Primary funding feature:** `fz` = the 30-day rolling z-score of the **daily mean funding
rate**, each print converted to an 8-hour equivalent (`rate x 8` for hourly prints), then
ranked cross-sectionally within the day.
**Secondary (descriptive only):** 7-day mean funding; indicator `|fz| >= 2`; the premium field.

## 6. Testing protocol

1. **Split (same as the prior studies, for comparability):** discovery before 2025-01-01,
   test from 2025-01-01 to 2026-10-10 (**about 93 calendar weeks**). The rule, feature and
   thresholds are **frozen on discovery**; the test period is looked at once.
2. **Walk-forward fitting:** M0 and M0-plus-funding are refit each calendar month on all
   data before it, with a **7-day embargo** (the longest label).
3. **Primary statistic: incremental IC.** Each day, tie-aware rank correlation across
   coins between (a) `fz` residualised on the M0 prediction and (b) the label. Average
   within each **ISO calendar week** (the block); the interval is a bootstrap over weeks.
   Report the number of weeks and the average number of coins per day.
4. **Overlap handling:** `y7` windows overlap, so inference uses weekly blocks and an
   additional run on non-overlapping 7-day samples (one weekday per coin, rotated).
5. **Nested comparison:** out-of-sample IC of M0 versus M0 plus `fz` on the same folds.
6. **Controls for the event comparison (secondary):** days with `|fz| >= 2` against
   **clean same-coin controls**: non-extreme days of the same coin, 7 to 30 days away,
   matched on the trailing volatility quintile and the BTC 7-day trend bucket.
7. **Regimes:** results by BTC 30-day trend tercile **with the block count in each**; no
   regime is interpreted below 15 blocks.
8. **Costs:** the long-short quintile spread reported gross and under 0.2 / 0.5 / 0.9 /
   1.2% round-trip scenarios at the 7-day horizon, each marked an assumption until the
   real fee tier is known.
9. **Sensitivity runs (all reported):** zero extra lag; excluding BTC and ETH; excluding
   coins with under 95% hourly candle coverage; daily panel versus the hourly archive
   aggregated to days on the overlap; excluding the first 60 days after each coin's
   listing.
10. **Multiple testing:** two primary tests (`y24`, `y7`), so the family-wise level is
    0.025 each (Bonferroni); all other results are descriptive.

## 7. Success and failure criteria (measurable, decided before the data is joined)

* **Minimum effect of interest (MEI): incremental IC of 0.02** [A]. Reason: in the
  normal approximation an IC of 0.02 at the 7-day horizon (sd about 12% [A]) gives a gross
  long-short decile spread of about 0.84%, **close to the 0.9% cost scenario**; a smaller
  IC could not matter economically at that horizon even if real.
* **Power:** with about 93 test weeks, the smallest effect detectable at 80% power is
  about **0.012 if the weekly-block sd of the IC is 0.04, and about 0.026 if it is 0.09**
  [A: both values assumed; the real sd is measured from M0 in the first run and the
  conclusion is stated against the measured value].
* **Supportive** (either horizon): the 97.5% block interval for incremental IC excludes
  zero **and** the point estimate is at least 0.02 **and** the sign agrees in discovery and
  test **and** the sign holds in at least two BTC terciles with at least 15 blocks each.
* **Ruled out:** the upper bound of the 97.5% interval is below 0.02 for **both** horizons.
* **Inconclusive:** anything else, including too few blocks. This is a valid outcome.
* **Pre-registered expectation [H]:** ruled out or inconclusive.
* **Consequences:** *supportive* leads to forward shadow collection and a second look
  (Stage B); *ruled out* stops active evaluation of funding **level** (the free forward
  logging in `pit_context.sqlite` continues at no cost); *inconclusive* keeps forward
  collection only.
* **Invalid run (rerun, not a result):** identity check not completed before joining;
  any rolling statistic using data after the decision time; fewer than 60 coins per day
  on average in the test period; or a code path that computes a statistic on the test
  period before the discovery rule is frozen.

## 8. Not in scope

Binance funding archives, open-interest history (no free source), liquidations,
unlocks, any paid or keyed source, any production change, any product label. Funding
**must not** be described as bullish, bearish or a squeeze signal in any product text
regardless of the outcome, consistent with the prior study's decision.

## 9. Preconditions (nothing here has been done)

1. Copy the daily panel (and, for reuse, the funding cache) from the temporary scratchpad
   to a stable local folder with a SHA-256 manifest. **No network needed.**
2. Commit this specification (done with this file) **before** any funding is joined to returns.
3. Record the Hyperliquid funding `time` semantics from its documentation, or keep the
   conservative one-day lag as primary.
4. Re-confirm the PIT task is running if forward data is wanted for later stages.

## 10. Recommended first implementation task

**Input freeze, with no analysis and no new network traffic:**

> Copy the 494 daily-candle files from the other session's scratchpad
> (`.../render-historical-data-bf650f/.../scratchpad/daily_all`) to
> `~/.moonwalking/data/daily_panel_2022_2026/` (read-only copy; do not modify the
> originals), and write `MANIFEST.json` containing, for every file, its SHA-256, product
> id, first and last candle date and candle count. Add a short verification script that
> (a) recomputes the hashes, (b) reports products with gaps or fewer candles than
> expected, (c) lists which of the 133 Hyperliquid-covered coins have a daily series and
> from which date, and (d) cross-checks overlapping days against `candle_archive.sqlite`
> (agreement within 0.1% on close). **Acceptance:** all 494 hashes match the source,
> coverage report written, cross-check passes for at least 99% of overlapping coin-days.

This is the highest-value first step because it removes the plan's most fragile
dependency (a temporary scratchpad), costs nothing, touches no live system, and every
later step (identity checks, the funding fetch, the baseline) depends on it.
