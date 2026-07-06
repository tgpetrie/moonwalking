# HANDOFF

## Snapshot

- Date: 2026-07-06
- Current branch: `codex/ai-ml-next-step-plan` (pushed to origin; sits ahead of `main`)
- Repo purpose: BHABIT Moonwalking is a React + Vite frontend and Flask backend for a live crypto tracking dashboard with alerts, movers, watchlist/insights tooling, and a product-shell pivot toward account-backed, cross-device watchlists.

## Product direction (four tracks, in priority order)

1. Cross-device watchlist — code complete, deploy pending (see below).
2. Near-live gainers/losers — replace REST polling with the Coinbase public
   WebSocket feed (`wss://ws-feed.exchange.coinbase.com`, ticker channel) so
   backend 1m/3m windows update tick-by-tick. Not started.
3. Real sentiment tracking — only Fear & Greed and CoinGecko fetchers are real
   (`backend/sentiment_data_sources.py`). The tier configs in
   `backend/sentiment/sources/*.json` describe Reddit/RSS/Telegram/Twitter
   sources but `backend/sentiment/providers/` has no implementations yet.
   Next win: Reddit public JSON + RSS/VADER providers honoring the
   truth-state rules in `docs/developer/SENTIMENT_ONE_BOARD.md`; remove the
   fabricated MD5 fallback documented in
   `docs/developer/SENTIMENT_ARCHITECTURE.md`. Not started.
4. Personal Coinbase integration — read-only API key, backend-only storage,
   `/api/portfolio` summary endpoint. Deliberately last; rides on deployed
   auth. Not started.

## Important recent work (July 6, 2026)

### Cross-device watchlist backend + wiring (DONE)

- Commit `c46e6ceb` — `feat(watchlist): SQLite-backed accounts with auth and guest sync`
  - `backend/watchlist.py`: user signup/login with hashed passwords, session
    handling, SQLite persistence (`data/watchlists.sqlite`), guest-watchlist
    sync into the authenticated account.
  - `frontend/src/mvp/MvpApp.jsx`: session restore (`/api/auth/session`),
    login/signup/logout, full watchlist CRUD against `/api/watchlists*`.
    Routes moved under `/app/*`.
  - `frontend/src/context/WatchlistContext.jsx`: guest-vs-authenticated sync.
  - Tests: `backend/tests/test_watchlist_auth_persistence.py`,
    `frontend/src/context/WatchlistContext.test.jsx`.
- Commit `fcc99ce3` — `feat(auth): production-ready session config`
  - `SECRET_KEY` required in production (boot fails without it).
  - HttpOnly/Secure cookies, SameSite=Lax (prod API traffic is same-origin
    via the Vercel `/api/*` rewrite to Render in `vercel.json`), 30-day
    persistent sessions.
  - CORS explicit-origins branch now sends `supports_credentials`.
  - `WATCHLIST_DB_PATH` env override + Render persistent disk in `render.yaml`.

Remaining gaps in this track:

- NOT DEPLOYED. Render disks need a paid instance; the free-tier alternative
  is migrating watchlist storage to Postgres (Supabase). Until deployed,
  cross-device does not actually work.
- `/app/portfolio` and `/app/settings` state in `MvpApp.jsx` is still seeded
  `useState` only (around line 1494) — watchlists persist, portfolio/settings
  do not.

### Earlier UI/board lane (still matters, do not regress)

- `17c9cbb6` / `7420683d` / `8eab79f5` — row cue hierarchy, SVG cue
  indicators, canonical board CSS.
- `51a96574` — row cue legend (`frontend/src/utils/rowCue.js`), shared
  polling cadence config (`frontend/src/config/cadence.js`), DataContext
  rework.
- `433bf6a1` — 1h volume banner snapshot rebuild fix; sentiment service
  default port moved 8002 → 8003.

## Performance notes

`PERFORMANCE_OPTIMIZATIONS.md` ("one fetch, three clocks") is still the right
mental model, but the tuning knobs changed: cadence now derives from
`frontend/src/config/cadence.js` (`VITE_FAST_1M_MS`, `VITE_BACKOFF_1M_MS`,
`VITE_PUBLISH_UI_MS`, `VITE_PUBLISH_3M_MS`, `VITE_PUBLISH_BANNER_MS`,
`VITE_POLL_JITTER_MS`) plus `VITE_ROW_STAGGER_MS` in `DataContext.jsx`.
`VITE_FETCH_MS` no longer exists. The banner-scroll troubleshooting section
in that doc is still accurate.

## Known repo hygiene issues

- The eslint pre-commit hook in `.pre-commit-config.yaml` can never pass
  (ESLint 10 needs a flat config; the repo has no ESLint config or dependency
  at all). Commit frontend work with `SKIP=eslint git commit ...` until the
  hook is fixed or removed.
- Legacy `frontend/src/Dashboard.jsx` hover-emitter code and disabled rabbit
  hover/glow CSS blocks in `frontend/src/index.css` are dead weight; the
  active entry is `App.jsx` → `MvpApp.jsx` (with `DashboardShell` mounted for
  the board view).
- `moonwalking_mobile/` contains only a `.DS_Store`; safe to delete.

## Next exact step

Deploy the watchlist backend so cross-device actually works:

1. Decide storage: Render paid disk (config already in `render.yaml`) OR
   migrate `backend/watchlist.py` storage to Supabase Postgres (free tier).
2. Sync the Render blueprint; confirm `SECRET_KEY` is generated and
   `/api/auth/signup` works on the deployed URL.
3. Verify from two devices: sign up on one, log in on the other, same
   watchlist appears.
4. Then move to track 2 (Coinbase WebSocket live board).

## Resume prompt for another device

Read `HANDOFF.md`. Watchlist auth/persistence is code-complete on branch
`codex/ai-ml-next-step-plan` (commits `c46e6ceb`, `fcc99ce3`) but not
deployed. Pick up at "Next exact step": choose Render disk vs Supabase
Postgres, deploy, verify cross-device login, then start the Coinbase
WebSocket live-board track. Keep the row cue and board CSS lanes intact.
