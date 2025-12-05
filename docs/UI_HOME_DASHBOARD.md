# BHABIT Dashboard – Canonical UI & Data Guide

Source of truth for the CBMo4ers / BHABIT home dashboard. Follow this when changing UI or data wiring. If older docs or comments disagree, this document wins.

---

## 0. Layout Snapshot (desktop)

Vertical order inside `.dashboard-shell`:
1) **1H PRICE** banner (scrolling, gold rail, left-aligned).  
2) **1-MIN GAINERS** hero (full width when ≤4 rows, two interleaved columns when >4).  
3) Row: **TOP GAINERS (3M)** on the left, **TOP LOSERS (3M)** on the right.  
4) **WATCHLIST** as a full-width section beneath the 3M row.  
5) **1H VOLUME** banner (scrolling, purple rail, centered).  
6) Sentiment/Insights appears only as a popup when an info icon is clicked.

Watchlist never sits beside the 1M hero; it always lives under the 3M row. No floating Insights panel altering layout.

---

## 1. Visual System

- **Font:** Raleway everywhere. No secondary families.  
- **Tokens:** `--bh-bg` near-black canvas, `--bh-gain` gold/orange, `--bh-loss` purple, `--bh-price` cyan, `--bh-muted` soft white/grey.  
- **Rabbit:** Single faint background asset behind the 1M/3M region; scrolls with content and brightens slightly on row hover.  
- **Rails:** Rows are transparent. A thin rail is always visible; hover beam uses orange for gains, purple for losses. Hover motion: `translateY(-1px) scale(1.01)` with smooth transitions. Add a slow (6–8s) breathing animation to rails/rabbit for ambient movement.

---

## 2. Token Row Grid (shared)

All token-like rows use the same grid and should line up across sections:
1. Rank (circle/number).  
2. Symbol.  
3. Price stack: current price (cyan) + previous price (muted) below.  
4. Optional extra/padding column (keeps alignment).  
5. Percent change (gold for gains, purple for losses).  
6. Actions: star + info icon, no pill backgrounds.

Classes to keep present and validated: `token-row table-row`, `token-pct-gain`, `token-pct-loss`, `tr-price-current`.

---

## 3. Sections & Behavior

### 3.1 1-MIN GAINERS
- Header: “1-MIN GAINERS” (gain rail).
- Layout rules:
  - ≤4 rows → single full-width column.
  - >4 rows → two columns, interleaved by index (0/2/4… left, 1/3/5… right).
  - Rank is global across visible rows; do not reset per column.
- Columns align with the 3M columns directly below.

### 3.2 TOP GAINERS (3M) / TOP LOSERS (3M)
- Side-by-side under the 1M panel.
- Headers: gainers use gold; losers use purple.
- Show More / Show Less toggles 8 ↔ 16 rows.
- Losers force percent negative: `-Math.abs(raw)`; pass `rowType="loser"` for purple rails.

### 3.3 WATCHLIST
- Full-width section under the 3M row, above the volume banner.
- Uses the same `TokenRow` grid/rails.
- Baseline is captured when added; show current price + % vs baseline (gold if up, purple if down).
- Empty copy: “Star a token to pin it here.”

---

## 4. Banners

- Structure: `.bh-banner-wrap` → `.bh-banner-track` → `.bh-banner-chip`.
- Animation: `continuous-scroll 180s linear infinite`; duplicate arrays for seamless looping.
- Chips are `<a>` links to Coinbase spot trading pages.

**1H PRICE (top)**  
- Gold/orange header rail, left aligned.  
- Chip: symbol, current price (cyan), 1h price % change (gold/purple/muted).

**1H VOLUME (bottom)**  
- Purple header rail, centered.  
- Chip: symbol, volume (or compact), 1h volume % change.

---

## 5. Sentiment Integration

- Sentiment is only used inside the info popup card. Layout and animation must not depend on it.  
- `SentimentContext` hits `/api/sentiment-basic` and feeds `SentimentCard` / `InsightsTabbed`.  
- If the API fails, the dashboard still renders; the popup shows a calm error state.

---

## 6. Data & Modeling (frontend expectations)

`useData` or equivalent should surface:
```ts
{
  banner1h: BannerRow[];    // price movers 1h
  volume1h: VolumeRow[];    // volume movers 1h
  gainers_1m: TokenRow[];
  gainers_3m: TokenRow[];
  losers_3m: TokenRow[];
  watchlist?: WatchlistItem[];
}
```

- Sorting is a backend concern. Frontend only paginates (8 ↔ 16) and applies the 1M interleave logic.  
- Symbols displayed use normalized tickers (e.g., `BTC-USD` → `BTC`) but keys stay canonical.  
- Watchlist items: `{ symbol, baseline, current }`, with `baseline` set when added. `deltaPct = (current - baseline) / baseline * 100` when both exist.

---

## 7. Validation & Guardrails

`scripts/validate_ui_rules.sh` should assert:
- `.bh-banner-track` and `.bh-banner-chip` exist and are used by banners.
- `token-row table-row` class is present in components.
- Only Raleway is referenced as the font family.
- `token-pct-gain`, `token-pct-loss`, and `tr-price-current` exist and are referenced.

Keep the watchlist under the 3M row, maintain the shared TokenRow grid, and leave sentiment as a popup-only feature.
