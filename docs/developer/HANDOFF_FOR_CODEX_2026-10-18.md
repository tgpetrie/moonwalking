# Claude to Codex handoff, 2026-10-18

Branch `claude/render-history-data`, based on pinned `56f1b418`. Nothing is
merged to main or deployed. Read-only against all Moonwalking stores and the
candle archive (a copy was used). All public requests were unauthenticated
and at most one per second.

## 1. What exists and where

| Item | Path | State |
| --- | --- | --- |
| RENDER/RNDR identity, venues, quote currencies | `data/render-history/identity.json` | done, verified |
| Coverage, gaps, lineage, all-time-low status | `data/render-history/coverage.json` | done |
| Validation results | `data/render-history/validation.json` | done, all passed |
| Daily candles (4 series) | `data/render-history/series/coinbase_<PRODUCT>_1d.json` | done |
| Weekly aggregates (4 series) | `data/render-history/weekly/coinbase_<PRODUCT>_1w.json` | done |
| Raw source responses with SHA-256 | `data/render-history/raw/` | done |
| Contract schema | `docs/developer/market-history.schema.json` | done |
| Inventory + contract + parity write-up | `docs/developer/RENDER_HISTORY.md` | done |
| Review parity + 100-week indicator fixture | `data/render-history/reference_parity.json` | done |
| Large-move study | `docs/developer/MOVE_STUDY.md`, `data/move-study/` | first run done, extended run pending |
| Brief for Gemini | `docs/developer/GEMINI_BRIEF_MOVE_CAUSES.md` | sent to user, answers pending |

Tests: `python -I -m pytest scripts -q` (30 pass).

## 2. Data facts you can rely on

- Two tokens, never joined: RNDR (Ethereum, `0x6de037ef...`, delisted) and
  RENDER (Solana, `rndrizKT3...`, online). Contracts match between Coinbase
  `/currencies` and CoinGecko `render-token`.
- Coinbase products: RENDER-USD (online), RNDR-USD, RNDR-USDT, RNDR-EUR
  (delisted). Binance returned HTTP 451; no other venue is in the data.
- RENDER-USD daily: 2024-02-15 to now, 977 candles, no missing day, the
  2026-10-18 candle is open (`complete: false`). RNDR-USD/USDT/EUR:
  2022-02-03 to 2025-06-26.
- Weekly: Monday 00:00Z weeks built from daily; first week, last week of
  delisted series and the current week are flagged incomplete, not dropped.
- Validation: boundary duplicates identical; OHLC invariants hold; daily vs
  archived hourly candles match on OHLC for all 374 comparable days; volume
  differs by at most 0.60%.
- Lows are labelled by scope. RENDER-USD lowest daily low 0.651 (2025-10-10);
  RNDR-USD 0.27 (2022-06-18). `is_all_time_low` is always false. CoinGecko's
  cited low (0.0367, 2020-06-16) is outside our data and unverified.

## 3. Decisions made with the user (keep)

1. RNDR and RENDER stay separate series, even labelled composites. So
   **SMA200 is unavailable for RENDER-USD** until the week of 2027-12-13 (200th
   complete week). Show it as unavailable with the reason (138 of 200 weeks).
2. No all-time low or high is claimed from Coinbase data.
3. No probabilities, targets or dates for specific coins from the study.

## 4. Review parity (the Gemini methodology review of the video)

- Several of its bar dates are wrong. Its "current bar, 12 Oct" is Coinbase's
  week of 5 Oct within 0.25%; its "local wave (5) high 2.4395, 11 May" is the
  week of 25 May (high 2.435). Do not use its dates as fixtures without
  re-checking the video.
- The Oct 2025 wick is venue dependent: Coinbase 0.651, review ~0.80 to 0.90.
- Indicators on the 5 Oct week (Coinbase, complete weeks): SMA50 1.7048,
  SMA100 3.1839, MACD -0.0021 / -0.0898 / 0.0877, Stoch RSI K 94.29 D 92.01.
  Close to the review, not equal. Hold parity to identical input closes using
  `indicator_fixture` (last 100 complete weeks), not to the video values.
- Unverified: the fixture's EMA seeding follows the Pine reference example;
  TradingView's built-in may differ in early bars.
- Joining RNDR before 2024-02-19 gives SMA200 3.6734. Comparison only, not
  published.
- **Update 2026-10-19: the video was read directly** (61 bars, see
  `RENDER_HISTORY.md` section 5b and `data/render-history/video_reference_bars.json`).
  Recorded 2026-10-13 about 21:00 to 22:00 UTC; chart is TradingView's
  aggregated `RENDERUSD` index, which uses RNDR prices until mid-2024. From
  August 2024 it matches Coinbase RENDER-USD closely (median close difference
  0.05%). Our indicators on the 5 Oct week equal the video's legend: SMA50
  1.7048 vs 1.7049, SMA100 3.1839 vs 3.1838, MACD histogram 0.0877 vs 0.0877.
  The review's "current bar" OHLC was the 5 Oct bar and its SMAs were the live
  12 Oct bar. The Oct 2025 wick on the index is 0.5454 (Coinbase 0.651). Use
  the video's dates for anchors; never its prices as Coinbase fixtures.

## 5. Review of your branch `codex/macro-chart-20261018` at `0198513`

- It consumes the contract correctly: rejects stitched series, requires unit
  fields, builds weeks from complete days, no all-time claims, RNDR and RENDER
  separate. Reactions respect the replay cutoff and confirmation time.
- The FET figures in your timing doc reproduce from the archived hourly
  candles: May 17 low 0.1843, June 1 high 0.2884, 5 touches at ±1% and 6 at
  ±2% of 0.1843, June 24 close 0.1729, July 6 close 0.1715, no return to
  ±1% of 0.2884 after June 22.
- Coins loaded live in the browser have less provenance than our files: every
  candle is marked complete, no no-trade ranges, no cross-check. Use the
  validated files in `data/render-history/` for RENDER acceptance.
- **User feedback:** the user sees only past levels. The future scenario is an
  opt-in checkbox, off by default, and disabled with no confirmed decline or
  while a View zoom is active. Consider making it discoverable (a visible
  "what to watch" list of levels, or an on-state hint when disabled). Keep the
  rule of no date and no probability.

## 6. The large-move study (first run, 407 current products, 2025-10 to 2026-10)

- After a +10% day, coins trailed volatility-matched peers: -1.4%, -2.0%,
  -1.9% (1, 3, 7 days, discovery) and -1.7%, -2.4%, -2.8% (test), intervals
  excluding zero. Holds across about 300 coins.
- In plain returns, buying at the close of a +10% day averaged -1.6% next day
  (test), -2.6% after an assumed 1% round-trip cost. Longer horizons negative
  but not established.
- After a -10% day: no replicated pattern, no dip-buying edge.
- Limits: relative to peers, assumed (not actual) costs, archive holds only
  today's listed products (survivorship), one year, not causal, overlapping
  splits. A post-hoc volatility-matched control was added after the first
  run; this is disclosed in the doc.
- Allowed in the UI: describe as an observed tendency in this sample, with
  scope and dates. Not allowed: a probability, target or date for a coin.
- **Extended run, done:** native daily candles for all 492 Coinbase USD
  products since 2022 (89 delisted included), settings fixed beforehand
  (discovery 2022 to 2024, test 2025 to 2026-10-17). The finding holds on 4x
  the events: after a +10% day, coins trail volatility-matched peers by about
  1.4%, 2.1% and 2.1% at 1, 3 and 7 days, in both periods and in every
  calendar year. Delisted products fade more (7-day -4.1% vs -1.7%). Buying at
  the close of such a day averaged -1.5% to -1.7% the next day before costs.
  Down-moves: still no pattern. Details in `MOVE_STUDY.md`.
- Still relative to similar coins, before real costs, one exchange and one
  cycle, and not causal. Safe copy for the UI: "In Coinbase USD products
  2022 to 2026, coins that rose 10%+ in a day have tended to trail similar
  coins over the next 1 to 7 days." No probabilities, targets or dates. Do not
  show it as a per-coin prediction.

## 7. Open items

- Gemini: cause catalogue for 80 events, video bar dates, critique of the
  study. Answers have not come back.
- Video bar dates need re-checking by someone who can open the video.
- A true all-time low needs a second source covering 2020 onward, as a
  separate labelled series. Not started.
- Hourly or minute RENDER-USD export to the contract: not done, on request.
- Study next steps: causes, thin-coin spreads, then a second event type
  (arrival at a confirmed high or low).

## 8. Update 2026-10-19: what the studies mean for the chart

- **Level study (`LEVEL_STUDY.md`, preregistered):** confirmed weekly highs and
  lows, macro anchors and Fibonacci 0.5 / 0.618 / 0.786 levels behave like
  placebo lines at a similar distance (0 of 24 tests survive). Keep levels as
  historical reference. Do not call them support or resistance, and do not
  imply a reaction is likely there.
- **Move study, after robustness checks (`MOVE_STUDY.md`):** the give-back
  after +10% days is real but concentrated in thin coins (under $1M a day) and
  high-volume, coin-specific spikes. Low-volume, market-driven rises barely
  fade. Rising into any line shows the same give-back, so it is about the
  approach, not the line.
- If the panel adds context, the defensible wording is about the approach:
  "sharp, high-volume rises in thinly traded coins have tended to give back
  part of the move over the following days (Coinbase USD, 2022 to 2026)". No
  probabilities, targets or dates.
- The cause categories from the Gemini table should not be shown: the split
  disappears once only same-day sources count.
- **Volume profile (`VOLUME_PROFILE_STUDY.md`, preregistered):** POC, VAH,
  VAL and high/low-volume nodes on confirmed swings also behave like placebo
  lines (0 of 22 tests), including with hourly-built profiles. Do not label
  them support, resistance, magnets or highways.
- **Study 2c (`ABSORPTION_STUDY.md`):** hourly two-step absorption/exhaustion
  candles add little (bearish: +0.1 to +0.4 points, not replicated by the
  rule); location does not help. One preregistered hypothesis passed:
  breakdowns through the macro low (mostly) or VAL lagged placebo
  breakdowns by about 1 point over 14 days in both periods, but on data that
  had already suggested it. If shown, label it as a small historical tendency
  awaiting confirmation on new data.
- **Study 2d (`PROFILE_SHAPE_STUDY.md`):** P/b profile shapes, three-day
  balance breakouts and volume ledges show nothing (0 of 22). Do not label
  profile shapes or balance breakouts as continuation signals.
