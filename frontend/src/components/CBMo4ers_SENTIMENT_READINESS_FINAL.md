# CBMo4ers / Moonwalkings — Sentiment V2 + Readiness Flattening (Final Patch Summary)

This doc captures the final state after restoring and hardening the Sentiment Card, adding TradingView charts, and removing “warm‑up purgatory” from fast tables. It’s meant to be developer‑ready and reproducible.

---

## What’s now in place

### 1) Flattened readiness rules (panels feel alive again)

**Behavior rule:**  
For tables: **if rows exist, status is `ready`**.  
Warm‑up is only for banners when *truly empty*.

**Tables updated:**
- `frontend/src/components/GainersTable1Min.jsx`
- `frontend/src/components/GainersTable3Min.jsx`
- `frontend/src/components/Losers3m.jsx`
- `frontend/src/components/Watchlist.jsx`

**Status precedence used everywhere in tables:**
```js
const status =
  error ? "error" :
  loading ? "loading" :
  rows.length > 0 ? "ready" :
  "empty";
```

**Banners updated:**
- `frontend/src/components/TopBannerScroll.jsx`
- `frontend/src/components/VolumeBannerScroll.jsx`

**Banner status logic (show truth immediately):**
```js
const items = bannerItems ?? [];

const status =
  error ? "error" :
  loading ? "loading" :
  items.length > 0 ? "ready" :
  (historyMinutes < 60 ? "loading" : "empty");
```

---

### 2) `/data` shape is explicit (no legacy leakage)

`useData` now returns only named lanes. Components no longer read `payload.data`.

**File:**
- `frontend/src/hooks/useData.js`

**Returned shape:**
```js
return {
  gainers1m: payload.gainers_1m ?? [],
  gainers3m: payload.gainers_3m ?? [],
  losers3m: payload.losers_3m ?? [],
  banner1hPrice: payload.banner_1h_price ?? [],
  banner1hVolume: payload.banner_1h_volume ?? [],
  latestBySymbol: payload.latest_by_symbol ?? {},
  meta: payload.meta ?? {},
  loading,
  error,
};
```

Consumers updated:
- `frontend/src/components/DashboardShell.jsx`
- `frontend/src/App.jsx` (or AppRoot / Dashboard entry)

Result: no more “phantom empty panels” because a component accidentally read the wrong lane.

---

### 3) Sentiment Card V2 is stable, styled, and real‑data tolerant

#### Normalization adapter (snake/camel aware)
**File:**
- `frontend/src/adapters/normalizeSentiment.js`

**Fix:** API returns snake_case (`overall_sentiment`, `sentiment_history`, etc.).  
Adapter now accepts either snake_case or camelCase, clamps safely, and never throws.

Adapter outputs:
- `overallSentiment` (0–1)
- `fearGreedIndex` (0–100 or null)
- `socialMetrics { volumeChange, engagementRate, mentions24h }`
- `socialBreakdown { reddit, twitter, telegram, chan }`
- `sourceBreakdown { tier1, tier2, tier3, fringe }`
- `sentimentHistory[]`
- `socialHistory[]`
- `trendingTopics[]`
- `divergenceAlerts[]`

#### Hardened hook with last‑good caching
**File:**
- `frontend/src/hooks/useSentimentLatest.js`

Behavior:
- Accepts `symbol`
- Fetches from `VITE_SENTIMENT_API_BASE`
- Preserves last‑good normalized snapshot
- Exposes `{ data, raw, loading, validating, error, refresh }`

#### TradingView charts are always on
**File:**
- `frontend/src/components/charts/TradingViewChart.jsx`

`Charts` tab renders TradingView immediately, and only gates *history charts*.
`Charts` tab renders TradingView immediately, and only gates *history charts*.

#### Sentiment modal skin + rabbit haze
**Files:**
- `frontend/src/styles/sentiment-v2.css` (or your exact CSS path)
- background asset: `frontend/public/purple-rabbit-bg.png`

Modal shell uses:
```css
.sentiment-modal-shell::before {
  background-image: url("/purple-rabbit-bg.png");
  opacity: 0.12;
  mix-blend-mode: screen;
}
```

#### InsightsTabbed now uses only normalized data
**File:**
- `frontend/src/components/InsightsTabbed.jsx`

- One fetch per modal open via `useSentimentLatest(symbol)`
- All tabs derive series from `data` (normalized)
- Social/Charts/Sources crashproof + empty‑state guarded

---

### 4) Cheap safety tests added

**Files:**
- `frontend/src/adapters/tests/normalizeSentiment.test.js`
- `frontend/src/utils/tests/stats.test.js`

Covers:
- snake_case and camelCase normalize identically
- Pearson correlation returns sane outputs on known inputs

---

## Runbook (what to do right now)

### A) Restart frontend clean on 5176
Your port error is always a zombie Vite.

```bash
# repo root
lsof -t -iTCP:5176 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true

cd frontend
pnpm dev
```

(Or `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5176` if you’re in npm mode.)

### B) Smoke test
1. Open dashboard
2. You should see:
   - tables fill **as soon as any rows exist**
   - banners show any computed items immediately
3. Open Insights modal:
   - Overview shows real numbers (no zeros unless API empty)
   - Social tab renders without crashing
   - Charts tab shows TradingView instantly
   - Sources tab renders breakdown or calm empty state

### C) If still sparse after warm‑up flattening
It’s backend filter pressure.

Add temporary logs around mover selection:

```py
logger.info("1m candidates=%s selected=%s", len(candidates), len(gainers_1m))
logger.info("3m candidates=%s selected=%s", len(candidates), len(gainers_3m))
logger.info("3m losers candidates=%s selected=%s", len(candidates), len(losers_3m))
```

If selected is tiny vs candidates, loosen thresholds (enter pct / min volume).  
For a live board, the top movers should show even if “weak.”

---

## Definition of “done”
- No tab can crash the app.
- No real rows are ever hidden by warm‑up logic.
- TradingView is always visible in Charts.
- `/data` consumers never touch legacy `payload.data`.
- Build passes and tests pass in one command.

---

If you want a final micro‑pass after this, it’s purely feel:
sync breathe pulse durations and hover glow easing across PanelShells so the whole board moves like one creature.
