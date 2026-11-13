# Codex assignment · Get the runner study the data it is missing

The Radar work now has a concrete goal and one replicated finding. Read
[the brief](../research/RADAR_RUNNER_STUDY_BRIEF_20261113.md) and
[the fresh replication result](../research/LIVE_MOVERS_FRESH_REPLICATION_RESULTS_20261113.md)
on branch `claude/instant-radar-fresh-replication-20261113` at the commit that
contains this file. The owner wants the mover boards to show which coin is most
likely to keep running, using the best pieces of six board options. Carbon is
designing the study. This session runs the analysis. The study is blocked on
data that only the collector and the candle archive can supply, and that is the
work proposed here, in priority order.

## 1. Backfill one-minute candles for the whole universe

`~/.moonwalking/data/candle_archive.sqlite` stops at 2026-10-12. Two of the five
candidate signals (a move against the coin's own normal, and coin-specific
against market-wide movement) and the whole early-watch study need one-minute
candles for the same days as the board episodes.

- Extend the existing `backend/candle_archive.py` pull from 2026-10-12 to the
  present for every USD product that was listed at any point in that span,
  including products since delisted. The source is public and needs no
  credentials.
- Then keep it current with a daily catch-up, so new days arrive with candles.
- Deliver a manifest: products, date range, rows, windows fetched and windows
  that returned nothing, and the hash of the archive at that point.

Done means the analysis can join any board episode from 2026-09-06 onward to
that coin's and Bitcoin's surrounding one-minute candles.

## 2. Record what the boards show but the ledger does not

`backend/board_outcomes.py` tracks the top eight rows of three boards. Verified
on the fresh rows: `entry_rank` is only ever 1–8, and the boards recorded are
`ignition_1m`, `confirmation_3m_up` and `confirmation_3m_down`.

- Track rows 9–16, so the "show more" rows have outcomes. Keep rank recorded so
  the default eight stay separable.
- Record the short-window board the user actually sees if it is not
  `ignition_1m`, and the 1-minute losers if that board is shown.
- Keep the change additive and versioned. Existing episodes and the frozen
  eligibility rules must stay reproducible, so a new snapshot or model version
  is better than changing the meaning of existing rows.

## 3. Fill the fields that are null

In every fresh row sampled, `quote_volume_usd`, `realized_volatility_pct_hour`
and their age fields are null. The retention fix that fills them was written on
a separate branch on 2026-10-27 and is not running on the local collector.
Deploy it there, or say what blocks it. These fields are the direct inputs for
the activity gate and the unusual-move ranking.

## 4. Record quotes, so the bounce question can be closed

Outcomes use last-trade prices. The main doubt about the replicated fade is
that some of it is bid/ask bounce after a fast move. Store best bid and ask at
entry and at each outcome checkpoint, with their ages. If that is costly, entry
and the five-minute checkpoint are enough to start.

Also make the peak fields distinguishable from missing: `max_favorable_15m` and
its siblings default to zero, so a true zero and "never updated" look the same.
Record how often the tracker observes a price, since the peak is only as fine
as that cadence.

## 5. Point the checkpoint files at the new result

`docs/ai/RESUME_HERE.md` and `docs/ai/ACTIVE_WORK.json` do not mention the
fresh replication or this direction. They are yours, so they were left alone.

## A suggestion for the owner to decide, not a task

The 5-second capture has stopped before warmup in every attempt beyond four
products. The one-minute candle route can test the early-watch idea now. It may
be worth parking the 5-second reader until the one-minute study shows whether
finer data is needed. That is a change of priority and is the owner's call.

## Boundaries

No live score, ranking or weight changes. No Coinbase account calls; everything
here uses public market data. Preserve the frozen captures and the locked
results. Work on your own branch and leave this branch's files as they are.
