# Sentiment Smoke Check

Use the canonical runtime; do not start Flask and Vite independently.

```bash
./start_app.sh
```

Then verify:

```bash
curl -sS http://127.0.0.1:5003/api/health | jq .
curl -sS 'http://127.0.0.1:5003/api/sentiment/latest?symbol=BTC' | jq .
```

Open `http://127.0.0.1:5173`, click a row to open Coin Pressure, and confirm:

- The selected symbol appears in the header.
- Real local tape fields render or say warming.
- Real market sentiment renders as market-wide, or says stale/offline/unavailable.
- Missing values render as a dash or unavailable state, never `NaN` or a fake midpoint.
- `/api/insights/<symbol>` and `/api/coin-intel?symbol=<symbol>` complete without a 404.
- The browser console has no application errors.

The complete checklist is `docs/testing/SENTIMENT_UPGRADE_VERIFICATION.md`.
