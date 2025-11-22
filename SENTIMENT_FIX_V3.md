# Sentiment Card + Insights Tabs: Stabilization & Visual Restore (V3)

You’re seeing zeros and “warming up” even while `/sentiment/latest` returns real values. That pattern means the adapter is normalizing the payload into an empty-but-valid shape — almost always because the API is snake_case while the UI/adapter expects camelCase. Fix the adapter first, then make Charts always show TradingView, then re‑skin the modal rabbit background, and finally remove the “half‑awake” warm‑up gating for tables.

This doc is written to be applied directly in your `moonwalkings` repo.

---

## 0) Before you touch code: reset the dev server lane

Port 5176 is already occupied by a detached Vite process. Kill it, then restart using your pinned dev script.

```bash
# from repo root
lsof -t -iTCP:5176 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true

cd frontend
pnpm dev
```

You should see Vite listening on `http://127.0.0.1:5176/`.

---

## 1) Replace `normalizeSentiment.js` with a casing‑tolerant adapter

Overwrite this file:

**Path:** `frontend/src/adapters/normalizeSentiment.js`

```js
const pick = (obj, ...keys) => {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
};

const toNum = (v, d = 0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
};

const clamp01 = (v) => Math.max(0, Math.min(1, toNum(v, 0)));

const arr = (v) => (Array.isArray(v) ? v : []);

export function normalizeSentiment(raw = {}) {
  // accept both snake_case and camelCase
  const overallSentiment = clamp01(
    pick(raw, "overall_sentiment", "overallSentiment")
  );

  const fearGreedIndex = toNum(
    pick(raw, "fear_greed_index", "fearGreedIndex"),
    null
  );

  const socialMetricsRaw = pick(raw, "social_metrics", "socialMetrics") || {};
  const socialMetrics = {
    volumeChange: toNum(
      pick(socialMetricsRaw, "volume_change", "volumeChange"),
      0
    ),
    engagementRate: clamp01(
      pick(socialMetricsRaw, "engagement_rate", "engagementRate")
    ),
    mentions24h: toNum(
      pick(socialMetricsRaw, "mentions_24h", "mentions24h"),
      0
    ),
  };

  const socialBreakdownRaw =
    pick(raw, "social_breakdown", "socialBreakdown") || {};
  const socialBreakdown = {
    reddit: clamp01(pick(socialBreakdownRaw, "reddit")),
    twitter: clamp01(pick(socialBreakdownRaw, "twitter")),
    telegram: clamp01(pick(socialBreakdownRaw, "telegram")),
    chan: clamp01(pick(socialBreakdownRaw, "chan")),
  };

  const sourceBreakdownRaw =
    pick(raw, "source_breakdown", "sourceBreakdown") || {};
  const sourceBreakdown = {
    tier1: toNum(pick(sourceBreakdownRaw, "tier1"), 0),
    tier2: toNum(pick(sourceBreakdownRaw, "tier2"), 0),
    tier3: toNum(pick(sourceBreakdownRaw, "tier3"), 0),
    fringe: toNum(pick(sourceBreakdownRaw, "fringe"), 0),
  };

  const sentimentHistoryRaw = arr(
    pick(raw, "sentiment_history", "sentimentHistory")
  );
  const sentimentHistory = sentimentHistoryRaw.map((p) => ({
    timestamp: pick(p, "timestamp"),
    sentiment: clamp01(pick(p, "sentiment")),
    priceNormalized: toNum(
      pick(p, "price_normalized", "priceNormalized"),
      0
    ),
  }));

  const socialHistoryRaw = arr(
    pick(raw, "social_history", "socialHistory")
  );
  const socialHistory = socialHistoryRaw.map((p) => ({
    timestamp: pick(p, "timestamp"),
    reddit: clamp01(pick(p, "reddit")),
    twitter: clamp01(pick(p, "twitter")),
    telegram: clamp01(pick(p, "telegram")),
    chan: clamp01(pick(p, "chan")),
  }));

  const trendingTopicsRaw = arr(
    pick(raw, "trending_topics", "trendingTopics")
  );
  const trendingTopics = trendingTopicsRaw.map((t) => ({
    tag: pick(t, "tag") || "",
    sentiment: pick(t, "sentiment") || "neutral",
    volume: pick(t, "volume") || "",
  }));

  const divergenceAlertsRaw = arr(
    pick(raw, "divergence_alerts", "divergenceAlerts")
  );
  const divergenceAlerts = divergenceAlertsRaw.map((a) => ({
    type: pick(a, "type") || "info",
    message: pick(a, "message") || "",
  }));

  return {
    overallSentiment,
    fearGreedIndex,
    socialMetrics,
    socialBreakdown,
    sourceBreakdown,
    sentimentHistory,
    socialHistory,
    trendingTopics,
    divergenceAlerts,
    raw,
  };
}

export default normalizeSentiment;
```

**Expected result after restart:**  
Overview tab shows real scores immediately. Charts/Social no longer default to empty unless the API truly returns empty arrays.

---

## 2) Fix `InsightsTabbed.jsx` tab keys and make Charts always show TradingView

Open:

**Path:** `frontend/src/components/InsightsTabbed.jsx`

### 2A) Ensure tab keys match render switch

The tab list must use keys that exactly match the conditional render.

```js
const TABS = [
  { key: "overview", label: "Overview" },
  { key: "social", label: "Social Sentiment" },
  { key: "charts", label: "Charts" },
  { key: "sources", label: "Data Sources" },
];
```

And later:

```js
if (activeTab === "overview") return renderOverview();
if (activeTab === "social") return renderSocialTab();
if (activeTab === "charts") return renderChartsTab();
if (activeTab === "sources") return renderSourcesTab();
```

If you see `"chart"` somewhere, rename to `"charts"` everywhere.

### 2B) Do not gate TradingView behind history length

In `renderChartsTab`, TradingView embeds come first and always render. History‑based charts can remain conditional below.

```jsx
const renderChartsTab = () => (
  <div className="insights-tab-body">
    <TradingViewChart symbol={symbol} interval="15" className="tv-block" />
    <TradingViewChart symbol={symbol} interval="60" className="tv-block" />

    {d.sentimentHistory.length > 0 ? (
      <SentimentHistoryChart data={d.sentimentHistory} />
    ) : (
      <div className="empty-card">
        Sentiment history warming up.
      </div>
    )}
  </div>
);
```

**Why:** TradingView is the always‑on backbone. Your own history charts are the layer that blooms once you have data.

---

## 3) Restore the purple rabbit modal background

You said the file is:

**Path:** `frontend/public/purple-rabbit-bg.png`

Because it’s in `public/`, reference it root‑relative. Add/confirm these styles:

```css
.sentiment-modal-shell {
  position: relative;
  background: rgba(10,10,12,0.9);
  border-radius: 20px;
  overflow: hidden;
}

.sentiment-modal-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url("/purple-rabbit-bg.png");
  background-size: cover;
  background-position: center;
  opacity: 0.12; /* subtle; tune as needed */
  pointer-events: none;
  mix-blend-mode: screen;
}

.sentiment-modal-content {
  position: relative;
  z-index: 1;
}
```

Then wrap your modal root:

```jsx
<div className="sentiment-modal-shell">
  <div className="sentiment-modal-content">
    {/* tabs + card */}
  </div>
</div>
```

This keeps the rabbit soft, spectral, and BHABIT‑clean — present but never loud.

---

## 4) Make tables feel fast again (reduce warm‑up drag)

With PanelShell/StatusGate, warm‑up thresholds can mask real rows. You want a simple precedence: if rows exist, you’re ready.

In each table component (or in `useData.js` if centralized):

```js
const status =
  error ? "error" :
  loading ? "loading" :
  rows.length > 0 ? "ready" :
  "empty";
```

**Outcome:**  
No more “loading lane” when data is already there. Skeletons vanish the moment the first real row arrives.

---

## 5) Smoke test checklist

1. Restart dev server (section 0).
2. Open a popup for a symbol with activity.
3. Overview:
   - Overall score, social volume change, fear/greed show real numbers.
4. Charts:
   - Two TradingView embeds load immediately.
   - Sentiment history chart appears once history exists.
5. Social:
   - Breakdown bars and/or history plots populate.
6. Data Sources:
   - Tier breakdown renders without crashing.

If any tab still shows zeros, log the normalized output:

```js
// temporary
console.debug("[sentiment normalized]", d);
```

You should see `overallSentiment` around 0.5–0.8 and non‑empty `sentimentHistory`.

---

## What this restores in spirit

- Stability first: no tab ever takes the app down.
- Immediate visual intel: TradingView always visible.
- Real narrative heat: snake_case payloads actually light the UI now.
- BHABIT atmosphere: purple rabbit background returned, subtle and alive.
- Faster boards: ready means ready, not “wait for a perfect hour.”

If you want the SentimentCard skin tightened next (spacing, hierarchy, micro‑badges), say the word and we’ll cut it to match your latest reference exactly.