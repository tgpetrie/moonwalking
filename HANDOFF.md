# Moonwalking / BHABIT Handoff

## Snapshot

- Date: 2026-07-20
- Branch: `main` at `478288ad` (all feature branches merged)
- Repository: `tgpetrie/moonwalking` on GitHub
- Product: BHABIT — personal crypto trading assistant dashboard at https://bhabit.net
- Owner: Tom (tgpetrie), solo operator. This is an information-only tool, NOT autonomous trading.

## Production

- **Live at https://bhabit.net** — Cloudflare DNS/TLS → Railway container
- **Deploy config**: `railway.json` (Dockerfile builder pointing at `backend/Dockerfile`)
- **GitHub repo connected** to Railway (`tgpetrie/moonwalking`, branch `main`). Auto-deploy shows "unavailable" — may need manual deploy trigger from Railway Deployments tab.
- **Health check**: `/api/health` with 300s timeout
- **Current deploy gap**: GitHub `main` has all features pushed (including Event Evolution, Portfolio Mode, notification priority). Production may still be running an older build — trigger a deploy from Railway dashboard to pick up new code.

## Architecture

```
Frontend (React/Vite)          Backend (Flask, single process)
  localhost:5173        →        localhost:5003
                                   ├── Coinbase WS ticker feed (live prices)
                                   ├── Alert engine (coin pressure detection)
                                   ├── Event Evolution (signal grouping)
                                   ├── Signal/Board outcome grading
                                   ├── Portfolio Mode (read-only Coinbase CDP)
                                   └── Notification dispatch (SMTP/Telegram/Discord)

Sentiment Service (FastAPI)
  localhost:8003         ←     proxied via Flask at /api/sentiment/*
```

### Key files and line counts

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app.py` | ~14,000 | Main Flask app — routes, background workers, data pipeline |
| `backend/alert_events.py` | 685 | Event Evolution: groups raw alerts → Signals with state transitions |
| `backend/signal_outcomes.py` | 309 | Tracks signal accuracy at 5m/15m/30m/60m checkpoints |
| `backend/board_outcomes.py` | 706 | Tracks mover-board accuracy with Wilson confidence intervals |
| `backend/portfolio_mode.py` | 699 | Read-only Coinbase CDP API client, permission enforcement |
| `backend/alert_delivery.py` | 273 | Notification dispatch (SMTP, Telegram, Discord, browser) |
| `backend/coinbase_ws.py` | 365 | WebSocket ticker feed with reconnect/backoff |
| `backend/alerts_engine.py` | ~150 | Raw coin pressure detection (feeds into Event Evolution) |
| `backend/watchlist.py` | ~900 | SQLite-backed user accounts, auth, session handling |
| `backend/sentiment_api.py` | ~570 | FastAPI sentiment service (Alternative.me + CoinGecko) |

### Frontend components (React/JSX)

- `DashboardShell.jsx` — main layout, tab routing
- `TokenRowUnified.jsx` — board row with pressure cues
- `AlertsTab.jsx` / `AlertsDock.jsx` — Signals/Pulse alert display
- `SentimentPopupAdvanced.jsx` — coin detail popup with Quick Buy Read
- `TopBannerScroll.jsx` / `VolumeBannerScroll.jsx` — scrolling ticker banners
- `AuthPanel.jsx` / `WatchlistPanel.jsx` — login/signup, watchlist management
- `PortfolioModePage.jsx` — portfolio holdings display (in `frontend/src/mvp/`)

## What's built and working

### 1. Live price board
Real-time crypto prices via Coinbase WebSocket feed (`coinbase_ws.py`). Falls back to REST polling for products without WS ticks. Board shows 1m/3m gainers/losers with pressure indicators.

### 2. Alert engine → Event Evolution pipeline
Raw alerts from `alerts_engine.py` (volume spikes, momentum shifts, divergences) feed into `alert_events.py` which groups them into per-coin **Events** with:
- State machine: `Building → Strengthening → Confirmed → Weakening → Fading`
- Confidence scores (0-100)
- Direction classification (up/down/neutral)
- "The Read" — human-readable interpretation (e.g., `BUY WATCH`, `TRAP RISK`, `NO CHASE`)
- Transition history with timestamps

### 3. Signal outcome tracking (PARTIALLY COMPLETE — see "What's next")
Two SQLite-backed stores run in parallel:

**SignalOutcomeStore** (`signal_outcomes.py`):
- Records entry price when a signal is created
- Measures directional returns at 5m, 15m, 30m, 60m
- Tracks max favorable and max adverse excursion
- Grades outcome as `followed_through` (hit +2% target before -1% stop) or `did_not_follow_through`
- `history_for(event)` returns historical win rate for same signal type+direction
- API: `/api/signals/outcomes/status`

**BoardOutcomeStore** (`board_outcomes.py`):
- Same checkpoint structure for mover-board entries
- Adds Wilson confidence intervals for small-sample stats
- Tracks by board type (ignition_1m, confirmation_3m_up, confirmation_3m_down)
- API: `/api/boards/outcomes/status`

**Both are wired into the main loop** at `app.py:13026` and `app.py:13127` — `observe()` is called every tick with current prices.

### 4. Portfolio Mode (read-only Coinbase integration)
- Coinbase CDP API with JWT auth (`portfolio_mode.py`)
- **Permission enforcement**: refuses keys with `can_trade` or `can_transfer` — view-only enforced in code
- Shows holdings, cost basis, allocation
- `get_held_symbols()` feeds into notification priority
- Needs 3 Railway env vars to activate: `COINBASE_API_KEY_NAME`, `COINBASE_API_KEY_SECRET`, `MW_PORTFOLIO_OWNER_TOKEN`

### 5. Portfolio-aware notification priority
- Coins you hold qualify for notifications at confidence 65+ (vs standard 85+)
- Implemented in `alert_events.py:notification_candidates()` and wired in `app.py`
- Tags elevated notifications with `priority: "holding"` and `notify_reason: "holding_priority"`
- 8 tests in `backend/tests/test_priority_notifications.py`

### 6. Coinbase OAuth integration
- Full OAuth 2.0 flow in `backend/coinbase_oauth.py` (250 lines)
- 4 routes in `app.py`: authorize, callback, disconnect, status
- CSRF state validation, token refresh with persistence to SQLite
- `portfolio_mode.py` tries OAuth first, falls back to env-var CDP keys
- Schema migration in `watchlist.py` adds token columns to users table
- For single-user: just set `COINBASE_PORTFOLIO_OWNER_EMAIL` env var (simpler path)

### 7. Position Intelligence
- `backend/position_intel.py` enriches portfolio with signal context
- API: `/api/portfolio/intel` — portfolio snapshot + per-holding signal data
- Per-holding: current signal state, posture (favorable/adverse/fading/developing), historical outcome stats
- Per-order: stop-loss/take-profit classification, distance from current, signal-aware context ("Signal weakening — consider tightening stop")
- Cross-references 29K+ graded outcomes from `signal_outcomes.py`
- 8 tests in `backend/tests/test_position_intel.py`
- **DECISION (2026-07-22): `/api/portfolio/intel` is intentionally env-var owner-only for now, NOT OAuth-aware.** Unlike `/api/portfolio` (which tries the user's OAuth token first), the intel route still gates on `COINBASE_PORTFOLIO_OWNER_EMAIL` and builds the client from static CDP keys. Rationale: no frontend consumes `/api/portfolio/intel` yet, so opening it to all OAuth users would be a speculative multi-user feature with no UI to validate against. Extending OAuth is a ~20-line refactor (lift the OAuth-lookup block from `portfolio_snapshot()` into a shared helper both routes call) — defer it to whenever the intel UI is actually built, and wire both in one stroke.

### 8. Notification delivery channels
`alert_delivery.py` supports SMTP email, Telegram bot, Discord webhook, and browser push. Per-symbol cooldowns and hourly caps. All channels disabled until credentials are set.

### 9. Cross-device watchlist with auth
SQLite-backed accounts (`watchlist.py`), session cookies (HttpOnly/Secure/SameSite), CORS with credentials. Guest watchlist migrates to account on signup.

## What's NOT built yet (the gaps)

### A. Outcome scorecard UI (HIGH PRIORITY)
The outcome data is **collecting in SQLite** but there's **no dashboard to view it**. Need:
- Aggregate accuracy panel: "Bullish Breakout signals followed through 62% over 200 samples"
- Per-signal-type breakdown with win rates, median favorable/adverse moves
- Time-series view showing whether accuracy is improving or degrading
- Per-coin history (currently `history_for()` groups by type+direction, not by individual coin)

### B. Feedback loop to auto-tune thresholds
Outcome data doesn't feed back to adjust:
- Confidence thresholds for notifications (hardcoded 85% standard, 65% held)
- Alert engine sensitivity parameters
- Which signal types should even generate notifications vs just log

### C. Notification outcome tracking
Signals are graded, but there's no separate tracking of "did notifications I *received* lead to useful action?" — the ultimate quality metric for the trading assistant use case.

### D. Notification channel activation
SMTP, Telegram, Discord, browser push are coded but need credentials configured:
- `MW_SMTP_HOST`, `MW_SMTP_USER`, `MW_SMTP_PASS`, `MW_NOTIFY_EMAIL_TO`
- `MW_TELEGRAM_BOT_TOKEN`, `MW_TELEGRAM_CHAT_ID`
- `MW_DISCORD_WEBHOOK_URL`

### E. Portfolio Mode activation
Needs Coinbase CDP API key (view-only!) created at https://portal.cdp.coinbase.com and set in Railway:
- `COINBASE_API_KEY_NAME`
- `COINBASE_API_KEY_SECRET`
- `MW_PORTFOLIO_OWNER_TOKEN` (any secret string, used to gate the endpoint)

### F. Production deploy verification
GitHub→Railway connection is set up but auto-deploy shows "unavailable". Current production may be running old code. Need to:
1. Trigger manual deploy from Railway Deployments tab
2. Verify `/api/alerts/recent` returns `signals` and `pulse` fields
3. Verify `/api/signals/outcomes/status` is reachable
4. Verify `/api/boards/outcomes/status` is reachable

## Environment variables (production)

Required:
- `SECRET_KEY` — session encryption (Railway generateValue handles this)
- `FLASK_ENV=production`
- `SESSION_COOKIE_SECURE=1`
- `CORS_ORIGINS=https://bhabit.net`
- `SERVE_FRONTEND_DIST=1` — serves built frontend from Flask

Optional (enable features):
- `ENABLE_COINBASE_WS=1` (default on) — live WebSocket prices
- `COINBASE_API_KEY_NAME` / `COINBASE_API_KEY_SECRET` — portfolio mode
- `MW_PORTFOLIO_OWNER_TOKEN` — gates portfolio API access
- `MW_SMTP_*` / `MW_TELEGRAM_*` / `MW_DISCORD_*` — notification channels
- `WATCHLIST_DB_PATH` — SQLite location (Railway persistent disk)
- `MW_SIGNAL_OUTCOMES_DB` / `MW_BOARD_OUTCOMES_DB` — outcome store location

## Local development

```bash
./start_app.sh          # starts Flask (5003) + sentiment (8003) + Vite (5173)
# OR
./dev.sh                # alternative dev script
```

### Tests
```bash
.venv/bin/python -m pytest -q backend/tests    # ~52 pass, 65 legacy skipped
cd frontend && npm run verify                  # 26 frontend tests
```

### Pre-commit hooks
- `black` (Python formatting) — auto-fixes, re-stage and retry
- `trailing-whitespace`, `end-of-file-fixer` — same pattern
- `detect-secrets` — use `# pragma: allowlist secret` for test fixtures
- `eslint` — **BROKEN** (ESLint 10 needs flat config, repo has none). Use `SKIP=eslint git commit` for all commits.

### Runtime gotcha: `cdp-sdk` must be installed in the interpreter the server actually runs (2026-07-22)

**Symptom:** `/api/portfolio` and `/api/portfolio/intel` return 503
`"Coinbase authentication support is not installed on this server."`
(`PortfolioDependencyMissing`, raised in `portfolio_mode.CoinbaseAdvancedTradeClient._jwt`).

**Cause:** the JWT signer does a lazy `from cdp.auth.utils.jwt import JwtOptions, generate_jwt`.
`cdp-sdk>=1.28,<2` is in `requirements.txt`, but on 2026-07-22 the running Flask
process was launched with **system Python 3.13** (`/Library/Frameworks/Python.framework/...`),
not the project `.venv` (3.12) — and neither interpreter had `cdp-sdk` installed. Result:
owner is authenticated, keys are loaded, but every Coinbase call fails at import.

**Fix (no restart needed):** the import is lazy, so installing into the *running*
interpreter is picked up on the next request without losing in-memory keys:
`<that-interpreter>/python3 -m pip install 'cdp-sdk>=1.28,<2'`.
Cleaner long-term: install `requirements.txt` into the `.venv` and launch the server
from it (`start_app.sh`) so the interpreter is deterministic.

**Watch out:** `cdp-sdk` pulls heavy deps (web3, solana, eth-*) and bumps `pydantic`
to 2.13.x, which conflicts with `gradio` (`<2.12`). Installing into a **venv** (not the
global framework Python) avoids polluting other tools; pin `pydantic` if gradio is needed.

## Dependencies

Python: Flask 3.1, flask-cors, flask-socketio, gunicorn, requests, websocket-client, cdp-sdk, FastAPI, uvicorn, sentry-sdk, numpy, pandas, feedparser, vaderSentiment, transformers, torch, PyYAML, beautifulsoup4, redis (Phase 3 cache, not active)

Frontend: React, Vite, standard JS toolchain

## Git branch state

All feature work is merged to `main`. Legacy branches exist but are stale:
- `codex/event-evolution` — merged to main
- `codex/portfolio-mode` — merged to main
- `codex/ai-ml-next-step-plan` — older planning branch
- `collab/claude-codex-coin-pressure-20260714` — earlier pressure work

## Session 2026-07-22 (part 2): three Portfolio-card threads shipped

All three are code-complete + unit-tested (backend 150 pass, frontend 48 pass); **not yet live-verified in a browser** (intel endpoint needs the owner-auth + CDP chain up). Nothing pushed.

1. **Confidence tiers** — the binary "not enough proof" gates are gone. `describeEvidenceTier(sampleSize)` in `portfolioSignals.js` grades comparable-outcome history into a ladder: None → Emerging (1–9, rate not quoted) → Building (10–29) → Solid (30–99) → Strong (100+). Used on the intel history line, the "Historical plan" cell, the plan-lock banner, and the page-footer calibration section (graded on `outcome_db_size`). Thresholds live in `EVIDENCE_TIERS` — tune there.
2. **Cost-basis entry** — unlocks P&L on partial/unavailable holdings. Storage: `manual_cost_basis` table + `set/get/delete_manual_cost_basis()` in `watchlist.py`. Overlay: `portfolio_mode.apply_manual_cost_basis()` (pure) blends known fills + manual avg for the unknown qty (status→`blended`) or defines the whole position (status→`manual`); **`complete` fills are never overwritten**; recomputes summary P&L + coverage. Owner-gated write routes `POST/DELETE /api/portfolio/cost-basis`. UI: `CostBasisEntry` inline form on each partial/unavailable card. Overlay is applied in the intel route before enrich.
3. **Descriptive levels (targets/protection, not-yet-outcome-validated)** — `position_levels.compute_levels()` (pure) derives swing support/resistance, an ATR(14) band, range position, volatility, 1h momentum, and volume trend from public Coinbase candles (`_fetch_coinbase_candles`, no auth). Route helper `_gather_levels_for_symbols()` caches raw candles per product (TTL `MW_LEVELS_CANDLE_TTL_S`=300s, 1h granularity ×50), fetches on demand with bounded concurrency (6 workers), capped `MW_LEVELS_FETCH_PER_REQUEST`=30/request so a big portfolio warms progressively. Attached as `holding["levels"]`; enriches the descriptive read with a range phrase. UI: `HoldingLevels` block with an S↔R track + marker, labeled "not yet outcome-validated", replacing the old hard plan-lock.

New tests: `test_manual_cost_basis.py` (8), `test_position_levels.py` (9), +4 in `test_position_intel.py`, +cost-basis/levels/tier cases in the frontend suite.

## Recommended next actions (priority order)

1. **Build the outcome scorecard UI** — 29K+ graded signals in SQLite, surface accuracy stats per signal type so Tom can see which alerts are actually predictive
2. **~~Wire position intelligence into the Portfolio UI~~ — DONE (2026-07-22)** — `PortfolioModePage` now fetches `/api/portfolio/intel` (progressive enhancement: falls back to `/api/portfolio` on 403/503), renders posture chip + board momentum + historical follow-through per holding, context rows under open orders, and a signal-coverage chip. Live-verified against real data (81 holdings, e.g. ARX "Pressure adverse · 78"). ~~NEXT: raise coverage~~ — **DONE (2026-07-22)**: `position_intel._descriptive_read()` now derives a plain-language 24h read (bands: <2% "Quiet today", 2–8% "Up/Down today", >8% "Up/Down big today") from `price_change_24h_pct` for any held symbol without a live Event Evolution signal, so all 81 cards show content. Reads are marked `read_source="descriptive"` and rendered with a dashed "24h price read" tag so they're visibly distinct from real signals. **Signal coverage stat stays pure** (counts only `read_source=="signal"`, ~9/81); a separate `read_coverage_pct` (~100%) is shown alongside. 8 new backend tests + 1 frontend test. NOTE: not yet live-verified in a running browser — the intel endpoint needs the owner-auth + CDP chain up; logic and render are unit-test-verified.
3. **Add v2 API cost basis fallback** — CDP keys may support `/v2/accounts/{id}/transactions` for buy history on coins without Advanced Trade fills (most of Tom's 81 holdings show "partial cost basis")
4. **Set up Telegram bot** for notification delivery (simplest channel to activate)
5. **Add per-coin outcome history** to `history_for()` so accuracy can be assessed per-asset
6. **Build feedback loop** — use accumulated outcome data to auto-tune notification thresholds
