# Coinbase paper depth prototype — handoff

Branch `claude/coinbase-paper-depth-prototype-20261112`, based on `1ccf3d4`.
Paper only, credential-free, synthetic positions only.

## Why

The official pilot marks a position against the single best bid and treats any
quote whose top-of-book size is below the position as thin. On a live 30 second
BTC-USD window the best level was at times worth about $10, so a $714 position
was thin on some polls and the window was rejected, though every quote was fresh.
The pilot was measuring top-of-book size, not what a sell would realise.

## What changed

- `scripts/coinbase_paper_depth.py` — a separate replay. It walks the bid ladder
  to price a market sell, then applies the pilot's slippage and fee convention to
  that walk. When the ladder can't cover the position, it returns
  `INSUFFICIENT_DEPTH` with the shortfall and leaves net proceeds unset, so a
  partial fill is never reported as the position's value. When a single level
  covers the position, the result equals the pilot's `_mark` exactly (tested).
- It reuses the pilot's staleness rule and its `_window_quality` function
  unchanged, and keeps the pilot's two execution corrections: the execution book
  must be newer than the trigger book, and a missed first execution makes the
  hold comparison `FIRST_EXECUTION_UNKNOWN`. An execution quote that can't cover
  the position counts as a miss (`EXECUTION_INSUFFICIENT_DEPTH`).
- It uses its own schema, `depth-prototype-1`, and refuses any tape that isn't
  marked `synthetic_position: true`. Its `official_pilot_result` is always
  `false`, whatever window the tape covers.
- `scripts/coinbase_paper_depth_collect.py` — records a tape from Coinbase's
  unauthenticated `market/product_book` endpoint (up to 50 levels). It reads no
  environment variables and calls no account endpoint, and a test checks that.
- **The official pilot gets one change, and it only tightens.** In
  `scripts/coinbase_paper_exit.py`, a tape that declares `synthetic_position` or
  `market_data_check` (any value except a literal `false`) can no longer be an
  official result, even over an aligned four-hour window with official settings.
  The new field `pilot_settings.synthetic_tape` reports this. Freshness, gap,
  coverage and fill-history limits are unchanged.

## Tests

`tests/test_coinbase_paper_depth.py` adds 14 tests: an exit that consumes three
bid levels (fees, VWAP, and the $3 the top-bid estimate would have overstated),
insufficient depth both directly and on an execution quote, a trigger followed by
an unavailable execution quote (the miss survives a later successful exit),
a trigger on a quote with too little depth, the newer-book rule, a four-hour
synthetic run that stays non-official, refusal of account-backed and pilot tapes,
a bid ladder that must descend, and the collector (with no network calls).
`tests/test_coinbase_paper_exit.py` adds a parametrized four-hour synthetic-tape
test and updates the exact-match assertion for the new `synthetic_tape` key.

On this branch the full suite gives 456 passed, 65 skipped, 1 failed. The failure
is `tests/test_seed_fixture.py::test_load_dev_volume_fixture` (`assert 60 == 10`),
and it fails the same way on `1ccf3d4`, so this branch didn't cause it.

## Live market-data run (public BTC-USD, synthetic positions)

30 seconds, 50 levels, fee 60 bps and slippage 10 bps (both declared), official
timing limits. All 30 books arrived. Quote ages ran from 146 to 1418 ms (median
806), none were negative and none exceeded 2000 ms. The book timestamp advanced
on 26 of 29 steps and never went backward.

| Synthetic size | Depth replay | Top-bid pilot, same books | Depth cost vs top bid |
|---|---|---|---|
| 0.01 BTC | valid, 30/30 slots | rejected, 10 thin | median 0, max 0.8 bps |
| 0.1 BTC | valid, 30/30 slots | rejected, 28 thin | median 0.45, max 1.0 bps |
| 1 BTC | rejected, 29/30 (1 short book) | rejected, 30 thin | median 1.2, max 1.6 bps |
| 5 BTC | rejected, 1/30 | rejected, 30 thin | — |

On BTC-USD up to 1 BTC, walking the ladder costs at most 1.6 bps, far below the
assumed 60 bps fee and 10 bps slippage. The binding problem was the thin rule,
not slippage.

## Caveats

- `INSUFFICIENT_DEPTH` means the requested levels didn't cover the position. It
  doesn't say the market couldn't. The thinnest book returned 0.71 BTC across 50
  levels, so the 1 BTC miss partly reflects the request size.
- Book levels are a snapshot. The prototype doesn't model queue position, hidden
  liquidity, or the book moving during the sell.
- Rebound signals still come from the top bid; only the proceeds use the depth
  walk.
- No rule triggered in the live window (BTC moved far less than 8%), so the
  live run didn't exercise the trigger and execution paths. The tests cover them.

## Pending

The **account-backed smoke test is still pending.** This prototype bypasses cost-basis
verification, fill pagination and the fee-tier lookup, so it doesn't stand in
for that test. The key's eligible holdings are thin pairs that fail the 2000 ms
freshness rule. Its liquid holdings fail the 500-fill pagination cap.

Tapes are kept locally in `%USERPROFILE%\.moonwalking\analysis\coinbase-paper\`, outside Git:
`btc-market-data-check-20261112-top-bid-covered.json`,
`btc-market-data-check-20261112-dollar-sized.json`, and
`btc-depth-20261112-30s.json`.
