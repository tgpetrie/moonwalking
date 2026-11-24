# Coinbase paper depth — Stage 2 handoff

Branch `claude/coinbase-paper-stage2-20261124`. It merges the depth prototype
(`47a661b`, `ef4d9ea`) onto `main` and finishes Stage 2 on top of it.
Everything here is paper or dry-run. No route, agent or script can place,
preview or move anything on Coinbase, and the safety-gate tests fail if one is
added.

## Why

The official pilot marked a position against the single best bid and treated
any quote whose top-of-book size was below the position as thin. On a live 30
second BTC-USD window the best level was at times worth about $10, so a $714
position was thin on some polls and the window was rejected, though every quote
was fresh. The pilot was measuring top-of-book size, not what a sell would
realise. The cycle strategist's dry-run exit had the same limit
(`insufficient_top_of_book_size`) and priced its sales in floats.

## What Stage 2 changed

### One Decimal sell estimate: `backend/paper_fills.py`

- `estimate_sell_proceeds(levels, quantity, fee_rate=, slippage_rate=)` walks
  the bids best first, applies slippage to the volume-weighted price of that
  walk, then charges the fee on the slipped proceeds. A single level that
  covers the size reduces to the pilot's `bid * (1 - slip) * quantity * (1 - fee)`.
- A book that can't cover the size returns status `insufficient_book_depth`
  with `fillable_quantity` and `depth_shortfall_quantity`, and leaves net
  proceeds and the weighted price unset. A partial fill is never reported as
  the position's value.
- `book_levels()` accepts Advanced Trade (`{"price", "size"}`) and Exchange
  (`[price, size, ...]`) levels. It rejects an empty book, prices that don't
  strictly descend, a zero or negative size, a non-finite number, and (given a
  best ask) a crossed book. JSON floats keep their printed value.
- Its users: the pilot's `_mark` (`scripts/coinbase_paper_exit.py`), the
  strategist's `paper_sale` (`backend/agents/trading_costs.py`), the depth
  replay, and `GuardedDryRunExitExecutor`. Existing pilot tapes and the
  strategist ledger produce the same numbers as before.

### Guarded dry-run exits (`backend/agents/cycle_strategist.py`)

- A quote that carries a `bids` ladder is priced across the levels the exit
  would consume (`order_type: simulated_sell_across_bids`, with
  `estimated_vwap_usd`, `levels_consumed` and `depth_cost_vs_top_bid_usd`).
- A ladder that can't cover the exit is blocked with `insufficient_book_depth`
  and the shortfall. A ladder that is malformed (`invalid_bid_ladder`) or
  doesn't start at the quote's own top bid (`quote_ladder_mismatch`) is
  refused. Every existing guard still runs first.
- Without a ladder the old rule is unchanged: the top bid must cover the exit
  (`insufficient_top_of_book_size`), priced by the shared estimate.
- Every executor outcome, blocked ones included, carries `dry_run: true` and
  `order_submitted: false`. `live_guarded`, the emergency pause and the daily
  order cap behave as before.

### Live quotes (`backend/agents/cycle_context.py`)

`fetch_top_of_book` and `fetch_live_quotes` take `depth_levels` (1 to 50).
Above 1 they read the public Exchange level-2 book and add a `bids` ladder of
that many levels (`source: coinbase_exchange_book_level_2`). **The default
stays 1**, so no caller changes behaviour until it asks for depth.

### Depth replay (`scripts/coinbase_paper_depth.py`)

- **Rebounds are measured on the executable price.** The running low, both
  rebound rules and net profit use the depth-weighted price for the full
  position size (`executable_price_usd`), not the top bid. A 0.0001 BTC bid
  jumping to $45,000 over a flat $40,100 book reads about 0.29% for a 0.03 BTC
  position, not 12.5%, and doesn't trigger. A real move in the price a sale
  would get still does.
- A quote whose book can't fill the position has no executable price, so its
  rule values are empty: it can't trigger, can't count as a missed trigger and
  can't set the running low. (The prototype already kept such quotes out of
  the persisted low; its own record used to show a made-up low and a zero
  rebound.)
- `threshold_held_at_exec` re-measures the execution book from the low the
  trigger saw, as the pilot does.
- It still uses schema `depth-prototype-1`, refuses tapes that aren't
  `synthetic_position: true`, and never produces an official result.

### Depth collector (`scripts/coinbase_paper_depth_collect.py`)

Credential-free as before. `--exit-fee-bps` is now optional: without it the
tape takes the strategist's configured paper fee (`MW_CYCLE_FEE_BPS`, 60 bps
by default), and every tape records `fee_source` (`declared` or
`configured_default`). `build_spec()` builds the tape header for tests and the
CLI.

### Account-backed collector and pilot

- `backend/paper_exit_adapter.py` rechecks the holding after the window, under
  its own 15-second request deadline, and records only
  `post_window_holding_unchanged`: `true`, `false`, or `null` when the read
  failed. No balance is written.
- The pilot reports `pilot_settings.post_window_holding` (`unchanged`,
  `changed`, `unverified`, or `not_recorded` for tapes written before the
  recheck existed). Only `unchanged` and `not_recorded` can be official.
- Synthetic tapes (`synthetic_position` or `market_data_check` set to anything
  but a literal `false`) still can never be an official result.

## Tests

- `backend/tests/test_paper_fills.py`: parity of a single level with the
  pilot's mark and the strategist's sale, the three-level walk (0.03 BTC
  across $45,000 / $44,900 / $44,800: $1,347.00 gross, $1,333.53 net at 1%),
  slippage-then-fee order, insufficient depth, book validation, rates.
- `backend/tests/test_cycle_strategist_depth.py`: ladder execution, a short
  ladder, malformed ladders, existing guards with a ladder, `live_guarded` /
  pause / cap, the dry-run flags on every outcome, and the fetcher's depth
  option.
- `backend/tests/test_paper_safety_gate.py`: reads the source and fails if
  any module names a Coinbase order, order-preview or money-movement
  endpoint, or sends a non-GET request to a Coinbase host other than the
  OAuth sign-in token exchange. It also checks the authenticated client is
  GET-only and that the public quote paths only read.
- `backend/tests/test_paper_exit_adapter.py`: the post-window recheck through
  the CLI (unchanged, changed, unreadable).
- `tests/test_coinbase_paper_depth.py` and `tests/test_coinbase_paper_exit.py`:
  dust-spike and real rebounds, thin opening quotes, the fee default, an
  end-to-end public tape that is never official, holding states, and pilot
  parity.

The tests were committed before the implementation (`a39955b`, then
`f2a5eed`). Backend suite from `backend/`: 1298 passed, 33 skipped. Repo
`tests/`: 1506 passed, 1 failed, the long-standing
`tests/test_seed_fixture.py::test_load_dev_volume_fixture`, which this branch
doesn't touch.

## Follow-up: opt the in-app dry-run exits into ladders

The in-app cycle pass still requests level 1, so its dry-run exits keep using
the top-of-book rule. Turning depth on is one line in `backend/app.py`, in
`_cycle_pass_quote_fetcher`:

```python
return fetch_live_quotes(products, depth_levels=50)
```

`scripts/run_local_agents.py` passes `fetch_live_quotes` as the fetcher and
would need the same argument. The level-2 Exchange book is the full
aggregated book, so it is a larger download than level 1. It is fetched only
for the exits Mode B is about to simulate.

## Earlier live market-data run (public BTC-USD, synthetic positions)

30 seconds, 50 levels, fee 60 bps and slippage 10 bps (both declared),
official timing limits. All 30 books arrived. Quote ages ran from 146 to
1418 ms (median 806). The book timestamp advanced on 26 of 29 steps and never
went backward.

| Synthetic size | Depth replay | Top-bid pilot, same books | Depth cost vs top bid |
|---|---|---|---|
| 0.01 BTC | valid, 30/30 slots | rejected, 10 thin | median 0, max 0.8 bps |
| 0.1 BTC | valid, 30/30 slots | rejected, 28 thin | median 0.45, max 1.0 bps |
| 1 BTC | rejected, 29/30 (1 short book) | rejected, 30 thin | median 1.2, max 1.6 bps |
| 5 BTC | rejected, 1/30 | rejected, 30 thin | — |

This run predates the executable-price rebounds. No rule triggered (BTC moved
far less than 8%), so the trigger and execution paths are covered by tests
only.

## Caveats

- `insufficient_book_depth` means the requested levels didn't cover the
  position. It doesn't say the market couldn't.
- Book levels are a snapshot. Nothing models queue position, hidden
  liquidity, or the book moving during the sell.
- Partial exits are not modelled: a sale either fills completely in the
  supplied book or is refused.

## Still open

- No official four-hour window has been run. The 30-second account-backed
  smoke check passed on OSMO-USD on November 13.
- Holdings that also trade on the matching USDC pair are ineligible for the
  account-backed pilot until a rule for valuing USDC prices and commissions
  is agreed. Dollar-sized orders stay ineligible until a private order
  inspection settles how their fills are reported.

Tapes are kept locally in `%USERPROFILE%\.moonwalking\analysis\coinbase-paper\`,
outside Git.
