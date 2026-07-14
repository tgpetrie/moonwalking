# Moonwalking Architecture

This document describes the current runtime. Product and data truth rules remain authoritative in `MW_SPEC.md`.

## Runtime topology

### Local development

`./start_app.sh` is the canonical entrypoint and starts exactly three services:

1. Vite frontend at `http://127.0.0.1:5173`
2. Flask board API at `http://127.0.0.1:5003`
3. FastAPI real-source sentiment service at `http://127.0.0.1:8003`

Vite talks to Flask. Flask proxies the dedicated sentiment service through `/api/sentiment/latest`, so browser code has one API authority. The old bridge service and ports 5001/5002/5100/8002 are not part of the active runtime.

### Single-box production

The supported deployment is the kit under `deploy/homeserver/` on an Oracle Cloud Always Free ARM VM or compatible Linux host:

- The frontend is built once and served by Flask on the same origin.
- Gunicorn runs one worker because the price, volume, and alert engines are in-process singleton workers.
- The sentiment service runs as a separate local process on port 8003.
- Tailscale provides private access; no public application port is required.
- SQLite stores price snapshots, alerts, volume baselines, and account-backed watchlists on the same box.

The current MVP is deliberately one-box. Multiple Flask workers or replicas would duplicate market workers and require a separate job system and shared database first.

## Data flow

```text
Coinbase WebSocket + bounded REST fallback
                 |
                 v
      Flask singleton market worker
                 |
       SQLite baselines + snapshots
                 |
      /data + /api/alerts + /api/insights
                 |
                 v
       DataContext (single UI poller)
                 |
                 v
 price banner -> 1m -> 3m -> intelligence -> watchlist -> volume banner

Alternative.me + CoinGecko
                 |
                 v
  FastAPI sentiment service (:8003)
                 |
                 v
  Flask /api/sentiment/latest proxy
                 |
                 v
       Market-wide sentiment UI
```

## Backend responsibilities

### Flask board API

- Owns the Coinbase price feed and bounded REST fallback.
- Maintains one price/snapshot worker and one 1h-volume worker.
- Computes 1m, 3m, and 1h price changes from real timestamped baselines.
- Computes 1h volume movement from real candle or SQLite baselines.
- Publishes the canonical `/data` snapshot and the alert stream.
- Serves local tape-based coin insights at `/api/insights/<symbol>`.
- Serves real external coin context at `/api/coin-intel?symbol=<symbol>`.
- Owns SQLite-backed signup, login, sessions, and persistent watchlists.

Script startup occurs only after the complete Flask route table has been registered. Request handling cannot silently create a second sentiment worker.

### Sentiment service

- Fetches Alternative.me Fear and Greed and CoinGecko global market data.
- Returns explicit `live`, `stale`, or `offline` state with source provenance.
- Leaves social, history, topics, and divergence fields null or empty when no real provider exists.
- Never manufactures neutral scores, headlines, social counts, or history.

Market-wide sentiment is labeled market-wide even when a coin triggered the popup. Coin-specific pressure comes from real local tape and alert evidence, not cloned market sentiment.

## Frontend responsibilities

- `frontend/src/main.jsx` mounts `App.jsx`.
- `/` renders `DashboardShell`; `/login`, `/signup`, and `/app/*` render the product shell.
- `DataContext` is the only board polling orchestrator.
- `WatchlistContext` keeps guest entries local and switches to API-backed persistence only for authenticated sessions.
- The board uses one continuous wrapper and stable action hit targets; data cells may animate without translating whole rows.
- Missing data stays null and renders as warming, unavailable, stale, or offline.

## Identity and storage

- Canonical asset identity is Coinbase `product_id`; display text is the base symbol.
- Guest watchlist state lives in browser local storage.
- Authenticated watchlists live in `backend/data/watchlists.sqlite` unless `WATCHLIST_DB_PATH` overrides it.
- Session cookies are HttpOnly; production requires a stable `SECRET_KEY`.
- No AI provider, cloud database, telemetry service, or exchange credential is required for the core board.

## Operational constraints

- Run `./start_app.sh` for local work.
- Run one Gunicorn worker in the supported deployment.
- Do not start `backend/app.py` a second time beside the canonical entrypoint.
- Do not substitute one metric for another. In particular, price movement is not a volume estimate and 24h movement is not a 1h estimate.
- During baseline warmup, return an empty list plus an explicit warming state.
