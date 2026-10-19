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
prior highs above the daily close are sorted upward as H1–H3, and up to three prior
lows below it downward as L1–L3. The guide calls them Prior high 1–3 / Prior low
1–3. Equal-to-close references are counted separately.
No percentage-distance gate, probability or extrapolated price is introduced.

These are prior observations, not validated support/resistance, fresh untested
levels or a forecast of the next cycle peak. Exceeding H1 need not exceed a more recent
high or establish a new cycle high. Levels beyond a cleared reference are places
to reassess after the price response, not a promised path. Missing overhead/downside
references remain unavailable; macro calculations never fill those slots.

The primary guide shows prior high/low prices, signed daily-close distances, turn dates,
confirmation dates and source explanations. Macro recovery/extension arithmetic
is in a closed disclosure. Macro band and E? projection default off. The plot starts
with up to 52 weekly bars (160 daily bars); Earlier and Fit history preserve access
to older history and A–D. The plot labels the same daily H/L references, with label
spacing that does not alter their actual price lines. Gap/replay/confirmation rules
and the underlying macro arithmetic remain intact.

## Evidence and narration

The additive `evidence.next_run` field contains the same shared result and dated
anchors. Worker engine and analysis fingerprints include it. New narration catalogs
use this map and exclude macro ratios. A plan must include both H1 and L1 when
available, and cannot select a farther reference while skipping a nearer one.
The structured-output schema enumerates only plans passing those constraints.
Legacy packets retain their previous macro catalog for compatibility. A changed
catalog/renderer invalidates prior narration cache; failure still uses a labelled
deterministic explanation from the new catalog.

The visible guide and Python narrator share `frontend/src/utils/chartDisclosures.json`.
The daily pivot rule has not been tested directly. Weekly-scale equivalents
behaved like arbitrary lines at similar distances in Coinbase USD 2022–2026.
This dated limitation is a required `study-limits` fact in every plan, including
fallback and cached output; its source is the pinned Study 2 record. Older macro
packets receive the weekly-study limitation. A copy change changes the catalog
fingerprint and cannot reuse a prior explanation. Saved R/S packet labels are
normalized to H/L from side/rank without changing any price, date, or source ID.

## Real saved AMP example

These are actual archived Coinbase daily observations through 2026-10-18, not
illustrative numbers or live quotes. Baseline daily close: $0.0007881. The table
uses the corrected labels; it is not a new AMP price download.

| Reference | Price | Distance | Extreme date | Confirmed UTC |
|---|---:|---:|---|---|
| H1 | 0.000825 | +4.7% | 2026-10-13 | 2026-10-16 |
| H2 | 0.000840 | +6.6% | 2026-10-16 | 2026-10-19 |
| H3 | 0.0008499 | +7.8% | 2026-10-08 | 2026-10-11 |
| L1 | 0.000710 | -9.9% | 2026-05-28 | 2026-05-31 |
| L2 | 0.000620 | -21.3% | 2026-10-12 | 2026-10-15 |
| L3 | 0.0006111 | -22.5% | 2026-10-02 | 2026-10-05 |

Confirmation at 2026-10-19 00:00 UTC is available at the exclusive cutoff after
the completed Oct 18 day. None of these values establishes where the run will peak.

## Initial verification (before the wording correction)

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

## Wording correction and verification

Branch `codex/chart-evidence-wording-20261019`, based on `fb59304a`.
Prepared explanations now describe observations instead of proposing regain,
retest, or rejection paths. The optional local measurement calls its boundary
the selected A anchor; internal numerical fields and touch grading are unchanged.
The model still selects IDs only, with the installed `qwen3.5:9b` configuration.
No study result, per-coin badge, new agent, model download, or order control is added.

- Full frontend suite: 559 tests in 48 files passed with `--maxWorkers=2`.
  The unrestricted run hit the existing 5-second interaction timeout under
  concurrent load; the timeout and test assertions were not relaxed. Token/Figma
  synchronization and production build passed. Final link and anchor-label
  adjustments were followed by all 28 affected frontend tests and a fresh build;
  the anchor-label test checks the displayed value against the selected A price.
  Existing Browserslist, bundle-size,
  and AlertsPanelGlobal act warnings remain.
- 51 offline Python narration/worker tests and four offline packet tests passed.
  They cover required study facts, schema choices, omitted-context fallback,
  cached-plan rejection, copy-change invalidation, old-label normalization, and
  all catalog availability states. The lexical regression check allows only
  reviewed negative clauses such as "not validated support/resistance"; an
  affirmative claim following that disclaimer still fails. It is a copy test,
  not a runtime free-prose filter or proof of factual semantics.
- The committed public RENDER exports at `09011e3c` pass OHLCV parity and all
  138 weekly replay cutoffs (977 daily records, 138 complete weeks). A real-data
  packet renders the required study limitation through deterministic fallback,
  passes the wording scan, and contains H/L IDs with no macro references.
  No network/model call or live database was needed for those checks.
- Browser verification on that snapshot covers prior-high explanation dates,
  signed daily distances, the study disclosure/link, collapsed macro calculations,
  H/L chart labels, and 390px phone wrapping. No page-width overflow or browser
  errors observed. The temporary viewport was reset. Preview data and screenshots
  remain ignored under `frontend/.runtime/`.
- Repository guardrails and whitespace checks passed. The existing collector,
  installed chart task, PIT task, other worktrees, and production are untouched.
  The changed worker code and shared disclosure file must be integrated together
  before the scheduled worker can use this revision.
