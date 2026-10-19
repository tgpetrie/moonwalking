# Automatic coin history and explainable chart levels

## User flow

Open `/chart-map`, enter a symbol such as AMP, search, and select the exact
Coinbase/USD result. The browser loads daily history and builds the weekly map
without a file or anchor choices. Progress counts date ranges and candles;
Cancel stops a download. Another failed or cancelled selection preserves the
previous chart. Saved-file import and manual macro/local anchor controls are
optional disclosures. Local measured-move overlays are off by default.

This is the first connected provider, not universal token coverage. Search
currently matches symbols in Coinbase's USD product catalog. Unknown symbols
show an unsupported state; no product identifier, price history, chain identity
or predecessor-token splice is guessed. Non-online products are marked as
historical markets. Token migration lineage is not established by a ticker.

## Source and implementation

- [`publicChartHistory.js`](../../frontend/src/utils/publicChartHistory.js):
  anonymous public GETs to the fixed Coinbase Exchange host. Product identity
  is checked against base/quote fields returned by the catalog. No credentials,
  account APIs, backend workers, local database or owner's archive are used.
- [`ChartCoinSearch.jsx`](../../frontend/src/mvp/ChartCoinSearch.jsx): explicit
  product selection, loading/progress/cancel, error and stale-response handling.
- [`MacroChartPage.jsx`](../../frontend/src/mvp/MacroChartPage.jsx): automatic
  chart/narrative, optional controls and separate macro/recent labels.
- [`MacroPriceChart.jsx`](../../frontend/src/components/charts/MacroPriceChart.jsx):
  recent high/low and .5/.786 numeric labels directly on the chart. Optional
  lowercase a–d differs from the larger historical A–D.

[Coinbase's product catalog](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs)
defines the identities searched. The
[candle documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
specifies daily granularity, a 300-candle maximum, possible rows preceding the
requested start, and missing intervals when no ticks are published.

The loader requests 299-day windows from 2010-01-01 through the last completed
UTC day, with a 40-window safety limit. Empty early windows do not terminate a
backfill or establish a listing date. Each returned row is validated; only rows
inside that request's half-open window are retained. Identical duplicates are
collapsed, conflicting duplicates fail, gaps remain gaps, and open days are
excluded. Existing weekly completeness and confirmation rules remain in force.

One module-level queue spaces requests at least 1.05 seconds after the previous
response completes. Each request times out at 20 seconds. Rate-limit/service
responses have at most three attempts with backoff and Retry-After handling;
requests for a pause beyond two minutes stop rather than retry early. Queues
and caches are per browser module instance, not a server-wide multi-user
limiter. A reviewed shared service would be needed before scaling traffic.

Catalog and at most three successful histories are held in memory. History
cache keys include product and UTC cutoff day. Nothing is written to an owner's
data store or browser persistent storage. Reloading starts a new search session.
Public browser CORS access was verified for the actual AMP workflow. This
research implementation does not establish a redistribution license or approve
production release; no production deployment was made.

## Explanation boundaries

The default reading states the latest confirmed high and low with dates, the
selected large decline and its 50–78.6% recovery reference, the percentage move
needed from the latest completed close, and the selected low that would be
undercut in a downside case. Prior turning points are not automatically
classified as tested support/resistance, and no entry/stop instruction follows.

“Would this make a new high?” compares the chosen reference against the highest
price in the **available history before the latest completed candle**, not
just the selected confirmed swing. The latest candle is excluded from that
reference so a newly completed breakout can be recognized. It explains partial
recovery below the old peak, retesting it, or an
extension above it, and flags a close already above that reference high. A high
in available venue history is not represented as an asset-wide all-time high.
This distinction matters for AMP: the available historical high exceeds the
highest pivot qualifying under the current confirmation window.

Optional small a–d names restart on the latest four alternating confirmed
swings, retaining a more extreme consecutive same-kind pivot. Macro A–D retains
its separately documented convention. Replay recalculates both from available
confirmed data only. These are two descriptive scales, not a validated pattern
match, causal explanation of price movements, or a continuation forecast.
Comparisons of macro highs and drawdown percentages are historical arithmetic.
Screen angles are not used as a similarity metric because zoom/axis transforms
change them. No success probability, “most likely” path, validated analogue
search, full wave classification or forecast date is claimed.

## Verification

The actual browser searched AMP, selected the Coinbase/USD result, checked
21 bounded date ranges and rendered the chart without a file. The chart showed
recent low .00035 (2026-08-19), recent high .0008771 (2026-09-26), and the
selected recovery band .047225–.0740375. These are real provider observations
and derived references from this run, not illustrative trading targets.
The historical high in available complete weeks was .123 (2021-06-16), whereas
the selected confirmed macro high was .0941 (2021-07-26). The default recovery
reference is 39.8% below .123; the optional 1.618 reference .1520375 is 23.6%
above it. Neither establishes likelihood. Prices can be revised by the provider.

Synthetic tests cover discovery/identity, explicit bounded windows, request
spacing, caching, malformed/conflicting/empty data, rate backoff, cancellation,
late responses, unsupported symbols, retained charts and an end-to-end mocked
coin-to-chart flow. Geometry checks distinguish the earlier observed high from
the selected pivot and test causal small-letter selection. Existing manual
geometry tests now explicitly open optional tools. No test uses network data.

Browser checks also cover the optional nested/future overlays, both new-high
explanation cases, numeric labels, optional-control defaults and responsive
containment. An unsupported-symbol search retained AMP, and the browser error
log was empty. Temporary viewport overrides were reset. `npm run verify`
passes token/Figma sync, build and **528 tests in 43 files**. Repository
guardrails and `git diff --check` pass. Existing Browserslist, main-chunk size
and two AlertsPanelGlobal act warnings remain. Local screenshot artifacts,
including `amp-automatic-chart.jpg`, remain under ignored `frontend/.runtime/`.
Existing Figma tokens/primitives, other agents' worktrees, main and production
are unchanged. Branch: `codex/macro-chart-20261018`.
