# Candle archive

`backend/candle_archive.py` keeps raw Coinbase Exchange candles (OHLCV) for
the periods the live collector didn't see, in its own SQLite file:
`MW_CANDLE_ARCHIVE_DB`, on Tom's PC
`%USERPROFILE%\.moonwalking\data\candle_archive.sqlite`.

## What it is, and isn't

- **It is** the exchange's own price and volume tape, minute by minute.
  The live stores prune theirs (price snapshots after 24h, minute volume
  after 48h), so this is the only minute-level price history Moonwalking has
  for anything older.
- **It isn't** live collection, and it isn't a replay of Moonwalking's
  signals or boards. Which alerts fired, how the boards ranked live,
  order-book state and social inputs can't be rebuilt from candles. The live
  record of those is in the live stores, and for the periods this PC missed,
  in production's database.
- No live code path reads it, so it can't be mixed into live rates by
  accident. Anything derived from it must carry its own methodology version.
  `archive_meta` and every row of `fetched_windows` record the source
  (`coinbase-exchange-candles`) and methodology (`exchange-candles-v1`).

## Reading it

| Table | Contents |
| --- | --- |
| `candles` | `product_id`, `granularity` (seconds: 60 = 1m, 3600 = 1h), `ts` (candle open, unix UTC), `open`, `high`, `low`, `close`, `volume` (base currency) |
| `fetched_windows` | Each 300-candle window actually fetched, with `status` (`ok`, `not_found`) and candle count |
| `archive_runs` | One row per run: range, request count, 429s, errors, status |
| `archive_meta` | What the file is |

Coinbase returns no candle for an interval with no trades. Inside a fetched
window, a missing minute means **no trades**, not missing data. Outside every
fetched window, nothing is known.

## Running it

```powershell
$env:MW_BOARD_OUTCOMES_DB = "$env:USERPROFILE\.moonwalking\data\signal_outcomes.sqlite"
$env:MW_CANDLE_ARCHIVE_DB = "$env:USERPROFILE\.moonwalking\data\candle_archive.sqlite"
$py = "$env:USERPROFILE\.moonwalking\venv\Scripts\python.exe"
& $py scripts\archive_candles.py --list-gaps                  # periods the collector missed
& $py scripts\archive_candles.py --gaps                        # 1m candles for all of them
& $py scripts\archive_candles.py --start 2026-10-05T10:00 --end 2026-10-12T10:30
& $py scripts\archive_candles.py --start 2026-09-05T00:00 --granularity 3600
```

Times without a zone are local. The default product list is every
USD-quoted Coinbase product plus every product the board outcome store has
seen. Re-running is cheap: windows already fetched are skipped, and windows
sit on a fixed grid so overlapping ranges line up. A window whose last
candle hadn't closed yet is stored but fetched again next run.

**Rate:** at most 2 requests/s by default, halving after any 429. The live
collector uses about 5 of Coinbase's ~10 public requests/s from the same IP,
so don't raise `--rate` much past 3. For scale, 1-minute candles for one week
of ~490 products is about 17,000 requests, roughly 2.5 hours at 2/s.
