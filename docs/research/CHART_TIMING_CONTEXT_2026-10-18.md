# Chart dates, historical durations and level reactions

## What the user can inspect

The price-map reading links to a new **When to look, and what to look for**
panel below the chart. Larger A–D and recent a–d legs show actual extremum date
ranges, elapsed calendar days, prices, percentage changes and when both turns
were confirmable. Missing earlier anchors remain missing. These durations are
historical observations, not expected durations for another move.

View buttons inspect a leg or a dated reaction with surrounding candles.
Short ranges use native daily candles; ranges over 360 days use weekly candles,
with at most 400 displayed at once. This is a display choice. The analysis
interval, original selected anchors, level values and replay cutoff stay fixed.
Large overlays are hidden during inspection to keep small price moves readable.
Fit history restores the full analysis view. Interval/replay changes clear the
inspection. Zooming to an old period is retrospective inspection with the
current replay cutoff, not a reconstruction of what was known on that date;
change Replay through for that purpose.

## Precisely what a reaction record means

`frontend/src/utils/chartTiming.js` defines the calculations. For each latest
confirmed high/low, inspect a symmetric linear-price band around its price.
The UI offers ±0.5%, ±1% (default) and ±2%. These are explicit exploration
settings, not earned thresholds or validated support/resistance boundaries.

Only completed native UTC daily candles through the replay cutoff qualify.
An episode cannot begin before the level's `confirmed_at`. A touch means
`daily.low <= band.upper && daily.high >= band.lower`, including boundaries.
Consecutive touching candles form one date range only when their daily buckets
are contiguous. A non-touch day or a missing day separates ranges. The number
of touching daily candles is shown; intraday residence time is unknown.

For each episode, report the immediately preceding candle's relation to the
band if available, then the first following candle entirely outside the band.
It can be above, below, pending or unknown across a gap. The panel shows that
candle's date and close. It does not equate every below-band exit with a
resistance rejection; an approach from above can instead be a downward pass.

The seven-day follow-up compares the last touch candle's close with the close
of the seventh subsequent daily candle. All seven contiguous candles must be
present and completed by the cutoff. Otherwise the return is null, with a
pending or missing-data state. The review checkpoint is
`last_touch_candle.end + 7 * DAY`: a follow-up availability time, not a predicted
price-arrival date. This is a descriptive close-to-close change without fills,
fees or a claim of trade profit. Later visits can overlap follow-up windows.

The panel reports missing daily intervals after confirmation and shows at most
the latest three episodes while retaining the total observed count. A missing
interval can hide a touch; counts are not a complete event history when there
are gaps. No visits is distinct from an unfinished follow-up. Original pivot
formation is not counted as a later retest.

## Real-data example

On the unchanged FET Coinbase snapshot through 2026-07-23:

- Larger legs A–B, B–C and C–D took 441, 492 and 680 days respectively.
- Recent legs took 47 days (2026-02-06–2026-03-25), 53 days
  (2026-03-25–2026-05-17) and 15 days (2026-05-17–2026-06-01).
- With the default ±1% setting, the recent .1843 low reference has five
  later touch ranges after its 2026-06-01 confirmation. For example,
  June 20–23 contains four touching daily candles; June 24's candle is
  entirely below the band, closing .1729. The seven-day change from the
  final touch close is approximately -1.5%.
- The July 2–5 touch range is followed by a fully below-band candle on
  July 6, with a .1715 close; its seven-day change is approximately -11.8%.
- The .2884 recent high has no later ±1% visit after its June 22 confirmation
  through this cutoff. That does not establish an expected next-touch date.
- At ±2%, the low reference has six touch ranges. The July group starts
  July 1 instead of July 2. The displayed width therefore matters and is not
  concealed as a fixed resistance rule.

These numbers are observed and derived from the snapshot, not illustrative
trading forecasts. The SHA-256 is
`6cfed7c82b077af72c30af8dcd82ff819357a8e5eac7873101c0840ebe25cc31`.
Provider revisions and true historical availability remain outside this audit.

## Checks and boundaries

Ten new synthetic tests cover dated-extremum versus confirmation timing,
confirmation gating, contiguous/gapped episode grouping, inclusive boundaries,
inspection width, exact seven-day closes, unresolved follow-ups, bad input,
physically truncated replay, future-price poisoning and chart-focus navigation.
Inspection preserves the original narrative, analysis interval and replay
cutoff; Fit history and the interval controls clear it.

`scripts/verify_chart_timing.mjs`, adapted from the existing read-only verifier,
checks FET and RENDER at 259 and 138 weekly cutoffs. All **397 cutoffs** pass,
with **764 level checks** and **428 recurring episode records**. These are audit
counts across overlapping prefixes, not independent setups or trades. Fully
truncated input and future-price-poisoned input produce identical results;
no seven-day return appears before its required candles are available.
RENDER SHA-256:
`5e1906f46de73138230479ca9e1e55b9e1402001ac7c066b3b0b55530ff29b60`.

`npm run verify` passes token/Figma synchronization, production build and
**538 tests in 45 files**. Guardrails and whitespace checks pass. Existing
Browserslist, main-chunk and two AlertsPanelGlobal act warnings remain.
Browser checks cover the real FET dates, both inspection widths, leg/reaction
focus, unchanged replay and levels, return to full history and responsive
containment. Screenshots remain ignored under `frontend/.runtime/`.

This slice does not provide calibrated future arrival windows, continuous
time at resistance, intraday event ordering, matched historical analogues or
support/resistance probabilities. A future timing model needs point-in-time
event definitions, censored non-arrivals, regime comparisons and holdout
calibration; projecting a past duration onto today's calendar does not supply
that evidence. No new market requests, data-store changes, branch consolidation
or production deployment were needed. Branch: `codex/macro-chart-20261018`.
