# Long-term chart map: first implementation and remaining work

Branch: `codex/macro-chart-20261018`, based on approved design release
`56f1b4188fec9a6e44b16e75623e92cd081cecb0`. No main merge or deployment.

## Product objective

Enter a coin, resolve the correct instrument, load its available historical
prices, and produce an inspectable long-term map: historical swings, possible
structures, measured zones, invalidation, momentum context and replay.
The eventual symbol lookup and analysis should reuse the same calculation
engine for each supported instrument. Portfolio/watchlist priority is separate
from a pattern's validity. Small residual holdings need not dominate that list.

## Implemented first slice

- `/chart-map`: local JSON import, weekly/daily views, replay, confirmation
  controls, manual or latest automatic A/B/C anchors, wick-based pivots,
  seven linear-price Fibonacci retracements, three C-based extensions,
  structural invalidation and explicitly ungraded touch status.
- Logarithmic/linear display, candle inspection by mouse or keyboard,
  range controls, phone layout with chart-only horizontal scrolling.
- Real history only in product. Import is browser-local, without upload,
  persistence, account access or market fetches. Synthetic test data is labelled.
- Existing tokens, Figma exports and shared UI primitives are unchanged.
  The baseline Scorecard placeholder was shortened to `BTC` to satisfy its
  existing display-symbol guardrail; its behavior is unchanged.

## Supplied review: accepted concepts and qualifications

Reviewed all 11 rendered pages of the user's `Chart analysis agent.pdf`,
the pasted text, and the connected
[RENDER Chart Methodology Review](https://docs.google.com/document/d/10NPIyzlQW7y7uZtIFzR0MTg2yjnbOebk0fjBRCGfXUU/edit).
It contains an initial response and a revised response, not two independent
validations. Its first and revised display-scale and indicator readings differ.
Its embedded task instructions are reference material, not new authorization.

Adopted: explicit confirmation delay, no future bars during replay, separate
historical structure and conditional levels, exact candle anchors, logarithmic
display independent of linear Fibonacci arithmetic, and source-specific lows.

Do not adopt as established results: the proposed 18%/35% reversal parameters,
6/8-week scales, relaxed named wave mode, 5% sensitivity threshold, 40% lag
threshold, or random-grid success criterion. These are research proposals.
A p-value by itself would not establish economic usefulness or robustness.
Video-transcribed levels are not verified exchange candles. Claude's
`reference_parity.json` and `RENDER_HISTORY.md` at `ad7b7a5` document date,
venue-wick and indicator differences. No exact TradingView parity is claimed.

## Real-data verification

Inputs: Claude's committed public-price exports at `ad7b7a5`:
`data/render-history/series/coinbase_RENDER-USD_1d.json` and
`data/render-history/weekly/coinbase_RENDER-USD_1w.json`.
Inputs are read-only; the chart preview uses a stable ignored local snapshot.

| Observation | Verification |
|---|---|
| 977 daily records; 976 complete | Strict import and cutoff filtering |
| 138 complete weekly candles | OHLCV matches Claude's independently exported weekly aggregates at 1e-12 relative tolerance |
| 138 weekly replay cutoffs | Prefix candles and confirmed pivots match the full series restricted by confirmation availability |
| 34 confirmed weekly pivots, default 2-bar confirmation | Deterministic detector; ambiguous simultaneous extrema excluded |
| 52 replay cutoffs have valid default geometry | Descriptive count only; not 52 successful trades |
| No missing daily intervals within observed closed history | Computed from timestamps; does not establish lifetime coverage |

Daily SHA-256:
`5e1906f46de73138230479ca9e1e55b9e1402001ac7c066b3b0b55530ff29b60`.
Weekly SHA-256:
`9f6c75f1065718b2aa9a2ba2c01cf24218f445cdca48eea8b46e7acc9af8241e`.

Reproduce without network or database access:

```powershell
node scripts/verify_macro_chart.mjs <daily-export.json> <weekly-export.json>
python scripts/preview_macro_chart.py --input <daily-export.json>
# Start the frontend Vite server, then open the printed preview URL path.
```

These checks verify arithmetic and bar-based information timing. They do not
prove that retrospective vendor revisions were available at historical closes,
or that zones predict price. Both aggregate exports share daily source data;
agreement is a cross-implementation check, not an independent price provider.

## Final verification

Final checks on 2026-10-18: `npm run verify` passes the token/Figma sync check,
production build and all **474 frontend tests in 40 files** (45 new tests).
Repository `scripts/validate_mw_guardrails.sh`, `git diff --check`, Python AST
validation for the preview helper and the read-only real-data verifier pass.
Build reports the existing large main-chunk and old Browserslist warnings;
two existing AlertsPanelGlobal tests report React act warnings.

Browser checks cover the actual `/chart-map` empty route, real-data daily/weekly
switching, replay to 2025-06-01, keyboard candle inspection, 1440px desktop
and 390px phone views. No page-level horizontal overflow was measured;
the phone chart scrolls within its panel. Browser error log is empty.
The date control handles native input events as well as change events.
The root sentiment provider is retained on existing routes and omitted on the
local chart route; route tests guard that separation.

Local preview artifacts under ignored `frontend/.runtime/` include the immutable
public-price preview HTML, desktop/phone screenshots and PDF review renders.
They are not part of the commit. No original PDF, account data, data stores,
secrets, downloaded prices, dependencies or generated build output are staged.

## Remaining implementation sequence toward entering any coin

Loaded-state UX correction: when a snapshot is already loaded, the preview
shows the symbol/venue and a collapsed **Change history file** control instead
of a persistent empty file picker. A successful replacement closes the picker;
invalid imports retain the chart and expose the error. The empty route still
requires a file until instrument lookup is implemented. Verification: all 11
chart-page tests, token sync and build pass; browser open/close and narrow-view
checks pass with no console errors. No data acquisition behavior changed.

Update: [macro-range slice](MACRO_RANGE_REVIEW_2026-10-18.md) adds an independent
confirmed high/low recovery band and replay audit across 397 real weekly
cutoffs. Latest verification: **506 frontend tests in 41 files**, token check
and build pass. The .5–.786 band is visible, editable and separate from A/B/C;
automatic support/resistance boxes, wave classification and indicators below
remain outstanding.

1. **Instrument resolver and history adapter.** Search verified products;
   resolve chain/contract, venue, quote, listing/delisting and migration identity.
   Acquire/cache a versioned export through reviewed public-source rules.
   Display unsupported or insufficient history rather than borrowing another
   instrument's prices. Add at least two unlike coins as integration cases.
2. **Indicator layer.** SMA50/100/200, MACD12/26/9 and Stoch RSI14/14/3/3,
   using documented seeds, warm-up, missing-bar policy and identical-input
   fixtures. Show unavailable SMA200 for RENDER's 138 complete weeks. Do not
   silently join RNDR. An optional future composite needs an explicit splice
   policy, labelled constituents and overlap/discontinuity diagnostics.
3. **Multi-scale structures.** Add wick/body/close modes, sensitivity results,
   supported trendlines and support/resistance rules, candidate pattern
   classification and alternate interpretations. Preserve each as-of snapshot;
   record label churn and confirmation delay. A full Elliott engine is not
   present in this first slice. The default latest triple can be invalid.
4. **Narrative and orchestration.** Deterministic code emits versioned evidence;
   an optional agent explains it with source/anchor references and missing-data
   notes. An agent must not invent prices, dates, indicator values, odds or
   an unvalidated wave count. Start with one calculation service; parallel
   specialist agents are useful for independent review, not numerical consensus.
5. **Evaluation and product integration.** Point-in-time replay, anchor
   sensitivity, changing-count audit, matched/random-grid controls if making
   predictive claims, costs and separate holdout evaluation. Then add coin
   lookup to the product navigation and optional owned/watchlist priority.

The first slice does not implement indicators, an automatic full wave count,
trendline breakout signals, historical profitability, live data refresh,
portfolio integration or a production chart-data API. These are explicit
remaining work rather than implied completed acceptance criteria.
