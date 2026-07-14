# Sentiment Integration Checklist

## Canonical services

- Flask board API: port 5003
- FastAPI real-source sentiment: port 8003
- Vite frontend: port 5173
- Browser entrypoint: `/api/sentiment/latest` through Flask

## Truth contract

- [x] One normalized frontend shape in `frontend/src/adapters/normalizeSentiment.js`.
- [x] `sentiment_meta` exposes pipeline state, timestamps, scope, and sources.
- [x] Upstream data exposes `live`, `stale`, or `offline` status.
- [x] Market-wide data is labeled `market_wide`.
- [x] Missing numeric values stay null.
- [x] Missing social, history, topics, and divergence remain empty.
- [x] No random, hash-derived, mock, or neutral-value fallbacks.
- [x] One popup poll loop per open symbol.
- [x] Coin pressure uses real local price/alert evidence.
- [x] External coin context uses `/api/coin-intel`.

## Current real sources

- Alternative.me Fear and Greed
- CoinGecko global market data
- Coinbase local price tape and timestamped baselines
- CoinPaprika coin events/timeline through `/api/coin-intel` when available
- CoinGecko coin community data as a coin-context proxy when available
- LunarCrush social metrics only when `LUNARCRUSH_API_KEY` or `LUNARCRUSH_KEY` is configured

See `docs/SENTIMENT_SOURCES.md` for the source/access matrix and primary documentation links.

Configured source catalogs without provider implementations are metadata only. They must not count as active coverage.

## Required UI states

- Live: render populated real fields with source and update time.
- Stale: render bounded last-good data with stale labeling.
- Offline: render offline state and no invented numeric values.
- Unavailable: render a dash or explanatory copy for a source that has no provider.
- Warming: render while local 1m, 3m, or 1h baselines mature.

## Verification

Use `docs/testing/SENTIMENT_UPGRADE_VERIFICATION.md` and run:

```bash
.venv/bin/python -m pytest -q backend/tests/test_sentiment_api_truth.py
(cd frontend && npm run test -- --run src/adapters/__tests__/normalizeSentiment.test.js)
```

Any new provider must include provenance, a bounded cache policy, rate controls, offline behavior, and tests before its values appear in the UI.
