# Sentiment Truth Verification

This checklist verifies the current real-source sentiment contract.

## Start

```bash
./start_app.sh
```

Expected services:

- Flask board API: `127.0.0.1:5003`
- FastAPI sentiment service: `127.0.0.1:8003`
- Vite frontend: `127.0.0.1:5173`

## Automated checks

```bash
.venv/bin/python -m pytest -q backend/tests/test_sentiment_api_truth.py
(cd frontend && npm run test -- --run src/adapters/__tests__/normalizeSentiment.test.js)
```

## Endpoint checks

```bash
curl -sS http://127.0.0.1:8003/health | jq .
curl -sS http://127.0.0.1:8003/sentiment/latest | jq .
curl -sS 'http://127.0.0.1:5003/api/sentiment/latest?symbol=BTC' | jq .
```

Verify:

- `data_status` is `live`, `stale`, or `offline`.
- Every populated external block has source provenance and an update time.
- `scope` is `market_wide` unless a future real coin-specific provider explicitly says otherwise.
- Missing social, history, topics, and divergence data is null or empty.
- No random or neutral fallback is shown.

## Offline behavior

Stop the sentiment process and request the Flask endpoint again.

- A bounded last-good response may return as `stale`.
- With no bounded cache, the endpoint returns an explicit offline error.
- The frontend must render stale/offline/unavailable state and preserve null values.

## Browser behavior

Open several coin pressure panels.

- The coin header and local tape fields change with the selected symbol.
- Market sentiment is labeled market-wide.
- An unavailable social source is not replaced by a zero or midpoint.
- Opening and closing the panel produces no console errors.

## Troubleshooting

If port 5003 is already occupied, stop the existing Moonwalking process before starting another. Do not start the backend on an alternate port because that creates a split runtime.
