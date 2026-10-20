# Current daily swing and weekly cycle: AMP, COTI, PYTH

The user wants both horizons, focused on the upcoming move rather than a
recovery fraction of a years-old decline. The preview now displays both lists,
with separate dated closes, source dates and confirmation intervals. Daily
observations use 90 days; weekly observations use 365 days of complete weeks.
These are explicit display scopes, not optimized prediction rules or time forecasts.

## Completed run

Public Coinbase product metadata and daily candles were fetched on 2026-10-20.
Daily cutoff: 2026-10-20 00:00 UTC, through the completed October 19 candle.
Latest complete week ends October 18. No missing daily intervals occur inside
the observed spans: AMP 1,958 days, COTI 1,881, PYTH 607. Incomplete edge weeks
are excluded. Initial COTI/PYTH requests received 429; bounded retries at a slower
pace completed. No alternate venue or region workaround was used.

| Coin | October 19 daily close | Prior daily highs beyond that day's high, within 90 days |
| --- | ---: | --- |
| AMP | $0.0008167 | None above the day's $0.000970 high |
| COTI | $0.010819 | $0.012800 (+18.3%), $0.013750 (+27.1%), $0.014240 (+31.6%) |
| PYTH | $0.073270 | $0.081860 (+11.7%), $0.087840 (+19.9%), $0.088960 (+21.4%) |

Distances in this table use the daily close, not the candle high. These are
observed prices, not predicted peaks, fresh/untested levels or a promised sequence.
AMP's nearest daily highs ($0.000825, $0.000840, $0.0008499) are all inside the
October 19 range. The UI and required narration now disclose that fact instead
of allowing those prices to read as new destinations. A missing overhead
observation stays missing; an old macro calculation is not substituted.

| Coin | October 18 weekly close | Nearest prior weekly highs above that weekly close |
| --- | ---: | --- |
| AMP | $0.0007881 | $0.0008771, $0.0008800, $0.0011800 |
| COTI | $0.010751 | $0.013400, $0.015200, $0.015800 |
| PYTH | $0.074200 | $0.088960 |

The first two AMP weekly prices were also spanned by the later daily candle.
Weekly rows are ranked against the weekly close; for PYTH, $0.0737 is below
the weekly close even though it is above the later daily close. This is why
mixing baselines silently gives different lists. The diagnostic JSON additionally
compares weekly observations against the daily close explicitly for like-for-like
distance inspection; its weekly comparison is not the UI's weekly ranking.

Switching the chart between Weekly and Daily changes its H/L lines and legend
to that interval. Both guide lists remain visible, and each Explain control
uses its own list's close. Historical macro arithmetic remains collapsed and
opt-in. The manual A/B/C geometry tool remains exploratory. This change does
not claim to reproduce a creator's video method; the older COTI/PYTH videos
have not been supplied or replayed at their original publication cutoffs.

## Reproduction

`scripts/chart_reference_comparison.mjs` is an offline CLI accepting one or
more chart-history JSON files and optional `--as-of YYYY-MM-DD`. It reports
90/365-day daily scopes, weekly observations, recent turns, prices already
inside the latest daily range, and the original macro arithmetic for comparison.
It never fetches data, changes the installed worker or writes an input file.

```powershell
node scripts/chart_reference_comparison.mjs AMP-history.json COTI-history.json PYTH-history.json
node scripts/chart_reference_comparison.mjs --as-of 2026-10-18 AMP-history.json
```

Saved output: `data/chart-reviews/next-cycle-2026-10-20.json`, including source-file
SHA256 values. Raw fetched histories and browser previews are ignored under
`frontend/.runtime/next-level-comparison-20261020-071326/`. The history snapshot
script and worker public client remain the download paths. Source contract:
[Coinbase candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).
Coinbase history is not established as the video creator's feed.

## Funding: scope and a confirmed audit defect

Reviewed committed Study 3a source at
`830762d5f3226de184c2277d1e0ddc4dee1b3e3c`. Its primary F1 contrast tests the
event-day mean funding regime, negative versus crowded positive, after +10%
days. It does not test changes in funding jointly with changes in open interest,
spot price or volume over intraday windows. A failure of that contrast does
not establish that funding has no other role. Funding is also an actual carry
payment linked to perpetual-versus-spot pricing; that mechanism alone establishes
no predictive edge. See [Hyperliquid's funding mechanism](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding).

**Needs revision before certifying the study.** In
`scripts/move_study/funding_study.py:89` at the reviewed commit,
`binance_day_funding` reads only the event day's monthly archive while filtering
the window `(t 00:00, t+1 00:00]`. A month-end event needs the next month's
midnight settlement too. The fetch plan also schedules only event months.

Confirmed independently using two real public BTCUSDT archives:

- January archive ends January 31 at 16:00 UTC; February starts February 1 at 00:00.
- For January 31, the current function returns an 8-hour-equivalent mean
  of **0.0050665%** from two prints. The specified three-print window gives
  **0.0022886667%**. This BTC example remains neutral under both calculations.
- An illustrative synthetic fixture with -0.01%, -0.01%, +0.10% demonstrates
  a possible classification change: current code says negative (-0.01% mean);
  the complete window says crowded (+0.0266667% mean). This fixture is not market data.

Evidence, archive URLs and checksums:
`data/research-reviews/funding-window-audit-2026-10-20.json`.
The numerical reproduction executed the four relevant AST-extracted functions
from the pinned committed source, with temporary CSV fixtures and the real archive
pair; it did not modify Claude's checkout or run the entire historical study.

Required repair: download/read adjacent months when the window crosses a month,
distinguish unavailable archive coverage from evidence of no perpetual, cover the
boundary with a regression test, and rerun all preregistered tests with changed
rows/regime counts reported. Do not claim the defect reverses the published
conclusion. It can affect F1 regime assignment; the F2 listing comparison need
not change when other same-day prints already establish perp presence.
F2 also explicitly excludes events from October 1 onward because the current
Binance monthly archive was unavailable; that coverage restriction must stay visible.

After repair, separate research questions can examine funding changes alongside
OI/price changes, and extreme funding relative to that coin's own past distribution.
Freeze features, horizons, comparisons and multiplicity controls before joining
future outcomes. These interactions remain untested hypotheses. Study 3b's proposed
taker-flow experiment has not been started by this work.

## Sentiment: actual state checked on this PC

- The existing market-wide service has Fear & Greed/global-market/derivatives
  adapters. Optional coin-context/provider code is not evidence of configured
  social coverage. The new coin-specific forward-news/social pipeline is unfinished.
- At this check, local port 8003 refused connections; Flask health on 5003 was
  healthy, but `/api/sentiment/latest?symbol=AMP` returned 503. This is a local
  service availability gap, not a production health assessment.
- The separate PIT task is running. A read-only SQLite query at 07:13 UTC found
  **24,030 positioning snapshots, 178 venue symbols**, from October 19 15:18 UTC
  through October 20 07:13 UTC, all with funding and OI. Source-health rows for
  Coinbase products/status and Hyperliquid were live. This is under 16 hours
  of collection, not enough for outcome claims.
- PYTH had 135 snapshots; AMP/COTI had none under those exact venue symbols.
  Ticker-matched Coinbase IDs are not independently verified token identities.
  Do not turn absent coverage into neutral scores or map another token by guesswork.
- Next sentiment implementation work is service integration/recovery and a
  coin-identity-aware forward RSS logger with `first_seen_utc`, revisions, source
  provenance and unavailable states. Only collected, verified material should feed
  later coin-specific summarization or sentiment testing.

The collector, PIT task, live databases and installed chart task were not changed.
The installed chart checkout has five pre-existing modified files containing other
active A/B/C work; it was read only. These branch commits need reviewed integration
with that work before the installed worker or deployed app can use them.

## Verification

- Full frontend suite: 561 tests in 48 files passed with two workers. The final
  weekly-baseline test deliberately uses a newer daily close and was followed by
  all 28 affected tests passing. Production build and token/Figma sync passed.
- 52 offline Python narration/worker checks and seven offline packet/comparison
  checks passed, including replay/future-price poisoning and missing-week states.
- Nine existing sentiment truth/positioning tests passed, with PIT writes disabled.
  Passing these tests does not repair the observed local service outage.
- All three fetched histories passed evidence production and deterministic
  narration-plan validation, including required daily-range context. Zero model
  calls; no assertion about newly accepted local-model output.
- Browser inspection: all three coins show both lists; AMP has the honest
  beyond-daily-high empty state; COTI switches between weekly/daily plot labels and
  its weekly explanation uses the weekly close. COTI wraps at 390px without page
  overflow. Macro details stay collapsed. No browser console errors observed.
  Temporary viewport override reset; screenshots stay ignored under `.runtime/`.
- Repository guardrails and whitespace checks passed. Existing Browserslist,
  chunk-size and unrelated AlertsPanelGlobal act warnings remain.
