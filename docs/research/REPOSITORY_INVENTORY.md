# Deliverable 1: BHABIT / Moonwalking repository inventory

Written 2026-10-24 on branch `claude/data-source-plan` (docs only; based on
`claude/scoring-research`, which sits on `claude/retention-hotfix`, i.e. production's
release `6235e2d2` plus the storage-retention fix). Research only: no code changed.

**Method:** everything below comes from reading the tracked files and running
`git ls-files`, `grep` and small scripts. **Not verified:** production environment
variable values and which optional keys are set there; frontend runtime behaviour;
any branch other than the one named above. Items taken from the owner's project memory
notes (not re-verified in this audit) are marked *(memory)*.

---

## 1. Shape of the repository (this tree)

| Area | Tracked files | Notes |
|---|---|---|
| `frontend/` | 308 | React + Vite. 134 files under `src/components` (largest: `SentimentPopupAdvanced.jsx` 2,867 lines, `AlertsTab.jsx` 1,562, `ScorecardPage.jsx` 838, `CodexPanel.jsx` 658, `DashboardShell.jsx` 615), plus `utils` (28), `hooks` (16), `context` (9), `mvp` (6), and two legacy folders (`legacy`, `legacy913`) |
| `backend/` | 158 | 75 top-level Python modules, 54 test files, `fixtures/`, `sentiment/` package |
| `docs/` | 53 | See section 7 |
| `scripts/` | 31 | Smoke, verification, local-run and release helpers |
| `deploy/` | 7 | `railway/` and `homeserver/` (systemd units, `setup.sh`) |
| `.github/workflows/` | 4 | `check-legacy-css`, `detect-secrets`, `smoke`, `validate-ui-rules` |
| Root config | | `Dockerfile` (in `backend/`), `railway.json`, `render.yaml`, `vercel.json`, `wrangler.toml`, `Procfile`, `docker-compose.yml` |
| **Total** | **657** | |

## 2. Runtime architecture

* **Production container** (`backend/production_entrypoint.sh`): starts the FastAPI
  sentiment service (`python -m backend.sentiment_api`, bound to `127.0.0.1:8003`) and
  then `gunicorn app:app` for the Flask application, with all SQLite files on a mounted
  volume (`/var/lib/moonwalking`, or `RAILWAY_VOLUME_MOUNT_PATH`).
* **Hosting:** Railway project `bhabit-mooners` behind Cloudflare, domain `bhabit.net`
  (per `HANDOFF.md`). Production was last deployed from the command line from
  commit `6235e2d2`, not from `main`.
* **Local development:** Flask `5003`, Vite `5173`, sentiment `8003`. The always-on
  local collector runs as a scheduled task on port 5003 *(memory)*.
* **Flask** (`backend/app.py`, 15,113 lines) hosts the price/volume workers, the alert
  pipeline, outcome grading, portfolio endpoints, watchlist/auth and the proxy to the
  sentiment service. It is the single largest risk for maintainability.

## 3. Data stores (SQLite)

| File | Owner module | Contents | Notes |
|---|---|---|---|
| `signal_outcomes.sqlite` | `signal_outcomes.py`, `board_outcomes.py` | `signal_outcomes`, `board_outcomes_v2` (and a legacy `board_outcomes`), heartbeat | Largest store (about 2.4 GB on 2026-10-18); `feature_snapshot_json` was about 1.1 GB of it |
| `control_dry_run.sqlite` | `control_dry_run.py` | Matched-peer feasibility observations | Had no pruning (about 2.3 GB, 6.7M rows); moved to a fresh file on production on 2026-10-18; retention is on `claude/storage-retention` |
| `price_snapshots.sqlite` | `price_db.py` | Price tape | 24-hour retention |
| `volume_1h.sqlite` | `volume_1h_store.py`, `volume_1h_compute.py` | Minute and hourly volume | Rolls minute closes, not native OHLC (unsuitable for research replay) |
| `sell_plan_outcomes.sqlite` | `sell_plan_outcomes.py` | Forward outcomes of generated sell plans | Tiny: records only when a plan is opened |
| `watchlists.sqlite` | `watchlist.py` | Accounts, sessions, watchlists, OAuth token columns | **Sensitive** (password hashes, tokens): never back up into analysis folders |
| `candle_archive.sqlite` | `candle_archive.py` (on `claude/data-integrity`) | Raw Coinbase candles | **Local PC only, outside the repo runtime.** 3.04M hourly candles for 407 products, Oct 2025 to Oct 2026, plus 5.9M one-minute candles for missed periods |

## 4. Backend modules by function

| Function | Modules (lines) |
|---|---|
| **Price and volume pipeline** | `app.py` (15,113), `price_fetch` (334), `price_db` (299), `coinbase_ws` (366), `volume_1h_store` (276), `volume_1h_compute`, `volume_1h_candles`, `cache`, `utils_rate_limiter` (495) |
| **Alerts and signals** | `alerts_engine` (2,780, "Coinbase-only" canonical engine), `alert_events` (694, event evolution, confidence, "The Read"), `alert_rules` (979), `alert_rules_api` (271), `alert_runner` (312), `alert_evaluator` (468), `alert_delivery` (274: SMTP, Telegram, Discord), `interpretation_engine` (941), `moonwalking_notifications` (759), `moonwalking_alert_system`, `moonwalking_api` (718) |
| **Scoring and context** | `live_ranking` (434, `live-strength-v1`), `signal_context` (175), `chart_reader` (491), `technical_analysis` (240), `insights` |
| **Levels and risk** | `position_levels` (159), `sell_side_intelligence` (285), `sell_plan_outcomes` (310) |
| **Portfolio** | `portfolio_mode` (1,118: owner-only, view-only Coinbase CDP), `position_intel` (422), `coinbase_oauth` (250), `watchlist` (1,136), `watchlist_insights` |
| **Measurement** | `signal_outcomes` (878), `board_outcomes` (782), `control_dry_run` (825), `storage_retention` |
| **Sentiment and external intelligence** | `sentiment_api` (1,431, FastAPI), `sentiment_aggregator` (1,882), `sentiment_orchestrator` (533), `coin_intel_external` (1,550), `derivatives_positioning`, `intelligence_api` (211), `data_aggregator` (658) |
| **Legacy social handlers (dormant)** | `reddit_handler`, `telegram_handler`, `stocktwits_handler`, `rss_handler`, `chinese_sources`, `custom_scrapers`, `social_apis_handler`, `social_sentiment`, `sentiment_analyzer` |
| **Legacy, demo or validation** | `cbmo4ers_quick_demo`, `validate_*_script`, `main_runner`, `sentiment_aggregator_unified` and `_enhanced` (shims that re-export `sentiment_aggregator`), `test_*.py` files in the backend root |

## 5. External services called today

| Service | Used for | Where | Access |
|---|---|---|---|
| Coinbase Exchange REST and WebSocket | Prices, tickers, candles, product list | `coinbase_ws`, `price_fetch`, `app.py` | Public |
| Coinbase CDP / OAuth | Owner portfolio (balances, fills, orders) | `portfolio_mode`, `coinbase_oauth` | JWT key (view-only enforced) or OAuth |
| Alternative.me | Fear and Greed (market-wide) | `sentiment_api` | Free |
| CoinGecko | Global market data; coin community and trending | `sentiment_api`, `coin_intel_external` | Free demo or key |
| CoinPaprika | Coin events and timeline | `coin_intel_external` | Free |
| Hyperliquid | Perp funding and open interest (BTC/ETH market-wide; per-coin via `derivatives_positioning`) | `sentiment_api`, `derivatives_positioning` | Keyless |
| Binance, OKX, Bybit | BTC and ETH funding and open interest | `sentiment_api` | Keyless public |
| Coinalyze | BTC and ETH CEX-aggregated funding and open interest | `sentiment_api` | Free key; **inert unless `COINALYZE_API_KEY` is set** |
| LunarCrush | Coin-scoped social metrics | `coin_intel_external` | Key; inert without it |
| CoinGlass, Arkham, CoinMarketCal | Availability flags only ("configured / not configured") | `coin_intel_external` | Keys; no data path found |
| Reddit, Telegram, X/Twitter, StockTwits, Chinese sources, RSS, 4chan, Alpha Vantage, CryptoPanic, Cryptometer | Legacy sentiment pipeline | handlers listed in section 4 | Gated by `MW_ENABLE_EXTERNAL_SENTIMENT` (default off) and keys |

The repo's own `docs/SENTIMENT_SOURCES.md` (reviewed 2026-07-14) lists the **active**
sources as Alternative.me, CoinGecko global, Coinbase Exchange, CoinPaprika events and
CoinGecko coin community. Hyperliquid per-coin positioning was added later (July 2026
research note).

## 6. Configuration surface

About 200 environment variables are read by the backend. Groups (names only):
price universe and fetch tuning (`PRICE_*`, `ONE_MIN_*`, `VOLUME_1H_*`); alert and
breadth thresholds (`ALERT_*`, `BREADTH_*`, `PUMP_*`); measurement
(`MW_SIGNAL_OUTCOMES_DB`, `MW_BOARD_*`, `MW_OUTCOME_*`, `MW_CONTROL_DRY_RUN_DB`,
`MW_COLLECTION_METHODOLOGY`); portfolio (`COINBASE_API_KEY_NAME`,
`COINBASE_API_KEY_SECRET`, `COINBASE_PORTFOLIO_OWNER_EMAIL`,
`COINBASE_OAUTH_*`); notification channels (`MW_SMTP_*`, `MW_TELEGRAM_*`,
`MW_DISCORD_*`); optional data keys (`COINALYZE_API_KEY`, `COINGLASS_API_KEY`,
`ARKHAM_API_KEY`, `COINMARKETCAL_API_KEY`, `CRYPTOPANIC_API_KEY`,
`CRYPTOMETER_API_KEY`, `LUNARCRUSH_API_KEY`, `SANTIMENT_API_KEY`,
`ALPHA_VANTAGE_API_KEY`, `COINGECKO_API_KEY`, `REDDIT_*`, `TWITTER_BEARER_TOKEN`,
`TELEGRAM_*`); AI keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`); feature gates
(`MW_ENABLE_EXTERNAL_SENTIMENT`, `MW_ENABLE_LEGACY_INTELLIGENCE`, `USE_REAL_SENTIMENT`).
**Which of these are set in production was not checked.**

## 7. Documentation and tests

* **Docs (53):** `docs/ai/AI_INDEX.md` and `ai/ARCHITECTURE.md` (agent orientation),
  `DATA_PIPELINES.md`, `SENTIMENT_SOURCES.md`, `developer/SENTIMENT_SOURCE_RESEARCH.md`
  (July 2026 free-first source research, partly implemented), `developer/SENTIMENT_SOURCE_SALVAGE_PLAN.md`,
  `SIGNAL_SYSTEM_V1_PROPOSAL.md`, `PORTFOLIO_MODE.md`, `ops/PRODUCTION_VOLUME.md`,
  `research/BHABIT_SCORING_RESEARCH.md`, and this folder's deliverables. Root-level
  `HANDOFF.md`, `MW_BACKLOG.md`, `MW_SPEC.md`, `AGENTS.md`, `CLAUDE.md` govern workflow.
* **Tests:** 54 backend test files. On the production-equivalent tree the suite shows
  534 passed, 65 skipped, 6 failing (a Windows file-encoding issue in scanner-order
  tests that also fails on the untouched release); with the demotion branch and
  `PYTHONUTF8=1`: 561 passed, 65 skipped, 0 failed. Frontend tests were not run in this audit.
* **CI:** four workflows (legacy-CSS guard, secret detection, smoke, UI-rule validation).
  **No workflow runs any backend or frontend tests** (verified by search). The smoke
  workflow on this tree probes Render and Vercel URLs, which production no longer uses
  (`HANDOFF.md` records a Railway-based replacement on another branch).

## 8. Branches and worktrees (purpose inferred from names unless stated)

| Worktree | Branch | Note |
|---|---|---|
| `Moonwalking` | `codex/integrate-production` | Integration line |
| `Moonwalking-Unified` | `codex/unified-20261018` | Codex consolidation target |
| `Moonwalking-RiskBoard` | `codex/portfolio-risk-board` | Portfolio Risk Board and agents layer |
| `Moonwalking-Claude-Design` | `claude/design-system-pass` | UI design system; holds **17 uncommitted files** (12 modified, 5 new Scenario Mode files, last touched 2026-09-23), owner unidentified |
| `Moonwalking-DataIntegrity` | `claude/data-integrity` | Outcome-gap fix, candle archive |
| `Moonwalking-Runtime` | `runtime/collector` | Always-on collector |
| `Moonwalking-Hotfix`, `-Retention` | `claude/retention-hotfix`, `claude/storage-retention` | Storage limits (pushed; hotfix is based on production's release) |
| (this session) | `claude/demote-weak-reads`, `claude/scoring-research`, `claude/data-source-plan` | Demotion and extended outcomes; scoring research; this plan |
| others | `claude/agents-page`, `claude/watchlist-decision-desk`, `claude/local-review`, `codex/macro-chart-20261018`, `claude/render-history-data` | Not inspected |

## 9. Observations that matter for data sourcing

1. **Derivatives are market-wide for BTC and ETH (five venues), and per-coin only via
   Hyperliquid.** No liquidation data is fetched anywhere, despite a code comment
   listing "funding/OI/liquidations" for Coinalyze (only funding and open interest are requested).
2. **No durable history exists for any external input.** Open-interest history is
   in memory for about 24 hours; sentiment history is not stored. Anything not collected
   forward from now cannot be backfilled later, except where a provider serves history.
3. **No listing-history record** exists in the repo, which matters for survivorship.
   A scheduled "PIT watch" task logs Coinbase product status and incidents to
   `pit_context.sqlite` *(memory)*; that file was not inspected.
4. **Two series are deliberately separate:** RNDR and RENDER; the SMA200 for RENDER-USD
   is unavailable until 2027-12 *(memory)*.
5. **Dormant code is a liability and an asset.** Many handlers are present but gated
   off; reviving one is cheaper than starting a new integration, but each needs the
   truthfulness rules in `docs/SENTIMENT_SOURCES.md` (provenance, freshness, no fabricated fallbacks).
6. **Maintainability:** `app.py` is 15,113 lines; the backend root also holds
   demo, validation and test scripts mixed with production modules.
