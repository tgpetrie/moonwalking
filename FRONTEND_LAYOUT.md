Authori```````tative frontendÍ layout, styling, and behavior spec for the CBMo4ers / BHABIT
dashboard. This is the single s``````````````````````````````12™™€¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸¸ource of truth for how the board should look and act.

The goal: one dark canvas, one set of rails, one system of type and color. No
Frankenstein, no surprises.

---

## 0. Global Design Rules

### 0.1 Brand Tokens

All layout and components lean on these core tokens:

```css
:root {
  --bh-bg: #060308;
  --bh-panel: rgba(0, 0, 0, 0);
  --bh-gain: #ffb347;          /* gold/orange for gains */
  --bh-loss: #c084fc;          /* purple for losses */
  --bh-price: #7ff0ff;         /* cyan for prices */
  --bh-muted: rgba(255, 255, 255, 0.35);
  --bh-board-width: 1160px;

  --transition-smooth: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-quick: all 0.3s ease;
}
```

### 0.2 Background & Canvas

The app is a single black stage with the rabbit in the back:

```css
body,
html {
  margin: 0;
  min-height: 100vh;
  background: #050308 url("/purple-rabbit-bg.png") center 120px no-repeat;
  background-size: 780px auto;
  color: #fff;
  font-family: "Raleway", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
```

No opaque card backgrounds for tables. Depth comes from rails, glows, and type,
not from big solid boxes.

### 0.3 Typography

Single font: Raleway. No monospace, no secondary fonts.

Guideline sizes:

- Section headers (e.g. “1-MIN GAINERS”, “Top Gainers (3m)”):
  - 0.9–1.0rem
  - font-weight: 700
  - letter-spacing: 0.12em
  - uppercase, centered above the panel.
- Row content:
  - Rank: 0.7rem, weight 500.
  - Symbol: 0.85rem, weight 600.
  - Current price: 0.8rem, weight 500, cyan.
  - Previous price: 0.7rem, weight 400, muted.
  - Percent: 0.8rem, weight 600, gain/loss color.

Color usage:

- Positive % → `var(--bh-gain)` (gold/orange).
- Negative % → `var(--bh-loss)` (purple).
- Prices → `var(--bh-price)` (cyan).
- Secondary text (previous price, labels) → `var(--bh-muted)`.

---

## 1. High-Level Layout

The page is a single “board” with a fixed max width and a small set of
grid rows.

### 1.1 Board Shell

```css
.dashboard-shell {
  max-width: var(--bh-board-width);
  margin: 0 auto;
  padding: 1.5rem 1.5rem 2.5rem;
}
```

Within `.dashboard-shell`, the vertical order is:

1. Top 1-hour price banner (ticker).
2. Row 1: 1-minute gainers (left) + Watchlist (right, when present).
3. Row 2: 3-minute gainers (left) + 3-minute losers (right).
4. Bottom 1-hour volume banner (ticker).
5. Floating Insights card anchored to the board’s right rail.

### 1.2 Panel Rows & Slots

All main sections sit in 2-column grid rows:

```css
.panel-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 32px;
  align-items: flex-start;
}

/* Row 1 – 1-minute gainers + watchlist */
.panel-row-1m {
  margin-top: 1.5rem;
}

/* Row 1 full-width mode (no watchlist) */
.panel-row-1m.panel-row-1m--full {
  grid-template-columns: minmax(0, 1fr);
}

/* Row 2 – 3-minute gainers/losers */
.panel-row-3m {
  margin-top: 1.75rem;
}

/* Slots inside the rows */
.panel-1m-slot,
.panel-watchlist-slot,
.panel-3m-slot {
  width: 100%;
}
```

React structure in `DashboardShell` (conceptually):

```jsx
<div className="dashboard-shell">
  <TopBannerScroll data={data.banner1h} />

  <section
    className={`panel-row panel-row-1m ${
      hasWatchlist ? "" : "panel-row-1m--full"
    }`}
  >
    <div className="panel-1m-slot">
      <GainersTable1Min
        rows={data.gainers_1m}
        watchlist={watchlist}
        ...
      />
    </div>

    {hasWatchlist && (
      <div className="panel-watchlist-slot">
        <WatchlistPanel watchlist={watchlist} ... />
      </div>
    )}
  </section>

  <section className="panel-row panel-row-3m">
    <div className="panel-3m-slot panel-3m-slot-gain">
      <GainersTable3Min rows={data.gainers_3m} ... />
    </div>
    <div className="panel-3m-slot panel-3m-slot-loss">
      <Losers3m rows={data.losers_3m} ... />
    </div>
  </section>

  <VolumeBannerScroll data={data.volume1h} />

  <div className="bh-insight-float">
    <InsightsPanel ... />
  </div>
</div>
```

---

## 2. Banners (Top & Bottom)

Both banners share a pill-based ticker style.

### 2.1 Container & Track

```css
.bh-banner-wrap {
  max-width: var(--bh-board-width, 1160px);
  margin: 0 auto;
  padding: 0 16px;
  overflow: hidden;
}

.bh-banner-track {
  display: flex;
  gap: 12px;
  white-space: nowrap;
  animation: continuous-scroll 180s linear infinite;
}

@keyframes continuous-scroll {
  0% {
    transform: translateX(0%);
  }
  100% {
    transform: translateX(-100%);
  }
}
```

### 2.2 Chip / Pill

```css
.bh-banner-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(5, 5, 9, 0.45);
  text-decoration: none;
  cursor: pointer;
  transition: var(--transition-quick);
}

.bh-banner-chip__symbol {
  font-size: 0.7rem;
  font-weight: 600;
}

.bh-banner-chip__price {
  font-size: 0.7rem;
  color: var(--bh-price);
}

.bh-banner-chip__pct {
  font-size: 0.7rem;
  font-weight: 600;
}

.bh-banner-chip__pct--gain {
  color: var(--bh-gain);
}
.bh-banner-chip__pct--loss {
  color: var(--bh-loss);
}
.bh-banner-chip__pct--flat {
  color: var(--bh-muted);
}

.bh-banner-chip:hover {
  background: linear-gradient(45deg, #7b3ef3, #ff00a8);
  border-color: rgba(255, 255, 255, 0.22);
}

.bh-banner-chip:hover span {
  text-shadow: 0 0 14px rgba(255, 255, 255, 0.6);
}
```

### 2.3 Behavior

- `TopBannerScroll`:
  - Input: `banner1h` (1h price-change).
  - Each chip: symbol, price, % change.
  - % colored by sign via `pctClass`.
  - Chip is an `<a>` to the asset’s Coinbase page.
- `VolumeBannerScroll`:
  - Input: volume-change list (volume now vs 1h ago).
  - Same chip style, % based on volume change.
- Empty state:
  - Always render the wrapper + track.
  - If no data, show a single chip: e.g. “No 1h data yet.”

---

## 3. Token Rows & Rails

All 1m/3m rows share a single grid and rail system.

### 3.1 Row Structure

Canonical React shape (inside `TokenRow`):

```jsx
<tr
  className={[
    "table-row",
    "token-row",
    rowType === "gainer"
      ? "is-gain"
      : rowType === "loser"
      ? "is-loss"
      : "is-flat",
  ].join(" ")}
>
  <td className="tr-col tr-col-rank">{rank}</td>

  <td className="tr-col tr-col-symbol">
    <span className="tr-symbol-text">{symbol}</span>
    <span className="sentiment-dot" />
  </td>

  <td className="tr-col tr-col-price">
    <div className="tr-price-current">{formatPrice(currentPrice)}</div>
    <div className="tr-price-prev">
      {previousPrice != null ? formatPrice(previousPrice) : "--"}
    </div>
  </td>

  <td className="tr-col tr-col-prev">
    {/* Optional extra context if needed; can be omitted if price column stacks both */}
  </td>

  <td className="tr-col tr-col-pct">
    <span
      className={[
        "tr-pct-value",
        changePct > 0
          ? "token-pct-gain"
          : changePct < 0
          ? "token-pct-loss"
          : "",
      ].join(" ")}
    >
      {formatPct(changePct)}
    </span>
  </td>

  <td className="tr-col tr-col-actions">
    <RowActions
      symbol={symbol}
      onInfo={onInfo}
      watchlisted={watchlisted}
      onToggleWatch={toggleWatch}
    />
  </td>
</tr>
```

### 3.2 Grid Layout

```css
.token-row.table-row {
  display: grid;
  grid-template-columns:
    auto              /* rank */
    minmax(0, 1.6fr)  /* symbol */
    minmax(0, 1.3fr)  /* current price */
    minmax(0, 1.2fr)  /* previous price or extra detail */
    auto              /* pct */
    auto;             /* actions */
  align-items: center;
  column-gap: 18px;
  padding: 10px 18px;
  background-color: transparent;
}

/* Shared column types */

.tr-col {
  display: flex;
  align-items: center;
}

.tr-col-rank {
  justify-content: flex-end;
  font-size: 0.7rem;
  font-weight: 500;
  opacity: 0.95;
}

.tr-col-symbol {
  gap: 8px;
  font-size: 0.85rem;
  font-weight: 600;
}

.sentiment-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #888;
}

/* Prices */

.tr-col-price {
  justify-content: flex-end;
  flex-direction: column;
  align-items: flex-end;
}

.tr-price-current {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--bh-price);
}

.tr-price-prev {
  font-size: 0.7rem;
  font-weight: 400;
  color: var(--bh-muted);
}

/* Percent */

.tr-col-pct {
  justify-content: flex-end;
}

.tr-pct-value {
  font-size: 0.8rem;
  font-weight: 600;
}

.tr-pct-value.token-pct-gain {
  color: var(--bh-gain);
}

.tr-pct-value.token-pct-loss {
  color: var(--bh-loss);
}

/* Actions */

.tr-col-actions {
  justify-content: flex-end;
  gap: 6px;
}
```

### 3.3 Constant Rail + Hover Inner Glow

The board always shows a thin rail under each row, with a stretched glow on hover.
Rows remain transparent so the rabbit art is visible.

```css
tr.table-row,
.token-row.table-row {
  position: relative;
  background-color: transparent;
}

/* Constant thin rail */
tr.table-row::before,
.token-row.table-row::before {
  content: "";
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: -3px;
  width: 58%;    /* length of the lane */
  height: 2px;   /* thin line */
  opacity: 0.18; /* faint but always there */
  pointer-events: none;
  filter: blur(4px);
  mask-image: linear-gradient(
    90deg,
    transparent 0%,
    black 48%,
    black 64%,
    transparent 100%
  );
}

/* Hover beam – inner glow */
tr.table-row::after,
.token-row.table-row::after {
  content: "";
  position: absolute;
  left: 50%;
  transform: translateX(-50%) translateY(0) scaleX(1);
  bottom: -5px;
  width: 64%;
  height: 6px;
  opacity: 0;
  pointer-events: none;
  border-radius: 999px;
  filter: blur(10px);
  mask-image: linear-gradient(
    90deg,
    transparent 0%,
    black 48%,
    black 64%,
    transparent 100%
  );
  transition:
    opacity 140ms ease-out,
    transform 160ms ease-out;
}

tr.table-row:hover::after,
.token-row.table-row:hover::after {
  opacity: 1;
  transform: translateX(-50%) translateY(-1px) scaleX(1.08);
}

/* Brand tints */

/* Gainers – transparent orange inner glow */
tr.table-row.is-gain::before,
tr.table-row.is-gain::after,
.token-row.table-row.is-gain::before,
.token-row.table-row.is-gain::after {
  background: linear-gradient(
    90deg,
    rgba(216, 137, 0, 0) 0%,
    rgba(216, 137, 0, 0.55) 50%,
    rgba(216, 137, 0, 0) 100%
  );
}

/* Losers – transparent purple inner glow */
tr.table-row.is-loss::before,
tr.table-row.is-loss::after,
.token-row.table-row.is-loss::before,
.token-row.table-row.is-loss::after {
  background: linear-gradient(
    90deg,
    rgba(123, 62, 243, 0) 0%,
    rgba(123, 62, 243, 0.55) 50%,
    rgba(123, 62, 243, 0, 0) 100%
  );
}

/* Flat – neutral grey */
tr.table-row.is-flat::before,
tr.table-row.is-flat::after,
.token-row.table-row.is-flat::before,
.token-row.table-row.is-flat::after {
  background: linear-gradient(
    90deg,
    rgba(68, 68, 68, 0) 0%,
    rgba(68, 68, 68, 0.35) 50%,
    rgba(68, 68, 68, 0, 0) 100%
  );
  opacity: 0.12;
}
```

---

## 4. 1-Minute Gainers Panel

Component: `GainersTable1Min`.

### 4.1 Behavior

- Data comes sorted by 1-minute % change (descending) from the backend.
- Maximum 16 rows considered.
- Paging:

```ts
const total = rows.length;
const visibleCount = isExpanded
  ? Math.min(total, 16)
  : Math.min(total, 8);

const visibleRows = rows.slice(0, visibleCount);
```

- Full-width (hero) mode: `visibleRows.length <= 4`
  - `panel-row-1m` has the `panel-row-1m--full` class.
  - The 1m table uses the full board width.
  - Rows are a single vertical column.
- Two-column interleaved mode: `visibleRows.length > 4`
  - Row 1 is a standard `panel-row-1m` (two columns).
  - 1m panel sits in `.panel-1m-slot` on the left.
  - Rows are split:

```ts
const leftRows = visibleRows.filter((_, idx) => idx % 2 === 0);
const rightRows = visibleRows.filter((_, idx) => idx % 2 === 1);
const displayRank = (globalIndex: number) => globalIndex + 1; // 1..8 or 1..16
```

### 4.2 Mapping

For each 1m row into `TokenRow`:

- `rank` → 1-based index from the full visible ordering.
- `symbol` → `row.symbol`.
- `currentPrice` → latest 1m snapshot (e.g. `row.current_price_1m`).
- `previousPrice` → `row.price_1m_ago`.
- `changePct` → `row.price_change_pct_1m`.
- `rowType` → `"gainer"`.
- Show More / Show Less button:
  - Visible only when `total > 8`.
  - Toggles `isExpanded` to switch 8 ↔ 16 rows.

---

## 5. 3-Minute Gainers & Losers

Components: `GainersTable3Min`, `Losers3m`.

### 5.1 Shared Layout

Placed side-by-side under the 1m row:

```jsx
<section className="panel-row panel-row-3m">
  <div className="panel-3m-slot panel-3m-slot-gain">
    <GainersTable3Min rows={data.gainers_3m} ... />
  </div>
  <div className="panel-3m-slot panel-3m-slot-loss">
    <Losers3m rows={data.losers_3m} ... />
  </div>
</section>
```

Both:

- Show 8 rows by default.
- Show More / Show Less toggles 8 ↔ 16 rows.
- Use the same `TokenRow` component → identical rails and column alignment.

### 5.2 3-Minute Gainers Mapping

- `symbol` → `row.symbol`.
- `currentPrice` → `row.current_price`.
- `previousPrice` → `row.initial_price_3min`.
- `changePct` → `row.price_change_percentage_3min` (or equivalent).
- `rowType` → `"gainer"`.

### 5.3 3-Minute Losers Mapping

Losers should always read as negative visually and numerically, even if
upstream data is sloppy.

- `symbol` → `row.symbol`.
- `currentPrice` → `row.current_price`.
- `previousPrice` → `row.initial_price_3min`.
- `changePct`:

```ts
const raw = row.price_change_percentage_3min ?? row.gain ?? 0;
const forced = -Math.abs(raw);
```

- `rowType` → `"loser"`.

---

## 6. Watchlist

Component: `WatchlistPanel`.

Placement logic:

```ts
const hasWatchlist =
  (watchlist?.length ?? 0) > 0 && !watchlistMinimized;
```

```jsx
<section
  className={`panel-row panel-row-1m ${
    hasWatchlist ? "" : "panel-row-1m--full"
  }`}
>
  <div className="panel-1m-slot">
    <GainersTable1Min
      rows={data.gainers_1m}
      watchlist={watchlist}
      ...
    />
  </div>

  {hasWatchlist && (
    <div className="panel-watchlist-slot">
      <WatchlistPanel
        watchlist={watchlist}
        ...
      />
    </div>
  )}
</section>
```

Behavior:

- When there is no watchlist (empty or minimized), the 1m panel spans full width.
- When watchlist has entries, the right column is occupied by the watchlist,
  and its width aligns with the 3m losers column below.
- Watchlist rows may use the same `TokenRow` grid or a pared-down variant,
  but must respect the same rails so columns line up.

---

## 7. Insights Panel

Component: `InsightsPanel` inside a floating wrapper.

Anchored to the board’s right edge, not the viewport’s random edge:

```css
.bh-insight-float {
  position: fixed;
  right: calc((100vw - var(--bh-board-width, 1160px)) / 2 + 16px);
  bottom: 24px;
  z-index: 40;
}
```

`InsightsPanel` uses a tabbed card with a glassy, subtle background; it should
not interfere with the core board rails.

---

## 8. Data Flow (Frontend Perspective)

The frontend expects a unified data bundle from the backend, e.g.:

```ts
type UnifiedData = {
  banner1h: BannerRow[];     // 1h price movers
  volume1h: VolumeRow[];     // 1h volume movers
  gainers_1m: TokenRow1m[];
  gainers_3m: TokenRow3m[];
  losers_3m: TokenRow3m[];
  watchlist: WatchlistItem[];
};
```

`DashboardShell` or a similar container:

- Fetches this bundle.
- Feeds slices to:
  - `TopBannerScroll` ← `banner1h`
  - `GainersTable1Min` ← `gainers_1m`
  - `GainersTable3Min` ← `gainers_3m`
  - `Losers3m` ← `losers_3m`
  - `VolumeBannerScroll` ← `volume1h`
  - `WatchlistPanel` ← `watchlist`

Sorting is entirely a backend concern. The frontend only:

- Paginates (8 ↔ 16).
- Chooses layout mode:
  - Full-width vs interleaved (1m).
  - Full-width vs 2-column (row 1 with/without watchlist).
- Maps fields to visually consistent columns and brand colors.

---

## 9. Interaction Notes

- Hover on any token row:
  - Should not change background color.
  - Should fire the inner glow beam beneath the row:
    - Transparent orange for gainers.
    - Transparent purple for losers.
- Rabbit artwork must remain visible through everything.
- Buttons like “Show More”, refresh toggles, etc.:
  - Use small opacity/scale transitions.
  - Do not disrupt the overall calm, legible board.

---

This document plus the matching CSS in `index.css` is the complete spec for
the CBMo4ers / BHABIT frontend layout. Any change to the visual system,
layout, or token mapping should be reflected here first, then implemented
in code to keep designers, devs, and future work all on the same rails.

