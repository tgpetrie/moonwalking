# RENDER / RNDR historical data

Data preparation for the long-term RENDER chart. Charts and integration are
Codex's; this is the inventory, the validated data, and the contract.

Branch `claude/render-history-data`, based on `56f1b418`. Data as of
**2026-10-18 00:00Z** (last closed day 2026-10-17).

## Bottom line

- There are **two tokens**, not one: RNDR (Ethereum) and RENDER (Solana).
  Coinbase lists them as separate currencies and both traded there side by
  side from 2024-02-15 to 2025-06-26. They are kept as separate series.
- The longest unbroken series is **Coinbase RENDER-USD, 2024-02-15 to now
  (977 daily candles, no missing day)**. RNDR-USD adds 2022-02-03 to
  2025-06-26 (1,240 days) as its own series.
- **No all-time low is established.** The lowest daily low in the
  RENDER-USD file is 0.651 (2025-10-10). The lowest in RNDR-USD is 0.27
  (2022-06-18). CoinGecko's aggregate record cites 0.0367 on 2020-06-16,
  which is in neither file. A chart can label these only by what they are
  ("lowest in Coinbase RENDER-USD history"), never "all-time".

## 1. Identity (verified)

| Token | Chain | Contract | Coinbase status |
| --- | --- | --- | --- |
| RNDR | Ethereum | `0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24` | delisted |
| RENDER | Solana | `rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof` | online |

Both contracts come from Coinbase `/currencies` and match the platform
addresses CoinGecko lists for `render-token`. CoinGecko treats the two as one
asset; Coinbase does not, and that is why the series are not merged.

| Venue | Product | Quote | Status | Daily history |
| --- | --- | --- | --- | --- |
| Coinbase Exchange | RENDER-USD | USD (fiat) | online | 2024-02-15 to 2026-10-18 |
| Coinbase Exchange | RNDR-USD | USD (fiat) | delisted | 2022-02-03 to 2025-06-26 |
| Coinbase Exchange | RNDR-USDT | USDT (stablecoin) | delisted | 2022-02-03 to 2025-06-26 |
| Coinbase Exchange | RNDR-EUR | EUR (fiat) | delisted | 2022-02-03 to 2025-06-26 |

Probed and not found on Coinbase: RNDR-BTC, RENDER-USDC, RENDER-USDT,
RENDER-BTC, RENDER-EUR, RENDER-GBP. Binance (RENDERUSDT, RNDRUSDT) answered
HTTP 451 from this location; no data was taken and no workaround was tried.
No other venue was checked, so Coinbase is the only venue in the data.

## 2. History, gaps, limits

**Daily (Coinbase native daily candles, fetched back until the source
returned empty windows).** For all four products the source answered OK with
no rows for at least ~600 days before the first candle, so each file spans
that product's life on Coinbase. First candle date is the first day with
trades, not a confirmed listing date.

| Series | Candles | Complete | Days with no trades inside span |
| --- | --- | --- | --- |
| RENDER-USD | 977 | 976 (2026-10-18 is still open) | 0 |
| RNDR-USD | 1,240 | 1,240 | 0 |
| RNDR-USDT | 1,240 | 1,240 | 0 |
| RNDR-EUR | 1,239 | 1,239 | 1 |

**Intraday (existing candle archive, RENDER-USD only).** Not refetched.
- 1h: 9,020 candles, 2025-10-01 12:00Z to 2026-10-12 17:00Z. Two 5-hour
  stretches with no trades (2025-10-25 16:00-20:00Z, 2026-05-08 02:00-06:00Z).
  30 of the candles (2026-10-11 12:00Z onward) sit outside the recorded
  fetch windows, so an absent hour there does not prove "no trades".
- 1m: 37,109 candles in two ranges, 2026-09-06 12:00Z to 2026-09-23 14:00Z
  and 2026-09-24 05:00Z to 2026-10-12 18:00Z. Nothing before 2026-09-06, and
  nothing between 09-23 14:00Z and 09-24 05:00Z.
- The archive holds no RNDR products. It is an archive of "periods the live
  collector missed", not a year-long daily history, so daily history before
  2025-10 came from the public pull below.

**Limits that matter for the chart**
- Nothing before 2022-02-03 on any Coinbase product. The asset traded
  earlier elsewhere (CoinGecko's low is from 2020).
- The archive's last hour is 2026-10-12; 2026-10-12 to 2026-10-18 has daily
  candles only.
- Coinbase leaves out days (and hours, minutes) with no trades. These files do
  not fill them.

## 3. Validation

All in `data/render-history/validation.json`.

- All 39 public requests returned HTTP 200 except the two Binance calls (451).
- Boundary duplicates between request windows (3 to 4 per product) were
  byte-identical rows; none conflicted.
- Every candle: aligned to UTC midnight, positive prices, `low <= open,close
  <= high`, volume >= 0. No failures, no zero-volume days.
- No day-over-day close move above 40% in any series.
- **Daily vs archived hourly (RENDER-USD, 374 days wholly inside archived
  hourly coverage):** OHLC identical on all 374. Volume differs slightly on
  18 days (median 0.009%, max 0.60%), no day above 1%. No day present in
  one and absent in the other, so "absent day = no trades" holds.
- **RENDER-USD vs RNDR-USD on 498 overlapping days:** median close ratio
  1.0003 (5th-95th percentile 0.967-1.005). Close to 1:1 but not equal, which
  is further reason not to treat them as one book.

## 4. Weekly aggregates

ISO weeks, Monday 00:00Z to Sunday 23:59:59Z, built from the daily series
only: open = first day present, close = last day present, high/low =
extremes, volume = sum. A week is `complete` only when all 7 days fall inside
the series' span and have closed.

| Series | Weeks | Complete | Incomplete (flagged, not dropped) |
| --- | --- | --- | --- |
| RENDER-USD | 140 | 138 | week of 2024-02-12 `starts_before_first_candle`; week of 2026-10-12 `open_period` |
| RNDR-USD / USDT / EUR | 178 | 176 | week of 2022-01-31 `starts_before_first_candle`; week of 2025-06-23 `series_ends_mid_week` |

## 5. Data contract: `moonwalking.market-history/v1`

Schema: [market-history.schema.json](market-history.schema.json). Files are
under `data/render-history/`:

```
index.json           lists every series file
identity.json        tokens, contracts, markets, venues checked
coverage.json        per-series coverage, lineage, intraday archive, all-time-low status
validation.json      every check above, machine-readable
series/coinbase_<PRODUCT>_1d.json
weekly/coinbase_<PRODUCT>_1w.json
raw/                 unmodified source responses with URL, fetch time, SHA-256
```

One file is one venue, one product, one granularity:

```jsonc
{
  "contract": "moonwalking.market-history/v1",
  "series_id": "coinbase-exchange:RENDER-USD:1d",
  "as_of": "2026-10-18T00:00:00Z",
  "asset":  { "symbol": "RENDER", "name": "Render Network", "chain": "solana",
              "contract": "rndrizKT3...", "coingecko_id": "render-token" },
  "market": { "venue": "coinbase-exchange", "product_id": "RENDER-USD",
              "base_currency": "RENDER", "quote_currency": "USD",
              "quote_kind": "fiat", "status": "online",
              "price_unit": "USD", "volume_unit": "RENDER" },
  "interval": { "granularity": "1d", "seconds": 86400,
                "bucket_timestamp": "open", "alignment": "UTC midnight" },
  "candles": [
    { "t": "2025-10-10T00:00:00Z", "o": 0, "h": 0, "l": 0, "c": 0, "v": 0,
      "complete": true, "flags": [] }
    // weekly candles add "week_end" and "days_present"
  ],
  "coverage":   { "first_candle": "2024-02-15", "last_candle": "2026-10-18",
                  "candle_count": 977, "last_closed_day": "2026-10-17",
                  "no_trade_ranges": [], "probed_back_to": "...",
                  "empty_probe_before_first_candle": true,
                  "lowest_daily_low": { "price": 0, "day": "...",
                    "scope": "this venue product, first candle through last candle in this file",
                    "is_all_time_low": false, "why_not_all_time": "..." } },
  "provenance": { "source": "coinbase-exchange-candles", "endpoint": "...",
                  "authenticated": false, "fetched_at": "...",
                  "raw_file": { "path": "raw/coinbase/...", "sha256": "..." },
                  "methodology": "coinbase-native-daily-v1",
                  "stitched": false, "derived_from": null,
                  "absent_day_means": "no trades on this product that UTC day" }
}
```

Rules the consumer can rely on:
- `t` is the bucket **open**, UTC, ascending, unique.
- `complete: false` means the bucket is open or only partly inside the
  series' span. Flags say why: `open_period`, `starts_before_first_candle`,
  `series_ends_mid_week`. `no_trade_days_inside_week` and
  `large_move_vs_prev_close` are information only and do not make a bucket
  incomplete.
- Absent buckets are not filled. A gap in an exchange series means no trades.
  `coverage.no_trade_ranges` lists them.
- Prices are in the quote currency, volume in the base currency. Never
  compare RNDR-EUR prices with USD series without saying so.
- `stitched` is always `false` and `provenance.authenticated` always `false`.
  RNDR and RENDER are not joined, by decision (see 5a). The chart may place
  them on one axis only as two labelled series (the overlap and ratio are in
  `coverage.json` -> `lineage`). Indicators are computed per series.
- `lowest_daily_low.is_all_time_low` is `false` and must stay false until a
  file proves full-life coverage. Label by `scope`.
- Methodology strings are versioned. A change to how a series is derived
  bumps them.

## 5a. Parity with the chart-methodology review

**Superseded in part by 5b**, which reads the video directly. The SMA and
MACD comparisons below were made against the wrong bar.

The review "RENDER Chart Methodology Review" (Gemini, from the video) gives
TradingView readings. `scripts/render_history/reference_parity.py` compares
them with Coinbase RENDER-USD weeks and writes
`data/render-history/reference_parity.json`. These are a reviewer's
transcriptions, not exchange data.

- **Several of the review's bar dates are wrong.** Its "current bar, Mon 12
  Oct '26" (O 1.9750 H 2.1995 L 1.7609 C 1.9960) is Coinbase's week of
  **5 Oct** to within 0.25% on every field. Its "local wave (5) high 2.4395,
  11 May '26" is the week of **25 May** on Coinbase (high 2.435). Its
  "17 Aug '26" bar fits no week well. Re-check dates against the video before
  using them as test fixtures.
- **Where dates line up, highs and lows mostly agree** (macro high 13.6352
  vs 13.649, Feb 2026 low 1.1238 vs 1.122, May 2025 bar within 0.07%). Several
  opens and closes are 4 to 18% off, which points to misreadings or a
  different price source.
- **The Oct 2025 liquidation wick depends on the venue.** Coinbase printed
  0.651 (2025-10-10). The review reads ~0.80 to 0.90. Any anchor or wave rule
  that uses wicks will give different answers per venue.
- **Indicators on the 5 Oct week, Coinbase RENDER-USD complete weeks:**
  SMA50 1.7048 (review 1.6998), SMA100 3.1839 (3.1332), MACD -0.0021 /
  signal -0.0898 / hist 0.0877 (-0.0018 / -0.0995 / 0.0977), Stoch RSI
  %K 94.29, %D 92.01 (inside the review's ranges).
- **SMA200 cannot be computed from RENDER-USD**: it has 138 complete weeks.
  The review's 3.7009 needs about four years of weekly closes, so the
  TradingView source must carry RNDR history. Joining RNDR-USD before
  2024-02-19 to RENDER-USD gives 3.6734. That figure is a comparison only and
  is not published as a series.
- **Decision (Tom, 2026-10-18): the series stay separate.** No joined
  RNDR→RENDER series will be built, so SMA200 is unavailable for RENDER-USD.
  The chart should show it as unavailable, with the reason (138 of 200 weeks),
  and not substitute another value. It first becomes computable on its own for
  the week of 2027-12-13, the 200th complete week counting from the first
  full week (2024-02-19). That week closes on 2027-12-19.
- The review's acceptance target "SMA within 0.05% of the video values"
  cannot hold across venues. Hold indicator parity to identical input closes
  instead: `indicator_fixture` in `reference_parity.json` has the last 100
  complete weeks with SMA50/100/200, MACD(12,26,9), RSI14 and Stoch RSI
  (3,3,14,14). Conventions are listed in the file. The EMA warm-up seed is the
  Pine reference example's convention. TradingView's built-in may differ in
  the first bars; this is not verified.

## 5b. The video itself (read 2026-10-19, supersedes the review's readings)

`scripts/render_history/video_reference.py` holds 61 weekly bars read
directly from frames of `macro render.mp4` (ffmpeg, 1 frame per second) and
compares them with Coinbase. Output: `data/render-history/video_reference_bars.json`.

- **What the chart is:** TradingView `RENDERUSD`, "Render · 1W · CRYPTO", an
  aggregated index, log price axis. It shows bars back to 2023, so it **joins
  RNDR history**. Moonwalking does not.
- **When it was recorded:** the live bar is the week of **2026-10-12** and its
  countdown reads "5d 2h" all the way through, so the recording is from
  2026-10-13, roughly 21:00 to 22:00 UTC. Live bar at that time: O 1.9961,
  H 2.2258, L 1.9706, C about 2.032 to 2.036.
- **Match with Coinbase:** from August 2024 on, every compared bar matches
  Coinbase RENDER-USD closely (median close difference 0.05%). From
  February to May 2024 the index matches **RNDR-USD**, not RENDER-USD, to
  within about 0.2%. That is the join, visible in the data.
- **One big exception: the Oct 2025 wick.** The index's low for the week of
  2025-10-06 is **0.5454**. Coinbase printed 0.651. Open, high and close match
  within 0.04%. Wick-based anchors differ by venue.
- **Indicators on screen** (the legend follows the hovered bar):
  - Week of 5 Oct (complete): SMA50 1.7049, SMA100 3.1838, SMA200 3.6930,
    Stoch RSI K 94.46 / D 92.06, MACD histogram 0.0877, MACD -0.0018, signal
    -0.0895.
  - Live week of 12 Oct (close 2.0322): SMA50 1.6997, SMA100 3.1332, SMA200
    3.7009, Stoch RSI K 93.24 / D 94.87, MACD histogram 0.0906, MACD 0.0238,
    signal -0.0668.
- **Our engine against the 5 Oct values**, on Coinbase RENDER-USD complete
  weeks: SMA50 1.7048 (-0.006%), SMA100 3.1839 (+0.003%), MACD histogram
  0.0877 (equal), signal -0.0898, MACD -0.0021, Stoch RSI K 94.29 / D 92.01.
  The averages are effectively identical; the small MACD and Stoch RSI gaps
  fit a different warm-up history (the index starts in RNDR's era). SMA200 has
  no Coinbase RENDER-USD value; the comparison-only RNDR join gives 3.6734
  against the index's 3.6930.

**Corrections to the Gemini review (and to 5a above):**
- Its "current bar, 12 Oct" OHLC (O 1.9750 H 2.1995 L 1.7609 C 1.9960) is the
  5 Oct bar, which the narrator hovered at about 0:49. Its SMA readings
  (1.6998 / 3.1332 / 3.7009) are from the live 12 Oct bar. Section 5a wrongly
  compared those SMAs against the 5 Oct week; against the right bar they
  agree as above.
- Its MACD "-0.0018 / -0.0995 / hist 0.0977" misreads the 5 Oct legend
  (histogram 0.0877, MACD -0.0018, signal -0.0895).
- Macro peak, week of 2024-03-11: video O 11.3823 H 13.6271 L 9.9340
  C 13.1381 (review: O 9.8118 H 13.6352 L 9.5931 C 12.6952).
- Wave A low, week of 2024-08-05: video O 4.5267 H 5.1221 L 3.4261 C 4.4820
  (review: O 4.8265 H 5.2071 L 3.3982 C 4.6800).
- Oct 2025 wick: 0.5454 on the index, 0.651 on Coinbase (review: 0.80 to
  0.90).
- The 2.43 local high is the week of 2026-05-25 (H 2.4331), not 11 May
  (H 2.0199).

Use the video's dates for references. Do not use its prices as Coinbase
fixtures; it is a different source.

## 6. Reproducing

```powershell
$py = "$env:USERPROFILE\.moonwalking\venv\Scripts\python.exe"
# 1. Public pull: unauthenticated, one request per 1.05 s, 39 requests
& $py -I scripts\render_history\fetch_public.py --out data\render-history\raw
# 2. Consistent copy of the archive; never read the live file
& $py -I -c "import sqlite3; s=sqlite3.connect('file:'+r'C:\Users\<you>\.moonwalking\data\candle_archive.sqlite'+'?mode=ro',uri=True); d=sqlite3.connect('archive_copy.sqlite'); s.backup(d)"
# 3. Build
& $py -I scripts\render_history\build_datasets.py --raw data\render-history\raw --out data\render-history --archive archive_copy.sqlite
& $py -I scripts\render_history\reference_parity.py --data data\render-history
& $py -I -m pytest scripts\render_history -q
```

The build is deterministic from `raw/` and the archive copy. Step 3 without
`--archive` skips the hourly cross-check and intraday coverage.

## What was not done

- No pull for the reference video: `macro render.mp4` could not be inspected
  here (no video tooling), so the design intent is taken from the brief only.
- No additional venues beyond Coinbase. Reaching the true all-time low needs a
  source that covers 2020 onward (an aggregator or another exchange) and its
  own provenance; that is a separate decision.
- Hourly and minute candles are not exported to JSON; they stay in the
  archive. Say if the chart needs an hourly file.
