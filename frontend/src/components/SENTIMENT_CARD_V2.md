
# SENTIMENT_CARD_V2.md
Author: ChatGPT  
Last updated: 2025-11-21

A developer-grade spec for the BHABIT / CBMo4ers Sentiment popup: stable fetching, normalized data, and crashproof tabs with TradingView charts.

---

## 0) Goal
Ship a stable, never‑crashing insights popup that:

1. Pulls real sentiment data from `/sentiment/latest` (FastAPI, port 8001 in dev).
2. Preserves the **last‑good snapshot** during revalidation or API outages.
3. Provides four tabs: **Overview**, **Social**, **Charts**, **Sources**.
4. Adds actionable intelligence: freshness, confidence, divergence, rhyme.
5. Matches BHABIT visual language: transparent shells, subtle glow, calm empty states.

---

## 1) Data Contract

### 1.1 Raw API
Endpoint:
- `GET {VITE_SENTIMENT_API_BASE}/sentiment/latest?symbol=UNI`
- Dev base: `http://127.0.0.1:8001`

Current raw shape:
```json
{
  "overall_sentiment": 0.53,
  "fear_greed_index": 55,
  "social_metrics": {
    "volume_change": 13.7,
    "engagement_rate": 0.88,
    "mentions_24h": 22566
  },
  "social_breakdown": {
    "reddit": 0.71,
    "twitter": 0.59,
    "telegram": 0.73,
    "chan": 0.42
  },
  "source_breakdown": {
    "tier1": 30,
    "tier2": 35,
    "tier3": 25,
    "fringe": 10
  },
  "sentiment_history": [
    {"timestamp":"...","sentiment":0.42,"price_normalized":57.59}
  ],
  "social_history": [
    {"timestamp":"...","reddit":0.63,"twitter":0.56,"telegram":0.71,"chan":0.36}
  ],
  "trending_topics":[{"tag":"#Bitcoin","sentiment":"bullish","volume":"+124%"}],
  "divergence_alerts":[{"type":"warning","message":"..."}]
}
```

### 1.2 Normalized Frontend Shape
Create a single adapter that always returns a safe, predictable object.

File:
- `frontend/src/adapters/normalizeSentiment.js`

Output shape:
```js
{
  ts: string | null,

  overallScore: number | null, // 0–100 int
  fearGreed: {
    value: number | null,      // 0–100 int
    label: "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed" | null
  },

  social: {
    volumeChangePct: number | null,   // can be negative
    engagementRatePct: number | null,
    mentions24h: number | null
  },

  channels: {                         // 0–100 ints
    reddit: number | null,
    twitter: number | null,
    telegram: number | null,
    chan: number | null
  },

  sources: {                          // already % shares
    tier1: number | null,
    tier2: number | null,
    tier3: number | null,
    fringe: number | null
  },

  sentimentSeries: Array<{t, sentiment, price}>,
  socialSeries: Array<{t, reddit, twitter, telegram, chan, composite}>,

  topics: Array<{tag, sentiment, volume}>,
  divergence: Array<{type, message}>,

  // derived (computed in adapter)
  freshnessSec: number | null,
  confidence: number | null,          // 0–100
  rhymeScore: number | null,          // -1..1 correlation
  divergenceBadge: {label, severity} | null
}
```

Adapter rules:
- Convert any 0–1 floats into 0–100 integers.
- Missing fields become **null**, never undefined.
- Derived fields computed only if inputs exist.

---

## 2) Hook: Stable Fetch + Last‑Good Snapshot

File:
- `frontend/src/hooks/useSentimentLatest.js`

Requirements:
1. Never return undefined data after a good snapshot has existed.
2. Expose SWR state cleanly.
3. Do not require components to call `refresh()`.

Reference:
```js
import useSWR from "swr";
import { normalizeSentiment } from "../adapters/normalizeSentiment";

const fetcher = (url) => fetch(url).then(r => r.json());

export function useSentimentLatest(symbol) {
  const base = import.meta.env.VITE_SENTIMENT_API_BASE || "";
  const url = symbol ? `${base}/sentiment/latest?symbol=${symbol}` : null;

  const lastGoodRef = useRef(null);

  const { data, error, isLoading, isValidating } = useSWR(url, fetcher, {
    refreshInterval: 35000,
    revalidateOnFocus: false,
    shouldRetryOnError: true,
    errorRetryInterval: 5000,
    dedupingInterval: 5000
  });

  const normalized = useMemo(() => {
    if (data) {
      const n = normalizeSentiment(data);
      lastGoodRef.current = n;
      return n;
    }
    return lastGoodRef.current; // last-good or null
  }, [data]);

  return {
    data: normalized,
    error,
    // loading only if no last-good exists
    isLoading: isLoading && !lastGoodRef.current,
    isValidating
  };
}
```

---

## 3) Popup Architecture

File:
- `frontend/src/components/InsightsTabbed.jsx`

Purpose:
- Fetch once per popup.
- Tabs never crash even if math/series fails.
- Charts tab uses TradingView only.

### 3.1 Tab State Contract
Tabs: `overview | social | charts | sources`

Compute status:
```js
const status =
  error ? "error"
  : isLoading ? "loading"
  : !snapshot ? "empty"
  : "ready";
```

### 3.2 Error Boundary
Wrap each tab so a tab failure does not kill React tree.

```jsx
class TabErrorBoundary extends React.Component {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(err) { console.error("[InsightsTabbed]", err); }
  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
```

Usage:
```jsx
<TabErrorBoundary fallback={<EmptyState title="Tab unavailable" />}>
  {renderSocialTab()}
</TabErrorBoundary>
```

---

## 4) SentimentCard v2 (Overview Tab)

File:
- `frontend/src/components/cards/SentimentCard.jsx`

Split into:
1. `SentimentCardBody({ snapshot, status })`
2. default wrapper `SentimentCard({ symbol, onClose })` that uses hook and renders body.

### 4.1 Layout Order (hierarchy)
1. Header: title, symbol, freshness, close.
2. Divergence badge.
3. Main metrics:
   - Overall score
   - Social volume change (24h)
   - Fear & Greed
   - Trend descriptor
4. Sentiment bar fill.
5. Confidence + Rhyme micro row.
6. Topics/alerts preview.

### 4.2 Derived Logic

#### Freshness
Adapter:
```js
freshnessSec = ts ? (Date.now() - new Date(ts).getTime())/1000 : null;
```

UI label:
- `< 60s` → "updated just now"
- `< 300s` → "updated Xm ago"
- else minutes/hours.

#### Confidence (0–100)
Heuristic:
```js
let score = 100;
if (!sentimentSeries.length) score -= 30;
if (!socialSeries.length) score -= 20;

const channelCount = Object.values(channels).filter(v => v != null).length;
score -= (4 - channelCount) * 7;

const sourceCount = Object.values(sources).filter(v => v != null).length;
score -= (4 - sourceCount) * 5;

const tierSpread = Math.max(...vals) - Math.min(...vals);
if (tierSpread > 40) score -= 10;

confidence = clamp(score, 0, 100);
```

UI badge:
- “Confidence 72/100”
- subtle hue shift based on range.

#### Divergence Badge
If `divergence.length > 0`:
- severity from alert type.
- labels:
  - "Narrative leads price"
  - "Price outrunning narrative"
  - "Fringe overheating"

#### Rhyme Score
If at least 5 points:
```js
rhymeScore = pearson(sentiments, prices); // -1..1
```

UI mapping:
- > 0.4: “Rhyme strong”
- 0.15–0.4: “Rhyme weak”
- -0.15–0.15: “No rhyme”
- < -0.15: “Split”

---

## 5) Social Tab v2

Uses normalized `channels` + `socialSeries`.

### 5.1 Leaderboard
Sort channels descending by value.

Delta:
```js
const prev = socialSeries.at(-2)?.[key];
const curr = socialSeries.at(-1)?.[key];
delta = prev != null && curr != null ? curr - prev : null;
```

Rows:
- Channel name
- Score
- Delta arrow or "–"
- Micro bar fill

### 5.2 Card States
- loading → skeleton rows
- empty → “No social series yet”
- ready → render even if some channel values null

Never compute delta unless both numbers exist.

---

## 6) Charts Tab v2 (TradingView)

File:
- `frontend/src/components/charts/TradingViewChart.jsx`

Two stacked embeds:
- 15m “Price action”
- 1h “Higher timeframe”

Symbol mapping:
```js
const mapToTV = (symbol) => `COINBASE:${symbol}USD`;
```

If no symbol → EmptyState.

---

## 7) Sources Tab v2

Uses `sources`.

Render:
- stacked horizontal bar
- 4 labels with percents

All null → EmptyState.

---

## 8) Styling (BHABIT Alignment)

### 8.1 Rabbit background asset
Source:
- `frontend/public/purple-rabbit-bg.png`

Popup shell CSS:
```css
.insights-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  background: url("/purple-rabbit-bg.png") center/cover no-repeat;
  opacity: 0.08;
  pointer-events: none;
}
```

### 8.2 Panel shell
Every tab uses:
- transparent fill
- subtle inner glow on hover
- no heavy borders
- calm empty/error copy
- reuse PanelShell + StatusGate (4‑state contract)

---

## 9) Performance + Safety Rules
1. No derived math in render unless `status === "ready"`.
2. `useMemo` for series transforms.
3. Never `.map` a possibly null array.
4. Use `snapshot?.field ?? null`.
5. ErrorBoundary per tab.
6. One hook call per popup.

---

## 10) Implementation Steps

### Step 0: Adapter
- Add `normalizeSentiment.js`.
- Export `normalizeSentiment(raw)`.

### Step 1: Hook
- Ensure last‑good ref + adapter integration.

### Step 2: SentimentCard body
- Split wrapper vs body.
- Add derived UI blocks (freshness, confidence, divergence, rhyme).

### Step 3: InsightsTabbed
- One fetch.
- Compute `status`.
- Wrap tab content with TabErrorBoundary.
- Social leaderboard + TradingView charts.

### Step 4: Styling pass
- Add rabbit background.
- Tune opacity/positioning to BHABIT standard.

### Step 5: QA
1. API online → all tabs switch, no crash.
2. API offline → Overview keeps last‑good; other tabs show empty/error.
3. Hard refresh → fast paint if last‑good exists.
4. Rapid tab switching → no extra fetch, no leaks.

---

# Backlog Tickets (ready to paste into GitHub)

## Ticket 1 — Add normalizeSentiment adapter
**Goal:** Centralize raw → UI‑safe sentiment mapping.

**Tasks**
- Create `frontend/src/adapters/normalizeSentiment.js`.
- Map raw floats to 0–100 ints.
- Return null for missing fields.
- Compute freshnessSec, confidence, rhymeScore, divergenceBadge.

**Acceptance**
- Given partial raw payload, adapter returns full normalized shape with only nulls, no undefined.
- Derived fields only present when computable.

---

## Ticket 2 — Harden useSentimentLatest hook
**Goal:** Preserve last‑good snapshot and reduce UI jitter.

**Tasks**
- Ensure lastGoodRef logic matches spec.
- Return isLoading only when no last‑good exists.
- Confirm env base reads `VITE_SENTIMENT_API_BASE`.

**Acceptance**
- With API flapping, Overview never blanks.
- No component calls refresh manually.

---

## Ticket 3 — Refactor SentimentCard to wrapper + body
**Goal:** Decouple layout from fetching and enforce 4‑state contract.

**Tasks**
- Split into `SentimentCardBody({ snapshot, status })` + wrapper.
- Add freshness, divergence badge, confidence, rhyme micro row.
- Add sentiment bar fill.

**Acceptance**
- Body renders stable empty/loading/error/ready states.
- Wrapper is ~10 lines: hook → status → body.

---

## Ticket 4 — Social tab leaderboard
**Goal:** Make Social tab useful and safe on partial data.

**Tasks**
- Use channels + socialSeries.
- Sort by score, compute delta with guards.
- Add micro bars + labels.

**Acceptance**
- Tab never crashes with missing series.
- Delta absent shows “–”.

---

## Ticket 5 — TradingView Charts tab
**Goal:** Restore old chart experience reliably.

**Tasks**
- Keep `TradingViewChart.jsx` iframe wrapper.
- Add two embeds (15m and 1h).
- Robust symbol → TV ticker mapping.

**Acceptance**
- Charts tab loads even if sentimentSeries empty.
- No React crash from widget errors.

---

## Ticket 6 — Sources tab stacked bar
**Goal:** Visualize tier distribution and confidence.

**Tasks**
- Render stacked bar from sources.
- Label tiers and percents.
- Empty state if all null.

**Acceptance**
- Tab stable with null data.
- Bar sums to 100 when inputs valid.

---

## Ticket 7 — Popup BHABIT styling pass
**Goal:** Restore BHABIT feel and rabbit background.

**Tasks**
- Add `purple-rabbit-bg.png` pseudo layer.
- Ensure opacity subtle.
- Confirm transparent shells + hover glow.

**Acceptance**
- Popup matches BHABIT contrast/tones.
- No build warnings for missing assets.

---

End.
