# Freshness checks for chart runs

The user reported that the AMP view looked stale and asked how each run can use
the latest data. Two different clocks were being conflated: the latest completed
daily/weekly candle, and the latest reported market trade. A saved preview file
also remains a fixed snapshot until the user explicitly refreshes it.

## Findings

- The installed AMP worker had daily candles through October 19, the latest closed
  UTC day at the October 20 check. This does not describe October 20's forming day.
- The browser client previously cached a product's result until the next UTC day.
  A repeat analysis could skip the provider entirely, including recent revisions.
- The worker previously allowed an apparently successful refresh when returned
  history trailed the requested cutoff. Its summary mentioned the problem, but
  a successful run alone was too easy to read as proof of current data.
- The loaded-history label used the requested/export cutoff instead of the last
  actual complete candle. A current export timestamp could conceal a missing tail.

## Run contract

`Analyse <coin>` and **Refresh latest data** now force a public provider recheck,
using `cache: no-store`. After an initial backfill, the client retains earlier
candles and re-requests the last seven daily buckets, treating that refreshed
interval as authoritative, including missing or revised rows. New UTC days extend
that overlap automatically. Ordinary non-forced API callers can reuse a result for
at most 60 seconds, and its actual coverage is checked again on return.

Both browser and worker require the latest actual completed daily candle to reach
the expected UTC cutoff. A five-minute margin after midnight allows settlement.
The browser rechecks after the optional ticker request; the worker rechecks before
publishing, including if the cutoff advanced during calculation/narration.
Missing latest candles fail the current run and retain the previous chart or
last-good worker data. No missing candle or neutral price is invented. Delisted
or inactive products may therefore remain available only as dated historical files.
This establishes observed tail coverage, not independent proof of exchange accuracy
or of uninterrupted trading inside every daily bucket.

The UI displays:

- actual daily history through, and expected daily history through;
- when the history was fetched/rechecked;
- the latest reported trade price, its exchange trade time, and provider check time;
- a clear unavailable state if the ticker fails or is malformed;
- a notice after a quote check is more than two minutes old;
- a visible historical-snapshot state when saved daily coverage is behind.

The freshness display recomputes its age every 30 seconds without making background
market requests. A refresh is explicit. Failed requests preserve the earlier
timestamped result; they do not make its timestamp newer. Saved-file import and
historical replay still work, with their actual dates visible. The offline
comparison CLI now reports `saved_snapshot`/`historical_replay` mode and candle
freshness; it never claims to contact the provider.

The ticker is a last-trade snapshot, not streaming market data. An older last-trade
time can mean no newer trade was reported, even when the provider check just
completed. See [Coinbase ticker contract](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker).
Daily/weekly pivot calculations retain their completed-candle closes. A forming
day's current trade is shown separately and cannot become a confirmed swing high
or low. Fresh prices also do not make an old anchor recent: anchor and confirmation
dates remain visible in both lists.

## Implementation and verification

- `frontend/src/utils/chartFreshness.js`: actual-tail versus expected-cutoff checks.
- `frontend/src/utils/publicChartHistory.js`: forced runs, bounded cache lifetime,
  incremental authoritative overlap and optional validated ticker context.
- `MacroChartPage.jsx`: freshness display and explicit refresh; stale/failed responses
  cannot replace the previous chart. `ChartCoinSearch.jsx` requests fresh analyses.
- `ChartWorkerStatus.jsx`: a recent/successful task with old or unrecorded candle
  coverage is visibly stale. The saved history can still be opened for inspection.
- `scripts/chart_worker.py`: reject a stale tail and cutoff rollover before success;
  use uncached public reads, retaining last-good data on error.

Full frontend suite: **571 tests in 49 files passed** with two workers; token/Figma
sync and production build passed. The final cache assertions were followed by all
14 history-client tests passing, including next-day rollover. **54 offline Python
worker/narration tests** and **seven offline packet/comparison checks** passed.
Checks cover stale exports with current claimed cutoffs, settlement boundaries,
cache expiry/forced refresh, revisions, quote failure, separate price baselines,
and last-good preservation. Repository guardrails and whitespace checks passed.
Existing Browserslist, bundle-size and unrelated act warnings remain.

An actual public AMP worker refresh matched actual last candle end to the expected
October 20 00:00 UTC cutoff. The completed daily close stayed $0.0008167; a separate
ticker check returned $0.0008042, trade time October 20 07:50:44 UTC. The browser
refresh path also completed against Coinbase and displayed both clocks. A second
browser refresh finished in about three seconds using the cached history overlap,
displaying $0.0008069, trade time 07:52:02, provider checked 07:54:29 UTC. These are
dated observations, not current quotes for a future reader. Smoke output and
screenshots are ignored under `frontend/.runtime/`. No model calls were needed.

## Integration boundary

The review preview runs this code. The installed AMP scheduled task still points
to `Projects/Moonwalking-MacroChart`, which contains five existing modified A/B/C
files. It was read only, and no collector/PIT task or live database was changed.
Integrate reviewed commits with that work before moving the installed task to this
version; do not overwrite the other checkout. No main merge or production deploy.
