# Build brief · slice 1: Signal lanes and FreshnessStamp

Exported from the Claude design canvas ("Build brief for the first slice" board), with the later design-pass decisions from the canvas added at the end.

Base: `codex/design-system-production` at `56f1b41`. Read `docs/DESIGN_SYSTEM.md`, `docs/FRONTEND_UI_RULES.md` and `docs/UI_CONTRACT.md` first.

## Goal

Make Ignition (1M) and Confirmation (3M) readable while rows update by giving each signal its own lane, and make the boards tell the truth when data is late.

- **Homepage improvement:** signal lanes in `TokenRowUnified`.
- **Reusable component:** `FreshnessStamp`, first used in the three board headers.

With `/data` failing for 70 seconds the pill stayed `LIVE`. `docs/FRONTEND_UI_RULES.md` already requires connection status to drive LIVE/STALE/DOWN, so this restores the written contract.

## Do not change

- `getMoveStatus`, `MOVE_STATUS_LABELS`, `deriveRowCue` thresholds, `live_score`, `BoardEvidenceLine` logic, or Live Strength. The draft scoring upgrade is separate research.
- `.bh-row` grid columns, `.bh-3m-grid`, the 1M two-mode layout, or board order.
- Rabbit hover and the `--emit-*` / `data-row-hover` contract.
- `--font-numeric`, the loaded font family, and `tokens.json`. This slice adds no tokens.

## Files

| Action | File | Change |
|---|---|---|
| New | `components/ui/FreshnessStamp.jsx` | Component, deriveFreshness, formatAge |
| New | `components/ui/FreshnessStamp.test.jsx` | Threshold, copy and status-change tests |
| Edit | `styles/ui-system.css` | .ui-freshness rules |
| Edit | `components/ui/DesignSystemPage.jsx` | Add all six stamp states to /design-system |
| Edit | `context/DataContext.jsx` | threeMinPublishedTs state, set beside both setThreeMin publishes, exported in value and deps |
| Edit | `hooks/useDashboardData.js` | Pass through threeMinPublishedTs |
| Edit | `components/DashboardShell.jsx` | Stamps in three headers, data-freshness on panels, status memo |
| Edit | `components/TokenRowUnified.jsx` | Rank delta moves into .bh-rank-stack, removed from .bh-symbol-markers |
| Edit | `components/GainersTable1Min.jsx` | Rank-delta hold 2600 becomes 8000 |
| Edit | `components/GainersTable3Min.jsx, LosersTable3Min.jsx` | Rank-delta hold 2600 becomes 24000, skeleton rows={8} |
| Edit | `components/TableSkeletonRows.jsx` | Div skeleton rows also get bh-row-grid |
| Edit | `index.css` | Lane, stale, pill and evidence rules appended at end |
| Edit | `docs/DESIGN_SYSTEM.md` | Add FreshnessStamp to the component table |

## FreshnessStamp

Props: `cadence` ("1m" or "3m"), `hasData`, `loading`, `warming`, `sourceAgeSeconds`, `lastSuccessMs`, `onStatusChange`, `className`. The stamp owns its 1-second tick. `DashboardShell` stores only the status from `onStatusChange`, so board rows do not re-render every second.

```js
// Production snapshots refresh about every 33s. These limits allow for that plus time for each board to publish.
export const FRESHNESS_THRESHOLDS = {
  "1m": { delayedAfterS: 42, staleAfterS: 45 },
  "3m": { delayedAfterS: 52, staleAfterS: 60 },
};
export const OFFLINE_AFTER_S = 60;

export function deriveFreshness({ cadence = "1m", hasData = false, loading = false, warming = false,
  sourceAgeSeconds = 0, lastSuccessMs = null, nowMs = Date.now() }) {
  if (warming) return { status: "warming", ageSeconds: null };
  if (!hasData && loading) return { status: "connecting", ageSeconds: null };
  if (!Number.isFinite(lastSuccessMs)) return { status: hasData ? "stale" : "connecting", ageSeconds: null };
  const fetchAge = Math.max(0, (nowMs - lastSuccessMs) / 1000);
  const ageSeconds = Math.round(fetchAge + Math.max(0, Number(sourceAgeSeconds) || 0));
  const limits = FRESHNESS_THRESHOLDS[cadence] || FRESHNESS_THRESHOLDS["1m"];
  if (fetchAge >= OFFLINE_AFTER_S) return { status: "offline", ageSeconds };
  if (ageSeconds > limits.staleAfterS) return { status: "stale", ageSeconds };
  if (ageSeconds > limits.delayedAfterS) return { status: "delayed", ageSeconds };
  return { status: "live", ageSeconds };
}
```

1M uses `lastSuccessMs={lastFetchTs}`. Both 3M boards use `lastSuccessMs={threeMinPublishedTs}`. All pass `sourceAgeSeconds={staleSeconds ?? 0}`.

| State | 1M | 3M | Copy | Rows |
|---|---|---|---|---|
| connecting | Loading, no rows | Loading, no rows | Connecting | 3M: 8 skeleton rows on the live grid. 1M: existing SkeletonGrid1m |
| warming | warming, no rows | warming3m, no rows | Warming baseline | Existing empty message |
| live | Age 42s or less | Age 52s or less | Live · 3s ago | Normal |
| delayed | Over 42s | Over 52s | Delayed · 44s ago | Normal, hollow stamp dot |
| stale | Over 45s | Over 60s | Stale · 1m 14s old · prices may have moved | Grey price and percent, no ambient motion, deltas hidden |
| offline | No successful fetch for 60s | No successful fetch for 60s | Offline · last data 1m 02s ago · retrying | Same as stale, rows stay visible |

Top `.bh-status-pill` reads the worst board state. Keep `fatal` as DEGRADED. Add delayed, stale and offline pill styles. Live becomes neutral, not amber.

## Signal lanes and tokens

| Lane | Location | Form | Tokens |
|---|---|---|---|
| Price direction | `.bh-cell-change` | Unchanged signed percent | --signal-positive, --signal-negative via --bh-gain, --bh-loss |
| Rank change | `.bh-rank-delta in .bh-rank-stack` | ▲2 or ▼1 on every board, aria-label "Moved up 2 on this board" | --text-muted, --text-2xs, --font-numeric |
| Move quality | `.bh-live-rank--*` | Same labels, 8px dot via ::before: filled, hollow, half, dotted | Confirmed and Extended --text-primary, Unconfirmed and Thin --text-muted, --text-2xs |
| Freshness | `.ui-freshness, data-freshness on .bh-panel` | State word plus age under the board title | --text-muted healthy, --danger stale and offline |

- `.bh-price-current`, `.bh-price-previous`, `.bh-change`: `font-variant-numeric: lining-nums tabular-nums`.
- `.mw-cell--price` and `.mw-cell--pct` in `.mw-board .mw-row`: `animation: none`, so numbers rest between updates. Keep `.bh-row-breathe` and hover.
- `.board-section-evidence`: `font-size: var(--text-2xs)`.
- Stale and offline panels: price and percent use `--text-muted`, `.mw-cell` animation none, `.bh-row-breathe` and `.bh-rank-delta` hidden.
- Other tokens: `--space-1`, `--r-full`, `--weight-semibold`, `--border-default`, `--ease-standard`, `--leading-tight`.

## Acceptance checks

### Truthful status
1. Block /data for every backend candidate, including the dev fallbacks to 127.0.0.1:5003. 1M reads Delayed by 42s and Stale after 45s. Every board reads Offline at 60s. The top pill is never LIVE during this.
2. With meta.staleSeconds at 74 and successful fetches, the stamp reads about "Stale 1m 14s old" and the pill reads STALE.
3. On recovery, stamps return to Live within one publish cycle and rows regain color and motion without a reload.
4. Rows are never removed by a stale or offline state.

### Lane separation
1. Rank delta computed color equals --text-muted for up and down on 1M, 3M Gainers and 3M Losers.
2. No .bh-live-rank computed color or background is amber or violet.
3. .bh-symbol-markers contains no rank delta.
4. Delta stays visible for 8s on 1M and 24s on 3M after the last rank change.
5. getMoveStatus and MOVE_STATUS_LABELS have no diff.

### Layout
1. Row height stays 60px at 1440 and 62px at 375.
2. document.documentElement.scrollWidth equals innerWidth at 1440, 1024, 375 and 320.
3. An 8-character symbol with "Tape confirmed" does not overflow .bh-symbol-line at those widths.
4. Row clicks, star, trade and rabbit hover behave as before.

### Performance and access
1. TokenRowUnified does not re-render from the 1-second stamp tick. Cover this with a render-count test.
2. Screen readers get state-word changes only. The ticking age is not in a live region.
3. Reduced motion stops the connecting and warming dot pulse.
4. New text is at least --text-2xs (10.9px). Muted text measures 6.9:1 on the void background.
5. npm run verify passes from frontend/.

### Tests to add
- `deriveFreshness`: each threshold boundary for both cadences, source age added to fetch age, offline based on fetch age only.
- `formatAge`: under a minute, minutes, hours.
- `FreshnessStamp`: copy per state, `onStatusChange` fires only on change.
- `TokenRowUnified`: delta in rank stack, same glyph format for gainer and loser.
- `DashboardShell.test.jsx` mock: add `lastFetchTs` and `threeMinPublishedTs`.

## Evidence and open checks

**Confirmed on a throwaway copy of this slice with sample data:** `npm run verify` (build plus 429 tests), row heights at 1440 and 375, no overflow with an 8-character symbol at both widths, and the delayed, stale and offline transitions.

**Still to verify:** 1024 and 320 widths, first-load skeleton rendering (cached rows prevented it in test runs), screen reader output, and the render-count test.

If the backend sends changed rows while reporting itself stale, those rows would still reorder, which the spec forbids. A table-level freeze is not in this slice.

## Later slices

1. Phone row: 16px gutters, 44px actions, and a bottom bar in place of the floating dock.
2. Reorder motion: remove the double-exposed rows during phone reorders.
3. Carry lanes and `FreshnessStamp` into Watchlists, Portfolio, Scorecard and Alerts.

---

# Design-pass additions (from the canvas)

These came after slice 1 and are not yet in the app. Where they touch the "Do not change" list above, they are deliberate decisions from the design pass. Assets are in `svg/` and styles in `css/` next to this file. The PNG renders are on branch `claude/local-review` (`929fdf1`).

## Phone review: fixes for the next build

From the "Why the rows change" board.

| What you see | Cause | Fix |
|---|---|---|
| Two coins drawn on one row on Ignition (1M), half-faded rows | `GainersTable1Min` renders its two columns as two separate `AnimatePresence` lists with `mode="popLayout"` and a shared `layoutId`. A coin crossing between 4th and 5th leaves one list and enters the other, so both copies render, and the leaving copy is positioned against `.bh-table`, which has no position. | Render the 1M board as one list in one `AnimatePresence` and let CSS grid split it into two columns on desktop and one on phone. Remove `layoutId`. Give `.bh-table` `position: relative`. Drop the rank-based delay on exit. |
| Big gap between 4th and 5th on phone | The two 1M columns stack on phone, keeping the gap between them. | Fixed by the single list above. |
| Percent sits on the price line | The percent cell shares the second line with the price. | On phone the percent cell spans both lines (`grid-row: 1 / span 2; align-self: center`), so it sits midway between the star and the trade button, in the same column. |
| Star and trade side by side | Action cell lays out in a row. | Stack them. Both are violet outlines, gold on hover. A watched star fills gold. |
| Background rabbit always faintly visible | The mural has a fixed opacity. | Swap in the moon-and-rabbit silhouette at opacity 0, raised to 0.2 while a row is hovered. Keep the existing `--emit-*` and `data-row-hover` hover contract. |

## Rows

- **Desktop:** star above trade, each 24px, 2px apart. The previous price sits in normal flow under the current price, and the percent is vertically centered on that price stack.
- **Phone:** a 4-column grid, `30px | 1fr | auto | 40px`, with two rows: symbol and quality on the first, current price over previous price on the second. Rank (column 1) and actions (column 4) span both rows and are centered. The percent (column 3) spans both rows and is centered, so it sits midway between star and trade. Actions are 40×32 each, so the row grows to about 72–80px.
- **Icons** (`svg/icons/row-star.svg`, `row-trade.svg`, both `currentColor`): `--icon-idle` at rest, `--color-gold` on hover and focus. A watched star also gets `fill: currentColor` in gold.
- **Row hover:** background `rgba(192,132,252,.07)` with a 2px violet inset on the left, 0.2s.

## Brand

- **Homepage header:** the BHABIT lettering alone, 60px tall, with the small moon (34px) off its top-right corner (`left: calc(100% + 10px); top: -14px`). Use `svg/bhabit-header-logo.svg` (all vector, flat amber lettering) or `svg/bhabit-header-logo-render.svg` (embeds the cratered lettering and moon renders, matches the canvas exactly).
- **Corner stars:** three per lettering, from `svg/stars/`. The header uses burst at the top-left of the B, tall at the top-right of the T, and needle at the bottom-right of the second B. They rest at 72% scale and 0.4 opacity, and peak at full size every 5.2s, staggered.
- **Breathing glow:** a blurred copy of the lettering behind it, opacity 0.16 to 0.62 over 5.2s. The moon halo does the same in neutral moonlight (`--color-bone`), never violet.
- **Navigation:** the moon mark (`svg/moon-rabbit-mark.svg`) plus the flat wordmark (`svg/bhabit-wordmark.svg`). Craters do not read at 15px, so the nav never uses the cratered lettering.
- **Moon rabbit:** a white rabbit carved into the moon like a crater, with lines in a mix of moon rock and violet, a purple eye, and calmer terrain behind it. A purple-filled rabbit was tried and rejected.

## Background silhouette

`svg/moon-rabbit-silhouette.svg` replaces the old rabbit mural. It sits at opacity 0 and rises to `--mural-hover-opacity` (0.2) with a soft violet drop shadow over 0.6s while any row on that board is hovered. Reduced motion removes the transition.

## Motion and accessibility

Every animation above stops under `prefers-reduced-motion: reduce`. The stars then rest at 90% scale and 0.7 opacity, and the glows hold at a fixed level.
