# Next-recovery map — 2026-10-19

The user identified a framing error: the page presented recovery fractions of AMP's
2021–2026 decline under “Where price could go next.” The arithmetic did not establish
plausible levels for the next run. This change makes nearby observed structure primary.

## Selection and presentation

`frontend/src/utils/nextRunMap.js` is shared by the UI and offline evidence producer.
It uses completed daily candles at the replay cutoff, regardless of the chart's
weekly/daily display. The reference price is the last completed daily close. This
can differ from the completed weekly close shown in the historical chart statistics.

Daily pivots use the selected confirmation count (default two completed candles
each side). Existing strict-pivot, ambiguous-candle and contiguous-window rules apply.
Only turns inside the most recent 365-day span and confirmed by the daily cutoff
qualify. This is an explicit display scope, not an optimized or validated threshold.
Exact equal-price duplicates retain the latest confirmed occurrence. Up to three
prior highs above the daily close are sorted upward as R1–R3, and up to three prior
lows below it downward as S1–S3. Equal-to-close references are counted separately.
No percentage-distance gate, probability or extrapolated price is introduced.

These are prior observations, not validated support/resistance, fresh untested
levels or a forecast of the next cycle peak. Clearing R1 need not clear a more recent
high or establish a new cycle high. Levels beyond a cleared reference are places
to reassess after the price response, not a promised path. Missing overhead/downside
references remain unavailable; macro calculations never fill those slots.

The primary guide shows R/S prices, signed daily-close distances, turn dates,
confirmation dates and source explanations. Macro recovery/extension arithmetic
is in a closed disclosure. Macro band and E? projection default off. The plot starts
with up to 52 weekly bars (160 daily bars); Earlier and Fit history preserve access
to older history and A–D. The plot labels the same daily R/S references, with label
spacing that does not alter their actual price lines. Gap/replay/confirmation rules
and the underlying macro arithmetic remain intact.

## Evidence and narration

The additive `evidence.next_run` field contains the same shared result and dated
anchors. Worker engine and analysis fingerprints include it. New narration catalogs
use this map and exclude macro ratios. A plan must include both R1 and S1 when
available, and cannot select a farther reference while skipping a nearer one.
The structured-output schema enumerates only plans passing those constraints.
Legacy packets retain their previous macro catalog for compatibility. A changed
catalog/renderer invalidates prior narration cache; failure still uses a labelled
deterministic explanation from the new catalog.

## Real saved AMP example

These are actual archived Coinbase daily observations through 2026-10-18, not
illustrative numbers or live quotes. Baseline daily close: $0.0007881.

| Reference | Price | Distance | Extreme date | Confirmed UTC |
|---|---:|---:|---|---|
| R1 | 0.000825 | +4.7% | 2026-10-13 | 2026-10-16 |
| R2 | 0.000840 | +6.6% | 2026-10-16 | 2026-10-19 |
| R3 | 0.0008499 | +7.8% | 2026-10-08 | 2026-10-11 |
| S1 | 0.000710 | -9.9% | 2026-05-28 | 2026-05-31 |
| S2 | 0.000620 | -21.3% | 2026-10-12 | 2026-10-15 |
| S3 | 0.0006111 | -22.5% | 2026-10-02 | 2026-10-05 |

Confirmation at 2026-10-19 00:00 UTC is available at the exclusive cutoff after
the completed Oct 18 day. None of these values establishes where the run will peak.

## Verification

- Full `npm run verify`: 558 tests in 48 files, token/manifest synchronization and
  production build passed. Existing Browserslist, bundle-size and act warnings remain.
- 46 offline Python worker/narration tests passed. New checks exclude macro facts,
  require nearest references, reject skipped levels, constrain schema selections,
  and invalidate old macro narration cache.
- Four offline packet tests passed, including physical-prefix replay and poisoned
  future prices. Four shared-map tests cover date scope/distance order, replay,
  missing intervals and honest insufficient-history/price-discovery states.
- Real worker runs saved an accepted local-model explanation from the new map.
  An actual Windows scheduled-task run finished with result 0 and cached accepted
  next-run narration. The browser showed the new levels, collapsed macro disclosure
  and the dated R1 explanation. Runtime smoke artifacts remain ignored.
- Guardrails and diff checks passed. No production deployment or main merge.

An early revised model response omitted S1 and was rejected; adding valid-plan
enumeration to the output schema produced an accepted response. The fallback never
substituted distant macro prices. One frontend run under concurrent local-model
load failed one interaction test; subsequent complete verification passed.
