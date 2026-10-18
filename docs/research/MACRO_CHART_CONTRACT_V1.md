# Macro chart prototype: data contract and interpretation

Base: `56f1b418` (`codex/design-system-production`), the approved Figma-ready
design system. Implementation: `codex/macro-chart-20261018`.

## First slice

`/chart-map` is a local-file research workspace, independent of portfolio,
authentication, market workers, scoring and notification routes. It uses the
existing UI primitives and semantic tokens without changing generated tokens.
No example market prices are shipped. Synthetic prices exist only in tests.

The browser reads one explicitly selected JSON file, without uploading it or
persisting it. No backend or account connection is required by the workspace.
Raw data belongs in ignored local output, not a public fixture or Git history.

## Accepted acquisition contract

The production-history boundary accepts Claude's committed
`moonwalking.market-history/v1` daily exports. Reviewed data branch:
`claude/render-history-data` at `ad7b7a5` (includes the script repair at
`1d66107` and the later reference/indicator fixture). The adapter requires native
UTC daily bucket opens, explicit quote/base units, and `provenance.stitched=false`.
It preserves `series_id`, coverage and source provenance. It independently
validates timestamps, completeness, uniqueness and OHLC rather than trusting
the supplied counts. It recomputes weekly candles from complete daily inputs;
the separately exported weekly file serves as a parity check.

The same contract supports another coin without changing chart calculations.
Automatic symbol discovery/acquisition is a later integration, not implemented
by the local file workspace. RNDR, RENDER, EUR, USD and USDT remain separate.

### Internal format and alternate input

The top-level object has:

| Field | Type / meaning |
|---|---|
| `schema_version` | Exact string `bhabit.chart-history.v1` |
| `instrument.product_id` | Canonical venue instrument identifier |
| `instrument.symbol` | Display base symbol, uppercase letters/numbers |
| `instrument.venue` | Explicit venue/source of prices |
| `instrument.quote_currency` | Explicit quote units; no USD/USDT substitution |
| `interval_seconds` | `86400`: native UTC daily candles |
| `captured_at` | Integer Unix seconds when this immutable export was captured |
| `candles` | Array of daily objects described below |

Each candle has integer Unix-second `start` and `end` (exclusive), with
`end - start = 86400` and `start` at UTC midnight. `open`, `high`, `low`,
`close` are positive finite numbers; `volume` is a nonnegative finite base-unit
number. `complete` is an explicit boolean. Duplicate timestamps and inconsistent
OHLC are rejected. A complete candle cannot end after the export capture.

The table describes the normalized `bhabit.chart-history.v1` form, also accepted
directly. Instrument mappings, migrations, provider provenance, response hashes
and coverage notes accompany the upstream export. The adapter accepts one
instrument and venue and never joins different tokens or venues.

## Time and data gaps

Weekly buckets begin Monday 00:00 UTC. All seven closed native daily bars are
required. Incomplete weeks are excluded, not padded or interpolated. Daily gaps
are counted within the observed first/last closed-bar span; this is not proof
of complete lifetime history. Prices are labelled low/high in analysed history.

Replay includes only closed candles ending at or before the selected UTC cutoff,
capped by `captured_at`. No chart feature is computed from excluded future bars.
Backfilled daily OHLC is a retrospective observation; this does not establish
that every vendor revision was available at the historical bar close.

## Pivots and anchor selection

The initial pivot detector uses strict local highs/lows with 1–4 completed bars
on each side (default 2). `time` is the extremum's bar start. `confirmed_at` is
the end of the final right-side bar, not the extremum date. Missing intervals
invalidate the relevant pivot window. Equal extrema do not qualify. A candle
that is both a high and low is excluded because intrabar swing order is unknown.

Confirmed individual pivots remain independently defined. The default anchor
selector alternates high/low, retaining the more extreme of consecutive same-kind
pivots, and takes the latest three; it does not search older triples for a
favourable outcome. Replaying earlier dates recalculates from that prefix only.
Selecting anchors manually is exploratory and does not constitute a historical
strategy signal or a calibrated Elliott-wave count. Controls reset anchors when
replay date, timeframe, confirmation setting or imported dataset changes.

## Geometry

For ordered anchors A, B, C, require low/high/low or high/low/high with C inside
the original A–B leg. Let `d = B.price - A.price`.

- Retracement at ratio r: `B.price - r*d`, with r = .236/.309/.382/.5/.618/.702/.786.
- Pullback reference band: the .382 and .618 levels, ordered by price.
- Extension from C: `C.price + k*d`, with k = 1/1.272/1.618; nonpositive
  extension prices are withheld.
- Structural invalidation: A's extreme, using a wick touch at/through A.

These are linear-price conventions on either a logarithmic (default) or linear
display. Equal ratios have equal screen spacing on the logarithmic display;
changing display scale does not change anchors or Fibonacci prices.
No future date, probability, liquidity
estimate, fee-adjusted return, order instruction or success rate is inferred.
The chart's right-hand strip is a display area for horizontal levels, not a
forecast time axis. A/B/C are anchor names; full Elliott counts require a
separate reviewed implementation and validation. Gemini's supplied parameters
are proposals, not earned thresholds or permission to reclassify old pivots.

Scenario availability is the maximum anchor `confirmed_at`. Touch status uses
only subsequent completed bars whose starts are at/after that instant. Target
and invalidation touches are reported separately, without claiming first-touch
ordering, execution, or outcome validation.

## Ownership and next integration

- Claude: verified RENDER/RNDR history and source/coverage manifest.
- Codex: this renderer, calculation module, adapter and tests.
- Gemini: video-grounded chart conventions and independent methodology review.

No broad branch consolidation is part of this work. The stopped
`codex/unified-20261018` branch is not the feature base.

Acceptance checks include future-price poisoning, right-bar confirmation delay,
weekly gap handling, invalid structure rejection, exact Fibonacci arithmetic,
local import behavior, empty states, keyboard inspection, and the existing
design-token/build/frontend suite. Browser review must cover narrow and wide
viewports once verified real history is available.
