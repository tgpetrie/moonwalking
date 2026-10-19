# Point-in-time context log

Steps 1 to 3 of the build order in `SENTIMENT_SOURCES_VERIFIED_2026-10-19.md`.
It records market context **when we first see it**, so later studies can use
only what was known before an event. This is the fix for the hindsight problem
the cause review exposed.

## What exists

| Piece | File | What it does |
| --- | --- | --- |
| Log and schema | `backend/pit_log.py` | Separate SQLite file: `pit_context_log` (append-only), `symbol_registry`, `source_health`, `watch_state` |
| Coinbase watcher | `backend/pit_watch.py` | Polls `/products` and the status page; logs listings, status changes, removals and incidents |
| Positioning snapshots | hooks in `backend/sentiment_api.py` and `backend/derivatives_positioning.py` | Every fresh Hyperliquid / OKX / Coinalyze fetch is appended (market-wide BTC/ETH and per-coin), at most once per venue and symbol per 5 minutes |

Path: `MW_PIT_LOG_DB`, default `backend/data/pit_context.sqlite` (gitignored,
separate from every live store). `MW_PIT_LOG_DISABLED=1` turns writes off.
Tests always run with writes off unless they opt in with a temp path.

## Rules

- **Filter on `first_seen_utc`** (our clock). `source_published_utc` is the
  source's claim, normalised to UTC.
- Rows are never updated or deleted. A changed item is a new row whose
  `revision_of` points at the previous one.
- Missing values stay NULL.
- `product_id` is set only when that exact Coinbase product id is in the
  registry. Other venues' symbols are kept in `venue_symbol` and are never
  mapped by guesswork, so RNDR and RENDER, and colliding tickers, stay apart.
- The first watcher pass on an empty log writes `BASELINE` rows, not
  listings. Products that already existed were not listed at that moment.
- A log failure never reaches the caller: the hooks log a warning and carry on.

## Event types

| Event | Source | Meaning |
| --- | --- | --- |
| `BASELINE` | `coinbase_products` | Product present on the first pass |
| `PRODUCT_LISTED` | `coinbase_products` | New product id since the last pass |
| `PRODUCT_STATUS_CHANGE` | `coinbase_products` | Change in status, trading_disabled, cancel_only, limit_only, post_only, auction_mode or status_message (before and after in the payload) |
| `PRODUCT_REMOVED` | `coinbase_products` | Product id disappeared from the catalogue (logged once) |
| `STATUS_INCIDENT` / `_UPDATE` | `coinbase_status` | New or changed status-page incident. The page lists only its last 50 |
| `POSITIONING_SNAPSHOT` | `hyperliquid_perp`, `okx_perp`, `coinalyze_perp`, ... | Funding (`metric_primary`) and open interest, USD where known (`metric_secondary`) |

`source_health` keeps live / blocked / offline per source with the last
HTTP status and error (Binance shows `blocked` 451).

## Running the watcher

```powershell
$py = "$env:USERPROFILE\.moonwalking\venv\Scripts\python.exe"
& $py backend\pit_watch.py --once
& $py backend\pit_watch.py --loop --interval 300
```

Two unauthenticated requests per pass, 1.1 s apart.

**Smoke run (2026-10-19, scratch database):** first pass 842 products as
`BASELINE` (515 online, 327 not), 50 incidents; second pass recorded nothing
new; a per-coin call logged one RENDER-USD Hyperliquid snapshot (funding
0.0000125 per hour, open interest about $2.30M).

## Always-on task (installed 2026-10-19)

The watcher runs as the **"Moonwalking PIT Watch"** scheduled task, the same
shape as the collector task but fully separate from it (it never touches
"Moonwalking Collector" or port 5003).

- Code runs from a stable copy in `%USERPROFILE%\.moonwalking\pit`
  (`pit_log.py`, `pit_watch.py`, `run_pit_watch.ps1`, `INSTALLED.txt` with the
  source commit), not from a worktree.
- Writes `%USERPROFILE%\.moonwalking\data\pit_context.sqlite`.
- Logs: `%USERPROFILE%\.moonwalking\logs\pit-watch-events.log`,
  `pit-watch-stdout.log`, `pit-watch-stderr.log` (previous run kept as `.prev`).
- Triggers: at logon, plus a 5-minute backstop; the launcher restarts Python
  if it exits. One pass every 5 minutes, two requests per pass.
- Update or reinstall: run `scripts\windows\install_pit_watch_task.ps1` from a
  checkout, then `Stop-ScheduledTask` / `Start-ScheduledTask -TaskName "Moonwalking PIT Watch"`.
- Stop: `Stop-ScheduledTask -TaskName "Moonwalking PIT Watch"`; remove with
  `Unregister-ScheduledTask -TaskName "Moonwalking PIT Watch"`. Both leave the data alone.

First live pass (2026-10-19 13:53 UTC): 842 products as `BASELINE`, 50 status
incidents; both sources `live`.

The positioning hooks only write while the sentiment service or board runs
from this code. The collector runs from `Moonwalking-Runtime`, which does not
have it yet, so positioning snapshots start once this branch is merged and the
runtime is updated.

## Tests

`backend/tests/test_pit_log.py` (10 tests): baseline vs listings, status
change with revision link, single removal record, fetch failure marks health
and logs nothing, incident update chain, no ticker guessing, NULLs kept,
throttle, disabled mode, writer never raises, the per-coin hook.

Run with `python -m pytest -o addopts="" backend/tests/test_pit_log.py`
(the repo's `pytest.ini` asks for pytest-cov, which this venv lacks).
