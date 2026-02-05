# UI Implementation Audit — BHABIT Dashboard

This file documents the current frontend implementation (components, behavior, and known gaps) as of the active branch.

Summary
- The implementation closely follows `docs/UI_HOME_DASHBOARD.md` and `docs/FRONTEND_LAYOUT.md`.
- Key components are implemented in `frontend/src/components/` and styling is in `frontend/index.css` and `frontend/src/index.css`.

Implemented components & behavior

- TokenRow (`frontend/src/components/TokenRow.jsx`)
  - Grid layout with columns for rank, symbol, price, previous price, pct, actions.
  - Strips common suffixes from symbols (`-USD`, `-USDT`, `-PERP`) for display.
  - Derives a previous price when not provided using current price and percent change.
  - Adds `is-gain` / `is-loss` classes based on data or explicit props.
  - Renders a `sentiment-dot` when sentiment is available.
  - Uses `RowActions` (star + info) where star toggles watchlist and info opens insights.

- Row actions (`frontend/src/components/tables/RowActions.jsx`)
  - `star` toggles watchlist via `WatchlistContext`.
  - `info` calls `onInfo` (does not navigate), used to open the insights / sentiment panel.

- Banners
  - `TopBannerScroll.jsx` and `VolumeBannerScroll.jsx` implement the top/bottom marquees.
  - They map incoming rows into banner chips and perform throttling/looping for smooth UX.
  - Chips use `.is-gain` / `.is-loss` classes so colors are driven by CSS variables.

- Panels
  - `GainersTable1Min`, `GainersTable3Min`, `Losers3m`, and `WatchlistPanel` exist with the expected split/expand behavior.
  - 3m/1m panels show placeholders or empty-state copy when no data.

- Insights / Sentiment
  - `InsightsTabbed.jsx` composes `SentimentCard` and chart widgets (TradingView wrappers) in tabs.
  - `SentimentCard.jsx` shows the fear/greed score, funding, and raw sources; it's used inside the larger insights modal.
  - `App.jsx` manages opening the Sentiment/Insights panel via `handleInfo` and lazy-loads the `SentimentPanel`.

- Rabbit background / animation
  - `.bh-rabbit-bg` element is included in `DashboardShell.jsx`. App toggles `rabbitLit` on `/data` refresh to briefly add `is-lit` class.
  - CSS rules place the rabbit behind the board and adjust opacity per `.is-lit`.

- Hover rail & glow
  - Implemented in `frontend/index.css` on `.token-row.table-row::before` (static rail) and `::after` (hover glow).
  - `::before` is always visible (faint), `::after` animates on hover; color gradients come from `is-gain` / `is-loss` classes.

Gaps, notes, and minor mismatches

- Previous price: TokenRow derives previous price when missing, which is good, but it may produce small rounding artifacts if pct is not precise. The UI shows `—` when not available.
- Rank interleaving (1m hero): the spec describes interleaved ranks across columns for 1m; the shared 1m component exists (`GainersTable1Min.jsx` / `SharedOneMinGainers.jsx`) but ensure the parent logic interleaves ranks when rendering two columns.
- Rabbit brightness gating: App toggles `rabbitLit` on refresh; the timing (280ms) is implemented and configurable in code — fine, but tweakable if you want a longer/shorter pulse.
- Accessibility: rows are `role="link"` and keyboard-activable (Enter), actions are buttons with aria labels. Focus styling is present in CSS but verify keyboard focus contrast in practice.

Files of interest (quick map)
- Components: `frontend/src/components/*` — see `TokenRow.jsx`, `GainersTable3Min.jsx`, `GainersTable1Min.jsx`, `Losers3m.jsx`, `WatchlistPanel.jsx`, `TopBannerScroll.jsx`, `VolumeBannerScroll.jsx`, `InsightsTabbed.jsx`, `SentimentCard.jsx`.
- Styles: `frontend/index.css`, `frontend/src/index.css`.
- App shell: `frontend/src/App.jsx`, `frontend/src/components/DashboardShell.jsx`.

Suggested next steps
- Verify interleaved ranking for 1m hero (5–8 tokens) renders as spec requires.
- Add unit/regression tests for format rules: percent formatting and previous-price derivation.
- Confirm watchlist baseline handling on first add (baseline set correctly) and delta computation in `WatchlistPanel`.

TL;DR: The frontend already implements most of the spec: banners, rail + hover glow, token rows with derived previous prices, watchlist, and a fully featured insights/sentiment modal. A few polish items remain (1m interleave validation, precision edge cases, accessibility contrast checks).
