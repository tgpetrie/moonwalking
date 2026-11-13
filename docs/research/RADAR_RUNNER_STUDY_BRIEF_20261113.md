# Radar runner study: brief and data facts — 2026-11-13

This page states what the owner wants from the mover boards, what one fresh
test has shown, and exactly which data exists. It is background for designing
the next study. Nothing here is a result beyond what the linked reports state.

## What the boards are for

The boards are a live, reordering list of what is moving most right now:

- a 30-second or 1-minute gainers list, eight rows by default, sixteen with
  "show more";
- 3-minute gainers and 3-minute losers, eight rows each.

The owner's goal, in plain terms: show which coin is moving fastest and which
has the most potential to break out and keep running, even briefly. It does not
have to be a trade signal and it does not have to be right every time. A flagged
coin should go on to run more often than an unflagged one. Percentage change is
the starting point for ranking, and other measures may be combined with it or
shown beside it. A tradable edge would be welcome but is not expected from
30-second to 3-minute tables.

## What has been shown so far

- [Locked historical comparison](LIVE_MOVERS_RESULTS_20261027.md): nonlinear
  model against simple model, inconclusive.
- [Fresh replication](LIVE_MOVERS_FRESH_REPLICATION_RESULTS_20261113.md), run
  once under a [predeclared protocol](LIVE_MOVERS_FRESH_REPLICATION_PROTOCOL_20261113.md):
  on sixteen post-freeze days the stored live score and the displayed percentage
  move ranked board entries backwards against five- and fifteen-minute
  directional outcomes, and a frozen simple ridge ranked them forwards. The
  effect is concentrated in the top fifth by score or move, which gave back about
  0.17% in five minutes and 0.27% in fifteen. Every band's mean gross outcome
  was negative.
- That test measured average outcomes and rank correlation. It did not measure
  whether the fastest movers contain the coins that go on to run. Rare large
  continuations can sit inside a group whose average is poor.
- F1–F5 remain untested. The 5-second capture they need has not completed a
  warmup outside the four-product pilot.

## Data that exists

**Board episodes.** Table `board_outcomes_v2`, written by
`backend/board_outcomes.py`. An episode starts when a product enters the tracked
rows of a board.

| Fact | Verified state |
|---|---|
| Boards recorded | `ignition_1m` (up only), `confirmation_3m_up`, `confirmation_3m_down` |
| Rows tracked | Top eight. `entry_rank` is 1–8 in every fresh row. Rows 9–16 are not recorded |
| Not recorded | A 30-second board, 1-minute losers, coins that never reach a board |
| Re-entry | Tracker default 3,600s per board and product |
| Outcomes | Directional gross return at 5, 15, 30 and 60 minutes from last-trade prices; `max_favorable_15m`, `max_adverse_15m`; `max_favorable_pct`, `max_adverse_pct` over the tracked horizon; `outcome_15m` class at ±0.5%; `last_seen_ts`, `exited_ts` |
| Peak fields | `NOT NULL DEFAULT 0`, so a true zero and "never updated" look the same. Updated when the tracker observes a price; the observation cadence has not been verified |
| Control | Each episode stores the nearest same-direction mover that was not on the board, its change at entry and its returns at the same four checkpoints |
| Volume per day | About 1,750–1,900 episodes per board per UTC day |

Availability in the 87,155 local rows entered from 2026-10-28T00:00Z to the
capture end: control product 84,173; control five-minute return 83,530;
thirty-minute return 84,354; sixty-minute return 81,880; nonzero
`max_favorable_15m` 52,474.

**Entry snapshot**, stored as JSON with each episode. Counts are from the first
60,000 local rows entered from 2026-10-28T00:00Z.

| Field | Availability |
|---|---|
| `pct_1m`, `pct_3m`, `volume_change_1h_pct` | Nearly all rows |
| `pct_1h` | 11,597 rows |
| `trend_streak` | 41,308 rows |
| `bullish_alerts`, `bearish_alerts` | All rows |
| `liquidity`, `spot_pressure`, `market_relation` (categories) | All rows, but a default cannot be told from a measurement |
| `quote_volume_usd`, `realized_volatility_pct_hour` and their age fields | Null in every row. The retention fix that fills them is not running on this collector |
| `live_score`, `live_rank`, `universe_size`, `data_quality` | All rows |
| Score components: `momentum_1m`, `momentum_3m`, `trend_1h`, `volume`, `confirmation`, `persistence` | All rows |

`pct_1m` and `pct_3m` are nominal windows; exact baseline ages were not stored.
The snapshot is captured at most 60 seconds before the entry timestamp.

**Samples.**

| Sample | Dates, UTC | Eligible episodes | Use so far |
|---|---|---:|---|
| Production backup, frozen | 2026-07-19 to 2026-10-17 | 333,170 | Fitting and the locked comparison |
| Local ledger, gap window | 2026-10-18 to 2026-10-27 | 54,338 | Reported as secondary in the fresh replication |
| Local ledger, post-freeze | 2026-10-28 to 2026-11-12 | 83,567 | The fresh replication, once |
| Local ledger, new days | 2026-11-13 onward | about 5,500 per day across boards | Untouched |

**One-minute candles.** `~/.moonwalking/data/candle_archive.sqlite` holds
Coinbase Exchange one-minute candles for 407 products from 2026-09-06 to
2026-10-12 and hourly candles from 2025-10-01 to 2026-10-12. Nothing later has
been pulled. `backend/candle_archive.py` is the existing puller; the source is
public and needs no credentials. A minute with no trades has no row.

## Candidate signals for "still building" against "already spent"

1. Speeding up or slowing down: the share of the 3-minute move made in the last
   minute.
2. Size against the coin's own normal movement.
3. Trading volume behind the move, against one or two prints.
4. Persistence: first appearance, or repeated returns to the board.
5. Coin-specific against market-wide movement.

Signals 1, 3 and 4 can be built from stored fields. Signals 2 and 5 need
one-minute candles for the same period.

## Board options under discussion

1. Activity gate: rank by percentage change, but require enough trading.
2. Staircase against spike: rank or mark by how the move was built.
3. Blended ranking: percentage change adjusted by proven signals.
4. Rank by how unusual the move is for that coin.
5. Repeat-runner view over the last hour.
6. Early-watch list for coins not yet on a board. This needs whole-universe
   data; board episodes cannot test it.

The owner's direction is to combine the best pieces of these options into one
working design, not to choose a single option.

## Fixed constraints

- The boards stay a live list of what is moving most. Any change must still read
  that way to a user.
- No live score, ranking, weight or production change follows from a study
  without a separate review.
- The repository is public. Account data, balances and holdings stay out of it.
- The locked historical validation is not rerun to answer its original question.
