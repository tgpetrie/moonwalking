**Scope**
This document defines null/zero/omit rules and stale definitions for `/api/sentiment-basic`, `/api/alerts`, and related `MetaHealth` fields. It is descriptive only and reflects current behavior.

**Null vs 0 vs Omit (Global Rules)**
- `null` means the value is unknown, unavailable, or not computed yet.
- `0` means a real numeric zero (valid measurement or count).
- Omit fields only where the code already omits them. For these endpoints, payload keys are generally present and use `null` when unknown.

**Stale Definitions And Thresholds**
- Backend sentiment-basic stale threshold: `SENTIMENT_BASIC_STALE_S` (env), default `60` seconds. Stale is `true` when no data or when `now - market_heat.ts` exceeds this threshold. Source: `backend/app.py:1362`.
- Frontend status pill stale threshold: `STALE_THRESHOLD = 20` seconds in `DashboardShell.jsx`; UI considers backend stale when `staleSeconds > STALE_THRESHOLD`. Source: `frontend/src/components/DashboardShell.jsx:200`.
- Cache stale-serving window (SWR): `CachePolicy.stale_seconds = 900` seconds (15 minutes) in `backend/cache.py`. Beyond TTL but within this window, cached payloads are served as stale. Source: `backend/cache.py:38` and `backend/cache.py:95`.
- SentimentCard freshness labels: `freshnessLabel` marks `< 2 min` as `fresh`, `< 10 min` as `recent`, otherwise `stale` based on `payload.timestamp`. Source: `frontend/src/components/cards/SentimentCard.jsx:6`.

**/api/sentiment-basic Null Rules**
- `ok`: always `true` in the current handler. Use `meta.ok` for actual health.
- `timestamp`: ISO string. Uses `market_heat.ts` when available, otherwise current time.
- `market_heat.score`: `null` when `has_data` is false; otherwise numeric 0-100.
- `market_heat.regime`: `null` when no data; otherwise string.
- `market_heat.label`: `null` when no data; otherwise string.
- `market_heat.confidence`: `null` when no data; otherwise numeric 0-1.
- `market_heat.components.green_1m`: numeric count/ratio when computed; `null` if unavailable.
- `market_heat.components.red_1m`: numeric count/ratio when computed; `null` if unavailable.
- `market_heat.components.green_3m`: numeric count/ratio when computed; `null` if unavailable.
- `market_heat.components.red_3m`: numeric count/ratio when computed; `null` if unavailable.
- `market_heat.components.total_symbols`: numeric count when computed; `null` if unavailable.
- `market_heat.components.avg_return_1m`: numeric return when computed; `null` if unavailable.
- `market_heat.components.avg_return_3m`: numeric return when computed; `null` if unavailable.
- `market_heat.components.volatility`: numeric when computed; `null` if unavailable.
- `market_heat.components.momentum_alignment`: numeric when computed; `null` if unavailable.
- `market_heat.components.breadth_1m`: numeric when computed; `null` if unavailable.
- `market_heat.components.breadth_3m`: numeric when computed; `null` if unavailable.
- `market_heat.reasons`: list of strings. Defaults to `"No price data yet"` when no data; otherwise `"Market in equilibrium"` if no specific reasons exist.
- `fear_greed.value`: `null` when F&G cache is empty or fetch failed.
- `fear_greed.classification`: empty string when unknown.
- `btc_funding.rate_percentage`: always `null` (not wired).
- `meta.ok`: `true` when `has_data` is true; `false` in exception handler.
- `meta.pipelineRunning`: `true` when not stale; otherwise `false`.
- `meta.staleSeconds`: integer seconds since `market_heat.ts`; `null` when no timestamp.
- `meta.lastOkTs`: `market_heat.ts` when `has_data` is true; otherwise `null`.
- `meta.error`: `null` in normal path; `"sentiment_basic_exception"` on exception.
- `meta.source`: `"internal"`.
- `meta.stale`: `true` when stale or no data; otherwise `false`.

**/api/alerts Null Rules**
- Top-level response: `{ "ok": true, "data": [...] }`. On errors, `data` is `[]` and `ok` remains `true`.
- Each alert item is validated against `AlertItem` and returns all schema fields with `null` when unknown.
- `pct`: `null` for basic alerts; if provided by an upstream alert source it should be numeric.
- `price`: `null` for basic alerts; if provided by an upstream alert source it should be numeric.
- `window`: `null` when unspecified; string like `"1m"` when provided.
- `severity`: required string; defaults to `"info"` if caller passed a falsy value.
- `message`: required non-empty string; `emit_alert()` will not create an alert without it.
- `extra`: always an object; `{}` when no extra metadata is provided.

**MetaHealth Rules (Fields Used By UI Status)**
- `ok`: boolean health flag. In sentiment-basic, derived from `has_data`; in pipeline meta, derived from successful polling.
- `pipelineRunning`: boolean; `true` when last successful data is recent enough, otherwise `false`.
- `staleSeconds`: integer seconds since last successful data; `null` if never succeeded.
- `lastOkTs`: ISO timestamp of last successful data; `null` if never succeeded.
- `error`: string describing the last failure; `null` when healthy.

**Examples: /api/sentiment-basic**
Fresh
```json
{
  "ok": true,
  "timestamp": "2026-02-07T12:00:00Z",
  "market_heat": {
    "score": 62,
    "regime": "risk_on",
    "label": "WARM",
    "confidence": 0.82,
    "components": {
      "green_1m": 42,
      "red_1m": 18,
      "green_3m": 38,
      "red_3m": 22,
      "total_symbols": 120,
      "avg_return_1m": 0.14,
      "avg_return_3m": 0.42,
      "volatility": 1.12,
      "momentum_alignment": 0.63,
      "breadth_1m": 0.70,
      "breadth_3m": 0.63
    },
    "reasons": ["Broad participation", "Momentum aligned"]
  },
  "fear_greed": {"value": 62, "classification": "Greed"},
  "btc_funding": {"rate_percentage": null},
  "meta": {
    "ok": true,
    "pipelineRunning": true,
    "staleSeconds": 5,
    "lastOkTs": "2026-02-07T12:00:00Z",
    "error": null,
    "source": "internal",
    "stale": false
  }
}
```
Stale but still serving
```json
{
  "ok": true,
  "timestamp": "2026-02-07T11:55:00Z",
  "market_heat": {
    "score": 58,
    "regime": "calm",
    "label": "NEUTRAL",
    "confidence": 0.45,
    "components": {
      "green_1m": 30,
      "red_1m": 28,
      "green_3m": 31,
      "red_3m": 27,
      "total_symbols": 120,
      "avg_return_1m": 0.02,
      "avg_return_3m": 0.06,
      "volatility": 0.98,
      "momentum_alignment": 0.51,
      "breadth_1m": 0.52,
      "breadth_3m": 0.53
    },
    "reasons": ["Market in equilibrium"]
  },
  "fear_greed": {"value": null, "classification": ""},
  "btc_funding": {"rate_percentage": null},
  "meta": {
    "ok": true,
    "pipelineRunning": false,
    "staleSeconds": 320,
    "lastOkTs": "2026-02-07T11:55:00Z",
    "error": null,
    "source": "internal",
    "stale": true
  }
}
```
Down/offline
```json
{
  "ok": true,
  "timestamp": "2026-02-07T12:05:00Z",
  "market_heat": {
    "score": null,
    "regime": null,
    "label": null,
    "confidence": null,
    "components": {
      "green_1m": null,
      "red_1m": null,
      "green_3m": null,
      "red_3m": null,
      "total_symbols": null,
      "avg_return_1m": null,
      "avg_return_3m": null,
      "volatility": null,
      "momentum_alignment": null,
      "breadth_1m": null,
      "breadth_3m": null
    },
    "reasons": ["No price data yet"]
  },
  "fear_greed": {"value": null, "classification": ""},
  "btc_funding": {"rate_percentage": null},
  "meta": {
    "ok": false,
    "pipelineRunning": false,
    "staleSeconds": null,
    "lastOkTs": null,
    "error": "sentiment_basic_exception",
    "source": "internal",
    "stale": true
  }
}
```

**Examples: /api/alerts**
Fresh
```json
{
  "ok": true,
  "data": [
    {
      "id": "impulse_1m_BTC-USD_1707307200000",
      "ts": "2026-02-07T12:00:00Z",
      "type": "impulse_1m",
      "severity": "medium",
      "symbol": "BTC-USD",
      "window": "1m",
      "window_s": null,
      "pct": null,
      "price": null,
      "price_now": null,
      "price_then": null,
      "vol_pct": null,
      "vol_now": null,
      "vol_then": null,
      "direction": null,
      "message": "BTC-USD moved +1.40% in 1m",
      "title": null,
      "product_id": null,
      "ts_ms": null,
      "event_ts": null,
      "event_ts_ms": null,
      "expires_at": null,
      "score": null,
      "sources": null,
      "trade_url": null,
      "meta": null,
      "extra": {"magnitude": 1.4, "pct": 1.4, "direction": "up"}
    }
  ]
}
```
Stale but still serving
```json
{
  "ok": true,
  "data": [
    {
      "id": "divergence_ETH-USD_1707303600000",
      "ts": "2026-02-07T11:00:00Z",
      "type": "divergence",
      "severity": "medium",
      "symbol": "ETH-USD",
      "window": "1m_vs_3m",
      "window_s": null,
      "pct": null,
      "price": null,
      "price_now": null,
      "price_then": null,
      "vol_pct": null,
      "vol_now": null,
      "vol_then": null,
      "direction": null,
      "message": "ETH-USD: 1m up +0.80% but 3m down -0.70% — possible reversal",
      "title": null,
      "product_id": null,
      "ts_ms": null,
      "event_ts": null,
      "event_ts_ms": null,
      "expires_at": null,
      "score": null,
      "sources": null,
      "trade_url": null,
      "meta": null,
      "extra": {"magnitude": 1.5, "direction": "reversal_up"}
    }
  ]
}
```
Down/offline
```json
{
  "ok": true,
  "data": []
}
```

**Search Anchors**
- `SENTIMENT_BASIC_STALE_S`
- `meta: {"source":`
- `STALE_THRESHOLD`
- `freshnessLabel`
- `stale_seconds`
- `btc_funding`
- `fear_greed`
- `expires_at`
