# BHABIT Dashboard — Build Guide

This document freezes the current BHABIT dashboard shape so you can restore it quickly.

Contents:
- Project shape
- Data flow (one SWR, many selectors)
- Components overview
- Layout + CSS
- Rabbit “ghost” effect
- Watchlist wiring + price reconcile
- What to verify in the browser

## Project Shape

- Top area: auto-refresh ticker
- Left: 1‑Minute Gainers
- Center row: 3‑Minute Gainers (left) + 3‑Minute Losers (right)
- Floating: Insight/Sentiment panel triggered via ⓘ or pct cell click
- Background: subtle rabbit image

Key files:
- `frontend/src/App.jsx`
- `frontend/src/hooks/useDashboardData.js`
- `frontend/src/components/{Gainers1m,Gainers3m,Losers3m}.jsx`
- `frontend/src/components/{TokenRow,RefreshTicker}.jsx`
- `frontend/src/components/tables/RowActions.jsx`
- `frontend/src/components/cards/SentimentCard.jsx`
- `frontend/src/context/WatchlistContext.jsx`
- `frontend/src/index.css`

## Data Flow (one SWR, many selectors)

Hook: `frontend/src/hooks/useDashboardData.js`
- Fetches unified `/api/data`
- Adapts backend shape into safe arrays: `gainers1m`, `gainers3m`, `losers3m`
- Preserves `initial_price_1min/_3min`; normalizes `symbol`, `price`, `changePct`
- Exposes `priceMap` for watchlist reconciliation

App wiring: `frontend/src/App.jsx`
- Uses `useDashboardData()` and passes `rows` to components
- `RefreshTicker` calls `mutate` to reload everything together
- Emits `onInfo(payload)` from rows to open insights panel

## Components

- `Gainers1m.jsx`: two-column layout, 4 rows per column, `side="gain"`
- `Gainers3m.jsx` / `Losers3m.jsx`: up to 8 rows, `side="loss"` for losers
- `TokenRow.jsx`: five-column row; pct cell is clickable to open insights; actions on the right
- `tables/RowActions.jsx`: watchlist toggle + delta since baseline + inline sentiment popover when no `onInfo` supplied
- `cards/SentimentCard.jsx`: calls `/api/sentiment?symbol=XYZ` or fallbacks; renders overview/scores/social/news/onchain

## Layout + CSS (authoritative)

See `frontend/src/index.css` for:
- Root tokens and colors (gold up, purple down, teal price, muted previous price)
- Section headers (uppercase with gradient underline)
- `one-min-grid` and `three-min-grid` layout wrappers
- Token row visuals and small hover lift; `:focus-within` highlight
- `.tr-col-pct.clickable` pointer affordance
- Responsiveness: collapses to single column under 1180px

## Rabbit “Ghost” Effect

- Subtle background image applied; optional “light-up” can be tied to row hover or refresh events
- To blink on refresh: set a state flag for ~300ms in the refresh handler and toggle a class that increases opacity

## Watchlist Wiring + Price Reconcile

- `WatchlistContext.jsx` stores `{ price (baseline), current, at }` per symbol
- New method: `reconcilePrices(priceMap)` updates `current` from unified data
- `App.jsx` renders a small `WatchlistReconciler` that calls `reconcilePrices(priceMap)` when `/api/data` changes
- `RowActions` shows delta based on baseline vs current price

## Verify in Browser

1. Install deps (`swr` added):
   - `cd frontend && npm i`
2. Run dev server:
   - `npm run dev`
3. Check:
   - Two-column layout with 1m and 3m panels
   - Teal current price, muted previous price; gold gains, purple losses
   - Star persists; ⓘ or pct cell opens sentiment panel
   - Refresh ticker refetches all at once
   - Background rabbit is subtle

If 1‑minute snapshot is slow or missing, panels remain stable since arrays default to `[]` and errors are separated.

