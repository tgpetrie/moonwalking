# AI Index

Project: BHABIT Moonwalking

Current instant-radar continuation: [Resume from anywhere](RESUME_HERE.md)
and [active work record](ACTIVE_WORK.json). Check these before relying on
an older chat or MacBook handoff for the current research branch/state.

Local no-credit helper: `scripts/local_ai.py`

- Usage and safety: `docs/ai/LOCAL_ASSISTANT.md`
- Good for grounded project questions, diff review, and log triage.
- Do not use the local 9B model as an unsupervised repository agent.

Read in this order before implementation:

1. `MW_SPEC.md`
2. `MW_BACKLOG.md`
3. `ARCHITECTURE.md`
4. `HANDOFF.md`
5. The relevant files under `docs/`
6. Touching CSS, colors, spacing, typography, or anything visual on any
   page: `docs/DESIGN_SYSTEM.md` first. It's the cross-system token
   reference (values live in `frontend/src/styles/design-tokens.css`) and
   says where the home board and the Moonwalking `/app/*` shell already
   agree, where they genuinely still disagree on purpose, and known gaps
   flagged but not silently fixed. `docs/FRONTEND_UI_RULES.md` and
   `docs/UI_CONTRACT.md` remain authoritative for the home board's own
   grid/row/motion rules specifically.

## Canonical runtime

- Frontend: Vite on `127.0.0.1:5173`
- Board API: Flask on `127.0.0.1:5003`
- Real-source sentiment: FastAPI on `127.0.0.1:8003`, accessed by the browser through Flask
- Local start: `./start_app.sh`
- Board endpoint: `GET /data`
- Health: `GET /api/health`

There is no active bridge service. Ports 5001, 5002, 5100, and 8002 are legacy.

On Tom's Windows PC, port 5003 is the **always-on collector**, not a dev
server: a scheduled task runs it from the `Moonwalking-Runtime` worktree and
writes every store to `%USERPROFILE%\.moonwalking\data`. Don't kill it or use
`--kill-port` on 5003; run dev backends on another port. See
`docs/developer/ALWAYS_ON_COLLECTOR.md`.

## Active frontend

- Mount: `frontend/src/main.jsx`
- Root router: `frontend/src/App.jsx`
- Public board: `frontend/src/components/DashboardShell.jsx`
- Single board poller: `frontend/src/context/DataContext.jsx`
- Guest/auth watchlists: `frontend/src/context/WatchlistContext.jsx`
- Product routes: `frontend/src/mvp/MvpApp.jsx`

Do not treat `frontend/src/Dashboard.jsx`, `legacy913`, playgrounds, backups, or original files as the active board.

## Active backend

- Board API and workers: `backend/app.py`
- Sentiment service: `backend/sentiment_api.py`
- Watchlist/auth blueprint: `backend/watchlist.py`
- Coin context: `backend/coin_intel_external.py`
- Local coin pressure: `backend/insights.py`
- Price baseline persistence: `backend/price_db.py`
- Canonical alerts: `backend/alerts_engine.py`

## Active alert/sentiment docs

- Alert behavior and thresholds: `docs/user-guides/ALERTS_USE_GUIDE.md`
- Alert contract: `docs/alerts_engine_spec.md`
- Sentiment/source matrix: `docs/SENTIMENT_SOURCES.md`
- Current audit: `docs/MOONWALKINGS_APP_AUDIT_2026-07-14.md`
- Handoff state: `HANDOFF.md`

## Non-negotiable data rules

- Real data only. Missing data is null/empty plus warming, unavailable, stale, or offline state.
- Canonical identity is `product_id`; UI text is the base symbol.
- Exactly one board polling context and one backend worker set.
- 1h price uses a real 1h price baseline.
- 1h volume uses a real 1h volume baseline. Never infer it from price.
- Market-wide sentiment must not be described as coin-specific.
- The frontend must not probe random ports or persist a noncanonical backend.

## UI rules

- One continuous board wrapper.
- Use the existing row and panel primitives; do not add a second layout system.
- Keep action controls stable. Animate data cells, not the whole row hit target.
- Top order: 1h price, 1m movers, 3m gainers/losers, Intelligence Log, Watchlist, 1h volume.
- Use Raleway and the current design tokens.

## Verification

```bash
npm run guardrails
.venv/bin/python -m pytest -q backend/tests
(cd frontend && npm run verify)
bash scripts/smoke_check.sh
bash scripts/smoke_sentiment_proxy.sh BTC
```

Do not commit or push unless Tom explicitly asks.
