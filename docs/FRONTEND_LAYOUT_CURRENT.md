# FRONTEND LAYOUT — Current Implementation (summary)

This short file records the current implementation state for the frontend layout and maps it to the spec in `docs/FRONTEND_LAYOUT.md`.

Overview
- The live code implements the major UI pieces described in `FRONTEND_LAYOUT.md`:
  - Token rows, banners, panels, watchlist, rabbit background, insights modal, and hover rails.

Key component mapping
- `TokenRow` — `frontend/src/components/TokenRow.jsx`: grid layout, `is-gain`/`is-loss` classes, derived previous price when unavailable, sentiment dot, `RowActions`.
- Hover rail & glow — `frontend/index.css` pseudo-elements on `.token-row.table-row::before` and `::after` implement static rail and hover glow with gradient colors.
- Banners — `TopBannerScroll.jsx` and `VolumeBannerScroll.jsx` implement top/bottom marquees with throttled refresh and looping.
- Panels — `GainersTable1Min.jsx`, `GainersTable3Min.jsx`, `Losers3m.jsx`, `WatchlistPanel.jsx` implement list rendering, empty states, and show-more behavior.
- Insights / Sentiment — `InsightsTabbed.jsx` + `SentimentCard.jsx` compose the modal; `App.jsx` toggles a `rabbitLit` pulse on data refresh and opens the SentimentPanel via `handleInfo`.

Notes & actionables
- Confirm interleaved ranking behavior in `GainersTable1Min.jsx` for 1m hero (5–8 tokens) — the `SharedOneMinGainers.jsx` helper exists but ensure rank ordering is interleaved when splitting columns.
- Verify keyboard focus contrast on `.token-row:focus` and the `row-actions` buttons for accessibility.

For a deeper, component-level audit and next steps, see `docs/UI_AUDIT.md`.
