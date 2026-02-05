# Sentiment Card v2 – Implementation Spec

## Goal
Sentiment popup should always show a reliable, insight-rich snapshot sourced from `/sentiment/latest`, maintain the last good payload during hiccups, and expose four resilient tabs (Overview, Social, Charts, Sources) that follow BHABIT visuals.

## 1. Data Contract
### 1.1 Raw API
- Endpoint: `GET {VITE_SENTIMENT_API_BASE}/sentiment/latest?symbol=SYMBOL` (dev base `http://127.0.0.1:8001`).
- Current payload fields: `overall_sentiment`, `fear_greed_index`, `social_metrics`, `social_breakdown`, `source_breakdown`, `sentiment_history`, `social_history`, `trending_topics`, `divergence_alerts`.

### 1.2 Normalized Frontend Shape (`frontend/src/adapters/normalizeSentiment.js`)
Adapter output (all keys always present, null when unknown):
```
{
  ts,
  overallScore,
  fearGreed: { value, label },
  social: { volumeChangePct, engagementRatePct, mentions24h },
  channels: { reddit, twitter, telegram, chan },
  sources: { tier1, tier2, tier3, fringe },
  sentimentSeries: Array<{ t, sentiment, price }>,
  socialSeries: Array<{ t, reddit, twitter, telegram, chan, composite }>,
  topics: Array<{ tag, sentiment, volume }>,
  divergence: Array<{ type, message }>,
  freshnessSec,
  confidence,
  rhymeScore,
  divergenceBadge
}
```
Rules:
- Convert 0–1 floats to 0–100 scores.
- Guard every field; never return `undefined`.
- Derived metrics only computed when inputs exist (freshness, confidence, rhyme, badge).

## 2. Hook (`frontend/src/hooks/useSentimentLatest.js`)
- Plain `fetch` loop that always hits `{base}/sentiment/latest` even when `symbol` is missing.
- Maintains `lastGoodRef` so once data is available it persists through errors.
- Poll interval defaults to `30s`; components may override via `refreshMs` and can pause with `{ enabled: false }`.
- Returns `{ data, raw, loading, validating, error, refresh }` where `loading` is only true before the first successful payload.
- Never expose raw snake_case data directly to the UI—`data` always flows through `normalizeSentiment`.

## 3. Popup Architecture (`frontend/src/components/InsightsTabbed.jsx`)
- One hook call per popup; pass `symbol` through.
- Compute `status` (`loading | error | empty | ready`) once using normalized snapshot.
- Wrap each tab body in `TabErrorBoundary` with a calm fallback.
- Tabs: Overview (card body), Social (channel leaderboard + signals), Charts (TradingView embeds), Sources (coverage + topics + divergence).
- No tab runs derived math before confirming `status === "ready"`.

## 4. Sentiment Card v2 (`frontend/src/components/cards/SentimentCard.jsx`)
Structure:
1. Header with symbol, freshness chip, optional close.
2. Divergence badge when present.
3. Main metric row: Overall, Volume Δ 24h, Fear & Greed label, Trend word.
4. Sentiment bar (0–100 fill).
5. Confidence + Rhyme mini row.
6. Topics + divergence preview list.

Derived logic highlights:
- Freshness phrases (`just now`, `4m ago`, etc.).
- Confidence heuristic (start at 100, subtract for missing series/channels/sources and big tier spreads, clamp to 0–100).
- Divergence badge severity from alert type/text (Narrative leads price, Price outrunning narrative, Fringe overheating, etc.).
- Rhyme score via Pearson correlation between sentiment and price series (>=5 points). Label categories: Rhyme strong, Rhyme weak, No rhyme, Split.

## 5. Social Tab v2
- Leaderboard built from normalized `channels` + latest `socialSeries` rows.
- Sort channels descending, show score, delta arrow (computed only when previous point exists), and micro bar fill.
- Include metrics grid, trending topics, divergence alerts, and optional TradingView Technical widget for “Technical pulse”.
- Empty/Loading states: skeleton or “No social signals yet. Give it a minute to breathe.”

## 6. Charts Tab v2
- Exclusive TradingView usage via `frontend/src/components/charts/TradingViewChart.jsx`.
- Embed two widgets (15m Price action, 1h Higher timeframe) mapped to Coinbase tickers (`COINBASE:${SYMBOL}USD`, fallback to Binance with `USDT`).
- If symbol missing, show empty-state message.

## 7. Sources Tab v2
- Use normalized `sources`, `topics`, `divergence` arrays.
- Render coverage mix (stacked bar or grid), trending topic list, divergence rows.
- Empty state when every value null/zero.

## 11. Source Catalog (versioned in repo)
- Location: `backend/sentiment/sources/*.json` grouped by tier (tier1/tier2/tier3/fringe).
- Loader: `backend/sentiment/loaders/source_loader.py` merges the JSON into the FastAPI service.
- When adding a source, update the relevant JSON file and commit alongside any pipeline changes; `/sentiment/sources` automatically reflects the new entry.

## 8. Styling Requirements
- Rabbit background asset: `/purple-rabbit-bg.png`. Apply via `.insights-shell::before` with subtle opacity and pointer-events disabled.
- Use transparent panel shells (`panel-soft`, inner glow), consistent section titles, and calm empty/error states across tabs.

## 9. Safety + Performance Rules
1. Never run `.map` on non-arrays; pre-normalize.
2. Derived math only when `status === "ready"`.
3. Heavy transforms wrapped in `useMemo` keyed by raw payload.
4. Tabs isolated by `TabErrorBoundary`.
5. One network call per popup session; no redundant fetches when switching tabs.

## 10. Implementation Plan
1. Build adapter (`normalizeSentiment.js`).
2. Update hook to use adapter + last-good cache.
3. Refactor SentimentCard into wrapper/body with new layout + derived metrics.
4. Rebuild InsightsTabbed: single hook, status gate, error boundaries, new Social + TradingView tabs.
5. Styling pass (rabbit asset + shell consistency).
6. QA pass: verify online/offline behavior, tab switching, cache freshness, and absence of additional fetches.

## QA Checklist
- ✅ Overview shows live data; Social/Charts/Sources switch crash-free.
- ✅ Killing API still shows cached snapshot + calm errors.
- ✅ Fresh load paints instantly when cached data exists.
- ✅ Rapid tab toggling does not spawn extra fetches or memory leaks.

---

## Backlog Tickets
1. **FEAT-001: Normalize sentiment payload**  
   *Acceptance Criteria:* Adapter returns fully populated object (null defaults) for valid fixture payloads, converts 0–1 floats to 0–100, produces derived freshness/confidence/rhyme when inputs exist, and includes unit tests covering missing-field scenarios.

2. **FEAT-002: Harden `useSentimentLatest` hook**  
   *Acceptance Criteria:* Hook reads `VITE_SENTIMENT_API_BASE`, caches and returns last-good snapshot when new fetch fails, exposes `{ data, raw, loading, validating, error, refresh }`, and triggers only one request per popup instance even when tabs switch rapidly.

3. **FEAT-003: Implement Sentiment Card v2 UI**  
   *Acceptance Criteria:* Overview tab renders header, divergence badge, metric row, sentiment bar, confidence/rhyme indicators, and topics preview using normalized data; freshness text updates live; layout matches BHABIT styles; component never crashes with partial data.

4. **FEAT-004: Rebuild Social tab with leaderboard + TradingView tech widget**  
   *Acceptance Criteria:* Tab renders metrics grid, channel leaderboard (sorted, with delta arrows and micro bars), trending topics, divergence alerts, and TradingView Technical widget when symbol exists; handles loading/empty states gracefully; calculations guard against missing series.

5. **FEAT-005: Replace Charts tab with TradingView embeds**  
   *Acceptance Criteria:* Tab displays two TradingView iframes (15m and 1h) for the current symbol, falls back to empty state without symbol, and never blocks or crashes the popup even if TradingView fails to load.

6. **FEAT-006: Source mix + topics tab polish**  
   *Acceptance Criteria:* Sources tab renders coverage mix bar/grid, topic list, and divergence alerts only when data present; empty state appears when all values null; styling aligns with panel-soft conventions.

7. **FEAT-007: Apply BHABIT shell + rabbit background**  
   *Acceptance Criteria:* Popup shell includes `/purple-rabbit-bg.png` overlay with specified opacity, all panels share the same transparent styling, and empty/error states use the calm copy from spec.
