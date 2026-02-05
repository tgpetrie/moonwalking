# BHABIT UI Master Plan v0.1

Living checklist. Each item has a “done when” so it stays objective.

## 0) Non-negotiable guardrails
- Single rail width source of truth (`--bh-rail-max`).
  - Done when: nothing is full-bleed unless explicitly intended.
- Single row grid (`.bh-row-grid` + `--bh-cols`).
  - Done when: price, pct, star, info align across 1m/3m/watchlist.
- Kill legacy port refs (`:8001`).
  - Done when: repo search finds none and console is quiet.

## 1) Layout lock (headers + rhythm)
- Section headers use one CSS block or component.
  - Done when: spacing/font sizing match reference skeletons.
- Vertical rhythm uses fixed tokens (`--bh-gap-lg`, `--bh-gap-md`).
  - Done when: sections sit on consistent rails.

## 2) 1-Min Gainers layout rules
- Rules:
  - <= 4 items: single column, full rail width.
  - >= 5 items: show top 8 as two columns (4 + 4).
  - Show more: reveal 8 more (up to 16 total), still two columns (8 + 8).
- Done when: layout never flips unpredictably.

## 3) 3-Min tables rules
- Each table shows 8 by default; show more +8 up to 16.
- Done when: gainers/losers behave identically.

## 4) Watchlist alignment + sizing
- Watchlist rows use `TokenRowUnified` and the same grid as tables.
- Watchlist panel sits on the same rail as tables.
- Done when: BTC row aligns with any table row pixel-perfect.

## 5) Watchlist search (full Coinbase directory)
- Backend exposes `/api/products/search?q=...` from cached Coinbase products.
- Frontend uses debounced typeahead + clear “not listed” state.
- Done when: NEON (if listed on Coinbase) can be added even when not in movers.

## 6) Banner speed normalization
- One marquee utility with constant px/sec for both banners.
- Done when: token count doesn’t change perceived speed.

## 7) Banner hover “lens” effect
- Hover uses transforms/glow only (no reflow).
- Done when: hover feels like a lens passing over the tape.

## 8) Volume banner sanity
- Baseline clamp: if V0 < MIN_BASELINE, render “—” and exclude from ranking.
- Optional clamp: pct in [-500, 500].
- Done when: no absurd % spikes on thin volume.

## 9) Sentiment modal correctness
- Modal shows clicked symbol in header.
- Hook includes `?symbol=...` and guards against NaN.
- Done when: ADA and BTC render different data.

## 10) Replace AnomalyStream with row badges
- [VOL] from hour-vs-hour candles (with baseline clamp).
- [VEL] from 1m change; optional [DUMP] from 3m losers.
- Done when: AnomalyStream can be removed without losing signal.

## 11) Motion system
- Micro-motion only; no reflow.
- Done when: UI feels alive but never glitchy.

## 12) Refresh cadence consistency
- 1m: ~8s, 3m: ~30s, banners: ~120s.
- Done when: 3m isn’t hammering like 1m and banners don’t jitter.
