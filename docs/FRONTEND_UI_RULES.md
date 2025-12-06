# CBMoovers / BHABIT – Frontend UI Rules (Home Board)

This file is the source of truth for the **home board** UI.

If existing code conflicts with this spec, the code is wrong.

The goal:

- One canonical grid, no drift.
- Clean, breathable spacing.
- Hover and motion that feel alive.
- Banners, tables, watchlist, and bunny all locked into a single system.

---

## 1. Files Covered

These rules apply to:

- `frontend/src/index.css`
- `frontend/src/components/DashboardShell.jsx`
- `frontend/src/components/TokenRow.jsx`
- `frontend/src/components/AnimatedTokenRow.jsx`
- `frontend/src/components/GainersTable1Min.jsx`
- `frontend/src/components/GainersTable3Min.jsx`
- `frontend/src/components/Losers3m.jsx`
- `frontend/src/components/WatchlistPanel.jsx`
- `frontend/src/components/BannerTicker.jsx` (or `TopBannerScroll.jsx` / `VolumeBannerScroll.jsx`)
- `frontend/src/components/ui/PanelShell.jsx`, `StatusGate.jsx` (wrappers only; no layout hacks)

Any other layout system or one-off CSS for the home board is a bug.

---

## 2. Board Grid – One System, Two Layout Modes

The home board uses a single canonical grid with only two row layouts:

- `full-width` – one column across the board.
- `two-column` – left and right panels, equal width.

All sections must sit inside one of these wrappers.

```css
/* Board width + outer grid */
.bh-board {
  max-width: 1200px;
  margin: 0 auto;
  padding-inline: 16px;
}

/* One full-width strip */
.bh-board-row-full {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  column-gap: 0;
  margin-bottom: 24px;
}

/* Two equal panels side by side */
.bh-board-row-halves {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  column-gap: 24px;
  margin-bottom: 24px;
}

.bh-board-panel {
  display: flex;
  flex-direction: column;
}

/* When only left panel has a visible header, right gets a ghost to keep rhythm */
.bh-section-header--ghost {
  visibility: hidden;
  border-bottom-color: transparent;
}
```

Allowed placements:
- Top 1h price banner: `bh-board-row-full > bh-board-panel`
- 1m gainers: either full-width or two-column (see below).
- 3m gainers/losers: `bh-board-row-halves > bh-board-panel` x2
- Watchlist: `bh-board-row-full > bh-board-panel`
- Bottom 1h volume banner: `bh-board-row-full > bh-board-panel`

Containers (panels, tables) must have transparent backgrounds; no visible card borders. Depth comes from glow, rails, and text, not boxes.

---

## 3. Canonical Row Layout – `.bh-row`

Every row for tokens (1m, 3m, watchlist) uses the same grid.

No per-table `grid-template-columns`. If alignment is off, this is where you fix it.

```css
/* Canonical row grid */
.bh-row {
  position: relative;
  display: grid;
  grid-template-columns:
    32px              /* rank */
    minmax(0, 1.6fr)  /* symbol/name */
    minmax(0, 1.2fr)  /* price block */
    minmax(0, 1.1fr)  /* % change */
    40px;             /* actions (star/info) */
  align-items: center;
  padding: 10px 0;          /* vertical breathing room */
}

/* Base cell styling */
.bh-cell {
  min-width: 0;
}

.bh-cell-rank {
  text-align: right;
  padding-right: 8px;
}

.bh-cell-symbol {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bh-symbol {
  font-weight: 600;
}

.bh-name {
  font-size: 0.75rem;
  opacity: 0.7;
}

/* Price block */
.bh-cell-price {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.bh-price-current {
  color: var(--bh-price);      /* steel cyan from style guide */
  font-weight: 600;
  font-size: 0.9rem;
}

.bh-price-previous {
  color: var(--bh-muted);      /* dimmer gray/steel */
  font-size: 0.75rem;
}

/* % change */
.bh-cell-change {
  text-align: right;
}

.bh-change {
  font-weight: 600;
  font-size: 0.9rem;
}

.bh-change-pos {
  color: var(--bh-gain);       /* BHABIT gold/orange */
}

.bh-change-neg {
  color: var(--bh-loss);       /* BHABIT purple/pink */
}

/* Actions column */
.bh-cell-actions {
  display: flex;
  justify-content: center;
}

.bh-row-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.bh-row-action {
  background: transparent;
  border: none;
  padding: 0;
  margin: 0;
  box-shadow: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* Outline-only icons */
.bh-row-action svg {
  stroke: var(--bh-fg);
  fill: transparent;
}
```

### 3.1 Rails and Hover Glow

Each row owns a single rail underneath. No double-height rails, no rails that span pairs of rows.

```css
/* Thin rail under each row */
.bh-row::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.25) 50%,
    rgba(255, 255, 255, 0) 100%
  );
  opacity: 0.5;
  pointer-events: none;
}

/* Shared hover glow overlay, adjusted by gain/loss class */
.bh-row::before {
  content: "";
  position: absolute;
  inset: -2px 0;
  opacity: 0;
  pointer-events: none;
  background: radial-gradient(
    circle at center,
    rgba(255, 165, 0, 0.18) 0%,  /* overridden for loss rows */
    rgba(255, 165, 0, 0) 60%
  );
  transition: opacity 160ms ease-out, transform 160ms ease-out;
  transform: translateY(2px);
}

.bh-row:hover::after {
  opacity: 0.9;
}

.bh-row:hover::before {
  opacity: 1;
  transform: translateY(0);
}

/* Loss rows use purple glow instead of gold */
.bh-row--loss::before,
.bh-row.bh-row--loss::before {
  background: radial-gradient(
    circle at center,
    rgba(151, 71, 255, 0.22) 0%,
    rgba(151, 71, 255, 0) 60%
  );
}
```

Vertical spacing comes from:
- `.bh-row` padding (10px 0).
- Optional row-gap on `.bh-table` (see next section).

If rows look cramped: adjust padding and row-gap here, not per table.

---

## 4. Tables – `.bh-table`

All tabular sections wrap rows in `.bh-table`. It only controls stacking and gaps, not grid columns.

```css
.bh-table {
  display: flex;
  flex-direction: column;
  row-gap: 4px;   /* consistent vertical gap between token rows */
}
```

No table introduces its own grid; it only mounts `TokenRow` (or `AnimatedTokenRow`) inside `.bh-table`.

---

## 5. TokenRow – Single Layout Owner

`TokenRow.jsx` matches the canonical `.bh-row` grid and exposes clean props.

It must use `forwardRef` so framer-motion can wrap it safely.

```jsx
// src/components/TokenRow.jsx
import React, { forwardRef } from "react";

export const TokenRow = forwardRef(function TokenRow(
  {
    rank,
    symbol,
    name,
    currentPrice,
    previousPrice,
    percentChange,   // number or string
    isWatchlisted,
    onToggleWatchlist,
    onInfo
  },
  ref
) {
  const numericChange =
    typeof percentChange === "number"
      ? percentChange
      : parseFloat(String(percentChange).replace(/[%+]/g, ""));

  const isLoss =
    !Number.isNaN(numericChange) && Number.isFinite(numericChange)
      ? numericChange < 0
      : false;

  const rowClassName = [
    "bh-row",
    isLoss ? "bh-row--loss" : null
  ]
    .filter(Boolean)
    .join(" ");

  const formattedChange =
    typeof percentChange === "number"
      ? `${numericChange >= 0 ? "+" : ""}${numericChange.toFixed(2)}%`
      : percentChange;

  return (
    <div ref={ref} className={rowClassName}>
      <div className="bh-cell bh-cell-rank">
        <span className="bh-rank">{rank}</span>
      </div>

      <div className="bh-cell bh-cell-symbol">
        <div className="bh-symbol">{symbol}</div>
        <div className="bh-name">{name}</div>
      </div>

      <div className="bh-cell bh-cell-price">
        <div className="bh-price-current">{currentPrice}</div>
        <div className="bh-price-previous">{previousPrice}</div>
      </div>

      <div className="bh-cell bh-cell-change">
        <span
          className={
            "bh-change " + (isLoss ? "bh-change-neg" : "bh-change-pos")
          }
        >
          {formattedChange}
        </span>
      </div>

      <div className="bh-cell bh-cell-actions">
        <div className="bh-row-actions">
          <button
            type="button"
            className="bh-row-action"
            onClick={onToggleWatchlist}
            aria-label={
              isWatchlisted ? "Remove from watchlist" : "Add to watchlist"
            }
          >
            {/* outline-only star icon */}
          </button>
          <button
            type="button"
            className="bh-row-action"
            onClick={onInfo}
            aria-label="Show token sentiment"
          >
            {/* outline-only info icon */}
          </button>
        </div>
      </div>
    </div>
  );
});
```

Rules:
- The price block must always show both `currentPrice` and `previousPrice`. If previous price is missing, it is a data bug.
- Info and star buttons are outline-only; no pills or filled backgrounds.

---

## 6. Section Headers

All board headers share the same typography and underline behavior.

Headers include:
- 1h Price Change
- 1-min Gainers
- Top Gainers (3m)
- Top Losers (3m)
- Watchlist
- 1h Volume

```css
.bh-section-header {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  font-family: var(--bh-font-heading);
  font-weight: 700;
  font-size: 1rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 12px;
  color: var(--bh-accent);           /* default gold/orange */
}

.bh-section-header::after {
  content: "";
  width: 100%;
  height: 2px;
  background: linear-gradient(
    90deg,
    var(--bh-accent) 0%,
    transparent 100%
  );
}

/* Losers header: purple */
.bh-section-header--losers {
  color: var(--bh-loss);
}

.bh-section-header--losers::after {
  background: linear-gradient(
    90deg,
    var(--bh-loss) 0%,
    transparent 100%
  );
}

/* Ghost version used to keep grid rhythm in right-hand 1m panel */
.bh-section-header.bh-section-header--ghost {
  visibility: hidden;
  margin-bottom: 12px;
}
```

Spacing from header → table is consistent across all sections by using the same margin-bottom and `.bh-table` layout.

---

## 7. 1-min Gainers – Two Layout Modes

There is exactly one component: `GainersTable1Min`.

Layout mode is driven by `items.length`:
- `items.length <= 4` → full-width single column.
- `items.length > 4` → two-column layout via `bh-board-row-halves`.

```jsx
import React from "react";
import { AnimatedTokenRow } from "./AnimatedTokenRow";

export function GainersTable1Min({ data }) {
  const items = data ?? [];

  if (!items.length) {
    return (
      <section className="bh-board-row-full">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">1-min Gainers</h2>
          <p className="bh-empty-copy">No 1-min gainers right now.</p>
        </div>
      </section>
    );
  }

  const isSingleColumn = items.length <= 4;

  if (isSingleColumn) {
    return (
      <section className="bh-board-row-full">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">1-min Gainers</h2>
          <div className="bh-table">
            {items.map((t, i) => (
              <AnimatedTokenRow
                key={t.symbol}
                rank={i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_1m_ago}
                percentChange={t.change_1m}
                isWatchlisted={t.isWatchlisted}
                onToggleWatchlist={t.onToggleWatchlist}
                onInfo={t.onInfo}
              />
            ))}
          </div>
        </div>
      </section>
    );
  }

  const mid = Math.ceil(items.length / 2);
  const left = items.slice(0, mid);
  const right = items.slice(mid);

  return (
    <section className="bh-board-row-halves">
      <div className="bh-board-panel">
        <h2 className="bh-section-header">1-min Gainers</h2>
        <div className="bh-table">
          {left.map((t, i) => (
            <AnimatedTokenRow
              key={t.symbol}
              rank={i + 1}
              symbol={t.symbol}
              name={t.name}
              currentPrice={t.current_price}
              previousPrice={t.price_1m_ago}
              percentChange={t.change_1m}
              isWatchlisted={t.isWatchlisted}
              onToggleWatchlist={t.onToggleWatchlist}
              onInfo={t.onInfo}
            />
          ))}
        </div>
      </div>

      <div className="bh-board-panel">
        <h2 className="bh-section-header bh-section-header--ghost">
          1-min Gainers
        </h2>
        <div className="bh-table">
          {right.map((t, i) => (
            <AnimatedTokenRow
              key={t.symbol}
              rank={mid + i + 1}
              symbol={t.symbol}
              name={t.name}
              currentPrice={t.current_price}
              previousPrice={t.price_1m_ago}
              percentChange={t.change_1m}
              isWatchlisted={t.isWatchlisted}
              onToggleWatchlist={t.onToggleWatchlist}
              onInfo={t.onInfo}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
```

All rows must show a previous price (`price_1m_ago`). If it’s missing, fix the data.

---

## 8. 3-min Gainers / Losers

3m tables always share a `bh-board-row-halves` wrapper.

```jsx
<section className="bh-board-row-halves">
  <div className="bh-board-panel">
    <h2 className="bh-section-header">Top Gainers (3m)</h2>
    <div className="bh-table">
      {gainers3m.map((t, i) => (
        <AnimatedTokenRow
          key={t.symbol}
          rank={i + 1}
          symbol={t.symbol}
          name={t.name}
          currentPrice={t.current_price}
          previousPrice={t.price_3m_ago}
          percentChange={t.change_3m}
          isWatchlisted={t.isWatchlisted}
          onToggleWatchlist={t.onToggleWatchlist}
          onInfo={t.onInfo}
        />
      ))}
    </div>
  </div>

  <div className="bh-board-panel">
    <h2 className="bh-section-header bh-section-header--losers">
      Top Losers (3m)
    </h2>
    <div className="bh-table">
      {losers3m.map((t, i) => (
        <AnimatedTokenRow
          key={t.symbol}
          rank={i + 1}
          symbol={t.symbol}
          name={t.name}
          currentPrice={t.current_price}
          previousPrice={t.price_3m_ago}
          percentChange={t.change_3m}
          isWatchlisted={t.isWatchlisted}
          onToggleWatchlist={t.onToggleWatchlist}
          onInfo={t.onInfo}
        />
      ))}
    </div>
  </div>
</section>
```

Both sides:
- Use the same `.bh-row` grid.
- Have identical row spacing via `.bh-table`.
- Differ only in header color and sign of change.

---

## 9. Watchlist

Watchlist is always full-width under the 3m tables.

```jsx
<section className="bh-board-row-full">
  <div className="bh-board-panel">
    <h2 className="bh-section-header">Watchlist</h2>
    {items.length === 0 ? (
      <p className="bh-watchlist-empty">
        Star a token in the tables above to pin it here.
      </p>
    ) : (
      <div className="bh-table">
        {items.map((t, i) => (
          <AnimatedTokenRow
            key={t.symbol}
            rank={i + 1}
            symbol={t.symbol}
            name={t.name}
            currentPrice={t.current_price}
            previousPrice={t.base_price}
            percentChange={t.change_since_added}
            isWatchlisted={true}
            onToggleWatchlist={() => toggleWatchlist(t)}
            onInfo={() => openSentiment(t)}
          />
        ))}
      </div>
    )}
  </div>
</section>
```

Rails and glow are scoped to the watchlist width, not the whole page.

---

## 10. Banners – Top (1h Price) and Bottom (1h Volume)

Use a shared `BannerTicker` component for both banners. They live in `bh-board-row-full` sections and align with the board.

They do not use `.bh-row`; they use pill-like chips.

```jsx
<main className="bh-board">
  {/* 1h Price Change */}
  <section className="bh-board-row-full">
    <div className="bh-board-panel">
      <BannerTicker
        title="1h Price Change"
        items={data.banner_1h_price}
        mode="price"
      />
    </div>
  </section>

  {/* 1m + 3m + Watchlist here */}

  {/* 1h Volume */}
  <section className="bh-board-row-full">
    <div className="bh-board-panel">
      <BannerTicker
        title="1h Volume"
        items={data.banner_1h_volume}
        mode="volume"
      />
    </div>
  </section>
</main>
```

### 10.1 Banner UI Rules
- Header uses `.bh-section-header`.
- Each chip shows: rank, symbol, price/volume, change (%).
- Rank and percent change use gain/loss colors.
- Chips auto-scroll horizontally.
- Tokens are clickable links to their Coinbase trade pages.
- No outline borders on pills; use subtle fill and glow instead.

Example CSS:

```css
.bh-banner {
  overflow: hidden;
}

.bh-banner-track {
  display: inline-flex;
  gap: 8px;
  white-space: nowrap;
  animation: bh-banner-scroll 40s linear infinite;
}

.bh-banner-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(5, 3, 8, 0.8); /* subtle fill, no border */
  box-shadow: 0 0 18px rgba(0, 0, 0, 0.6);
  text-decoration: none;
}

.bh-banner-chip-rank {
  font-weight: 600;
}

.bh-banner-chip-symbol {
  font-weight: 600;
}

.bh-banner-chip-price {
  color: var(--bh-price);
  font-size: 0.8rem;
}

.bh-banner-chip-change-pos {
  color: var(--bh-gain);
}

.bh-banner-chip-change-neg {
  color: var(--bh-loss);
}
```

---

## 11. Bunny Layer

The bunny art is a separate layer anchored to the board, not a random background image.

Rules:
- Centers behind the 1m + 3m block.
- Scrolls with the page (attached to board, not viewport).
- Very low opacity by default (~5%).
- Can pulse slightly when the board is hovered.

Example:

```css
:root {
  --bh-bunny-opacity: 0.05;       /* baseline 5% */
  --bh-bunny-scale: 1.0;
}

/* Wrapper for bunny layer in DashboardShell */
.bh-bunny-layer {
  position: absolute;
  inset: 80px 0 160px 0;          /* roughly span 1m+3m+watchlist */
  display: flex;
  justify-content: center;
  pointer-events: none;
  z-index: 0;
}

.bh-bunny-layer img,
.bh-bunny-layer svg {
  max-width: 480px;
  opacity: var(--bh-bunny-opacity);
  transform: scale(var(--bh-bunny-scale));
  filter: drop-shadow(0 0 24px rgba(0, 0, 0, 0.8));
  transition:
    opacity 220ms ease-out,
    transform 220ms ease-out;
}

/* Board hover subtly wakes the bunny, but does not overpower text */
.bh-board:hover .bh-bunny-layer img,
.bh-board:hover .bh-bunny-layer svg {
  opacity: 0.08;
  transform: scale(1.02);
}
```

Implementation notes:
- `DashboardShell` should render bunny once, behind the core panels, using a dedicated wrapper with `position: relative` on the board.
- Bunny layer must not change table dimensions; it lives under their z-index and ignores pointer events.

---

## 12. Motion and Stagger

Motion must sit on top of the fixed layout; it does not own the layout.

### 12.1 AnimatedTokenRow

```jsx
// src/components/AnimatedTokenRow.jsx
import { motion } from "framer-motion";
import { TokenRow } from "./TokenRow";

export const AnimatedTokenRow = motion(TokenRow);
```

### 12.2 Variants

```jsx
// src/components/motionVariants.js
export const rowVariants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 }
};

export const listVariants = {
  visible: {
    transition: {
      staggerChildren: 0.05
    }
  }
};
```

### 12.3 Usage in Tables

```jsx
import { motion } from "framer-motion";
import { AnimatedTokenRow } from "./AnimatedTokenRow";
import { rowVariants, listVariants } from "./motionVariants";

<div className="bh-table">
  <motion.div
    initial="hidden"
    animate="visible"
    exit="exit"
    variants={listVariants}
  >
    {items.map((t, i) => (
      <AnimatedTokenRow
        key={t.symbol}
        variants={rowVariants}
        rank={i + 1}
        /* rest of TokenRow props */
      />
    ))}
  </motion.div>
</div>
```

### 12.4 Constraints
- No deprecated `motion()` factory usage.
- Only use `motion.div`, `motion.span`, and `motion(TokenRow)`.
- If there are ref warnings, `TokenRow` is not using `forwardRef` correctly.

---

## 13. Non-Negotiables

1. There is one board grid: `.bh-board` + `.bh-board-row-*` + `.bh-board-panel`.
2. There is one row grid: `.bh-row`.
3. All rows (1m, 3m, watchlist) derive from `TokenRow` (or `AnimatedTokenRow`).
4. Banners use `BannerTicker` and live in `bh-board-row-full`.
5. Bunny layer is low opacity, scrolls with the board, affected by hover, never affects layout.
6. Any divergence from these classes or structures is a bug.

---

## `docs/DATA_PIPELINES.md`

See companion file for data and fetch rules. If UI and data disagree, fix the data layer to match the contract before changing the layout.
