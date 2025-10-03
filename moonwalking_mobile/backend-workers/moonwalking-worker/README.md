# Moonwalking Worker (Cloudflare)

Endpoints:

- `GET /data` → Data bundle for app Home
- `GET /signals/pumpdump` → Pro signals (pump/dump)
- `GET /sentiment?symbols=BTC-USD,ETH-USD` → Latest sentiment rows (Pro)
- `GET /watchlist` | `POST /watchlist/add` | `POST /watchlist/remove` → per-device watchlist via Durable Object
- `POST /devices/register` → registers Expo push token
- `POST /mock/seed` → dev-only seeding (requires `X-Cron-Secret`)

Cron:

- builds bundle and signals
- ingests sentiment via connectors (stubs) and aggregates per symbol
- enqueues alerts to Queue when thresholds hit

## Dev

```
npm install -g wrangler
wrangler dev
# (optional) add types locally if doing type-checks
npm add -D @cloudflare/workers-types typescript
# run typecheck / format
npm run typecheck
npm run format
# seed sample payloads
curl -X POST http://127.0.0.1:8787/mock/seed -H "X-Cron-Secret: set-a-strong-random-value"
```
