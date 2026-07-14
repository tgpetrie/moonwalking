# Moonwalking Handoff

## Snapshot

- Date: 2026-07-14
- Branch: `codex/ai-ml-next-step-plan`
- Repository: `/Users/cdmxx/Documents/moonwalkings`
- Product: BHABIT Moonwalking live crypto board plus account-backed product shell.
- Git policy: Tom explicitly requested committing/pushing this change set after verification.

## Current outcome

The local MVP now has one canonical, verified runtime:

- Vite frontend: `127.0.0.1:5173`
- Flask board API: `127.0.0.1:5003`
- FastAPI sentiment service: `127.0.0.1:8003`
- Start command: `./start_app.sh`

The public board, 1m/3m tables, real 1h banners, alerts, coin popup, guest watchlist, account session discovery, login/signup routes, and SQLite-backed authenticated watchlists are wired. The supported production shape remains one Flask worker plus the sentiment service on an Oracle/Tailscale single-box deployment.

## Work completed in the current change set

### Runtime and routing

- Standardized every active local start path on ports 5173/5003/8003.
- Removed duplicate background-worker startup from script mode.
- Moved the script entrypoint below the complete Flask route table. `/api/insights/<symbol>` and the remaining compatibility routes now exist in script mode as they do under imports.
- Prevented request-time code from silently creating a legacy sentiment poller.
- Disabled the unfinished legacy intelligence blueprint by default; `/api/coin-intel` is canonical.
- Guest `/api/auth/session` now returns HTTP 200 with `authenticated: false`.

### Data truth

- Rebuilt the sentiment service as real-source only: Alternative.me plus CoinGecko global market data, with explicit provenance and live/stale/offline state.
- Removed fabricated random sentiment, social metrics, topics, history, divergence, MD5 values, mock headlines, and mock news.
- Market-wide sentiment remains labeled market-wide when a coin opened the panel.
- The source catalog and source counts include only providers that contributed to the current real snapshot.
- Missing external coverage remains null or empty.
- Replaced estimated 1h price movement with actual SQLite timestamp baselines.
- Removed price-as-volume and 24h-as-1h fallbacks. Banners now show real rows or warming state.
- Compatibility banner and volume-snapshot endpoints now reuse the same canonical background snapshots as `/data`.
- Fixed candle product-id normalization so `MORPHO-USD` cannot become `MORPHO-USD-USD`.

### Frontend and interaction

- Preserved motion on data cells while anchoring whole rows, making star/info/trade controls reliably clickable.
- Preserved missing sentiment values as null in the central adapter.
- Removed frontend volume estimates and hardcoded banner samples.
- Guest watchlist add/remove and baseline storage work through the canonical `mw_watchlist`/`product_id` contract; the old browser key migrates without data loss.
- Auth screens link back to the live board and describe server-backed behavior without unsupported cloud claims.
- Alerts Center active/recent flows work; the dock now shows a numeric unread count and opening marks the current stream read.
- The coin popup loads both real local pressure and real external coin context without 404s.
- Coin Pressure now includes a Pulse-tab `Quick Buy Read` that translates the canonical alert engine into operator labels:
  - `BUY WATCH`: supported upside, still prefer pullback/retest.
  - `RECONFIRM`: active momentum but not clean enough for blind chase.
  - `WATCH`: early volume/attention smoke without clean direction.
  - `NO CHASE` / `TRAP RISK` / `PROTECT`: fakeout, divergence, exhaustion, or risk-control families.
  - `AVOID LONG`: active downside pressure.
- The quick-read mapping lives in `frontend/src/components/SentimentPopupAdvanced.jsx` and uses real alert families plus freshness, volume confirmation, breadth, and labeled sentiment/attention context.
- The row legend now defines quick-read labels in addition to streaks, peaks, arrows, and volume warmup.

### Alerts and sentiment documentation

- `docs/user-guides/ALERTS_USE_GUIDE.md` now explains what alerts are trying to tell the operator, the current default thresholds, cooldowns, TTLs, and quick-buy interpretation.
- `docs/alerts_engine_spec.md` now documents the UI quick-read mapping and threshold summary from `backend/alerts_engine.py`.
- `docs/SENTIMENT_SOURCES.md` is the source matrix for active public sources and optional credentialed providers. Reddit/X remain unavailable until official API credentials and compliant ingestion exist.
- `backend/sentiment/sources/tier3.json` catalogs optional credentialed providers such as LunarCrush, Santiment, Messari, Kaito, and The Tie without counting them as active coverage unless credentials are configured.

## Verification completed

- Backend suite passed with 52 tests; 65 legacy/provider tests are intentionally skipped.
- Runtime/banner, sentiment provenance, and active-source catalog regressions are covered.
- Frontend production build and unit suite passed; the current suite contains 26 tests, including canonical watchlist migration.
- Guardrails passed.
- Smoke endpoints passed against the live backend.
- Browser QA covered desktop and mobile layout, board population, alerts, watchlist add/remove, coin popup, login/signup routes, click stability, horizontal overflow, and console errors.
- Clean startup logs showed one price worker, one volume worker, one sentiment service, and no legacy intelligence import failure.

Run the final verification commands after any subsequent edit:

```bash
npm run guardrails
.venv/bin/python -m pytest -q backend/tests
(cd frontend && npm run verify)
bash scripts/smoke_check.sh
bash scripts/smoke_sentiment_proxy.sh BTC
```

## Honest limitations

- Cross-device behavior is code-complete but not proven until the one-box deployment is online and tested from two devices.
- Sentiment has market-wide real sources plus coin-context attention proxies. True coin-specific social sentiment requires a credentialed provider such as LunarCrush, Santiment, Messari, Kaito, or The Tie.
- `/app/portfolio` and `/app/settings` still use seeded in-memory product-shell state.
- Personal Coinbase integration has not been designed or implemented.
- On a fresh database, 1m, 3m, and 1h sections deliberately show warming until their real baseline windows mature. Existing SQLite history shortens this after normal restarts.
- The backend remains a large module. Runtime responsibilities are now explicit, but extracting workers and routes into narrow modules is a future maintainability task, not required for the current one-box MVP.

## Recommended next action

Deploy the current build with `deploy/homeserver/`, verify account login and watchlist sync from two devices over Tailscale, and only then begin personal Coinbase or new sentiment-provider work.
