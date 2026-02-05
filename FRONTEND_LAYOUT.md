Authoritative frontend layout, styling, and behavior spec for the CBMo4ers / BHABIT dashboard. This is the single source of truth for how the board should look and act. One dark canvas, one set of rails, one system of type and color.

---

## 0. Global Design Rules

- Single font everywhere: **Raleway**. No Fragment Mono, no Prosto One, no extra families.
- Core tokens:

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

- Background: near-black canvas with a faint rabbit underlay that stays visible through rows.
- Typography: Raleway for headers, body, and actions. Prices use `--bh-price`; muted lines use `--bh-muted`; gains use `--bh-gain`; losses use `--bh-loss`.

---

## 1. High-Level Layout (desktop)

`.dashboard-shell` is centered at `--bh-board-width` with inset padding. Vertical order inside `.dashboard-shell`:

1) Top **1H PRICE** banner (scrolling).  
2) **1-MIN GAINERS** hero.  
3) Row: **TOP GAINERS (3M)** left, **TOP LOSERS (3M)** right.  
4) **WATCHLIST** as its own full-width section under the 3M row.  
5) Bottom **1H VOLUME** banner (scrolling).  
6) Sentiment/Insights shows only as a popup card when the info icon is clicked.

Watchlist never sits next to 1M; it always lives under the 3M row.

---

## 2. Banners (top & bottom)

- Structure: `.bh-banner-wrap` → `.bh-banner-track` → `.bh-banner-chip`.
- Animation: `.bh-banner-track { animation: continuous-scroll 180s linear infinite; }`.
- Data arrays are duplicated (`[...rows, ...rows]`) for seamless looping.
- Chips are `<a>` links to the Coinbase spot trading page.

**1H PRICE (top)**  
- Header rail: gold/orange, left-aligned.  
- Chip content: symbol, current price (cyan), 1h price % change (gold/purple/muted).

**1H VOLUME (bottom)**  
- Header rail: purple, centered.  
- Chip content: symbol, volume (or compact), 1h volume % change.

---

## 3. TokenRow grid (shared)

All token-like rows use the same grid:

1. Rank (circle/number).  
2. Symbol.  
3. Price stack: current price (cyan) + previous price (muted) below.  
4. Optional extra / padding.  
5. % change (gold for gains, purple for losses).  
6. Actions (star + info icon, no circular pill backgrounds).

Applies to: 1-MIN gainers, 3M gainers, 3M losers, and watchlist rows.

Rails: thin lane always visible; hover beam uses transparent orange for gains, purple for losses. Row hover uses a subtle `translateY(-1px) scale(1.01)` with smooth transitions.

---

## 4. 1-MIN GAINERS hero

- Header: “1-MIN GAINERS” (gain rail).
- Behavior:
  - If there are **4 or fewer rows**: one full-width column.
  - If there are **more than 4 rows**: two columns, interleaved by index (0/2/4… → left, 1/3/5… → right).
  - Rank is global across the visible set (1..N); do not reset per column.
- Alignment: left column aligns with TOP GAINERS (3M) below; right column aligns with TOP LOSERS (3M) below.

---

## 5. 3-MIN gainers & losers

- Side-by-side under the 1M hero:
  - Left: “TOP GAINERS (3M)” (gold header).
  - Right: “TOP LOSERS (3M)” (purple header).
- Both use `TokenRow`; identical grid/rails.
- Show More / Show Less supports 8 ↔ 16 rows.
- Losers: percent must always render negative (`-Math.abs(raw)`); set `rowType="loser"` for purple rails.

---

## 6. Watchlist (full-width section)

- Renders below the 3M row, above the bottom banner.
- Rows use the same `TokenRow` grid and rails.
- For each symbol:
  - Store baseline “price when added”.
  - Show current price (cyan) + % vs baseline (gold if up, purple if down).
- Empty state copy: “Star a token to pin it here.”

---

## 7. Rabbit background & motion

- Single rabbit asset behind the 1M/3M region; scrolls with content.
- Default: very faint, grey-ghost opacity; large enough to span both columns.
- On row hover: brightens slightly (still subtle).
- Ambient: add a gentle 6–8s breathing animation to rails or the rabbit.

---

## 8. Sentiment integration

- Sentiment is used only for the info popup card.
- `SentimentContext` fetches `/api/sentiment-basic` and feeds `SentimentCard`/`InsightsTabbed`.
- Info icon in every token row triggers `onInfo(symbol)` → opens modal.
- Layout/CSS/animation must not depend on sentiment. If the API fails, the dashboard still renders; only the card shows a calm error state.

---

## 9. Validation touchpoints

`scripts/validate_ui_rules.sh` should assert:
- `.bh-banner-track` and `.bh-banner-chip` exist in banners.
- `token-row table-row` class is present.
- Only the Raleway font family is referenced.
- `token-pct-gain`, `token-pct-loss`, and `tr-price-current` exist and are referenced.
