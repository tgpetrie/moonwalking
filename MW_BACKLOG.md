# Moonwalkings Living Backlog

Rules live in `MW_SPEC.md`. This file records durable work status.

Status keys: Open, In progress, Done, Blocked.

## Done and verified on 2026-07-13

### P0.1 One-board layout and control stability

Status: Done

- The public board uses one continuous wrapper with aligned rails and no desktop or mobile horizontal overflow.
- Watchlist and Intelligence Log remain inside the canonical board flow.
- Whole-row translation was removed so star, info, and trade actions have stable click targets; data-cell motion remains.

Verification: desktop and mobile browser passes, normal Playwright clicks, overflow measurements.

### P0.2 Alerts system

Status: Done

- Alerts Center renders the real canonical alert stream and taxonomy.
- Opening the center marks the current stream read.
- The floating control displays an unread count and clears it after opening.
- Active and Recent views, close behavior, market pressure, and alert details were browser-tested.
- Intelligence Log consumes the same underlying alert objects.

Verification: live alert arrival, unread/read transition, panel tabs, close behavior, console check.

### P0.3 3m movers reliability

Status: Done

- 3m gainers and losers use real SQLite timestamp baselines.
- Last-good snapshots survive partial price fetches.
- Both sides populated during a multi-minute live run and did not collapse during normal refreshes.

Verification: repeated `/data` coverage checks and live browser observation after warmup.

### P1.1 Sentiment truth audit

Status: Done

- Removed random, MD5, mock-news, and neutral-value sentiment fallbacks.
- Real sources expose provenance and `live`, `stale`, or `offline` state; the active source catalog lists only providers that contributed data.
- Market-wide sentiment is labeled market-wide and never presented as coin-specific.
- Missing social/history/topics/divergence data remains null or empty.
- Local coin pressure uses real tape baselines; external coin context uses `/api/coin-intel`.

Verification: backend truth tests, endpoint inspection, coin-popup browser pass, zero popup console errors.

### P1.2 Watchlist and auth truth audit

Status: Done

- Guest session discovery returns a normal unauthenticated response instead of a console-producing 401.
- Guest add/remove works with a fixed added-price baseline and no duplicates.
- Guest storage uses the canonical `mw_watchlist` key and `product_id` schema, with a tested migration from the old key.
- Authenticated SQLite persistence is covered by integration tests.
- Watchlist controls remain clickable while the board is moving.

Verification: browser add/remove, local-storage inspection, backend persistence tests, frontend context tests.

### P1.3 Runtime architecture repair

Status: Done

- Canonical ports are Vite 5173, Flask 5003, and sentiment 8003.
- Startup creates one price worker and one volume worker.
- The complete Flask route table registers before script startup.
- The legacy in-process sentiment poller is disabled by default and cannot start from a request.
- Legacy fabricated compatibility endpoints now retire explicitly or proxy canonical real data.

Verification: clean restart logs, route regression tests, health/smoke checks.

### P1.4 Truthful 1h banners

Status: Done

- 1h price movement uses a real SQLite 1h baseline.
- 1h volume movement uses real candle or SQLite baselines.
- 24h price movement is no longer converted into a fake 1h value.
- Price movement is no longer substituted for missing volume movement.
- Component and snapshot compatibility endpoints reuse the canonical background banner snapshots.
- Warmup returns empty rows with explicit warming state.

Verification: regression tests and live baseline inspection.

## Open deployment and expansion work

### P2.1 Deploy the current one-box build

Status: Open

Scope: deploy `deploy/homeserver/` to the selected Oracle ARM VM, configure Tailscale and the persistent data directory, then verify login and watchlist sync from two devices.

### P2.2 Add real coin-specific social providers

Status: Open

Scope: implement provider modules for approved Reddit/RSS or other real sources, with rate limits, provenance, TTLs, and explicit unavailable states. Do not add a provider merely to fill empty UI sections.

### P2.3 Personal Coinbase integration

Status: Open

Scope: design a decision record for read-only credentials, backend-only secret storage, portfolio contracts, and revocation before implementation.

### P2.4 Persist portfolio and settings

Status: Open

Scope: replace product-shell seeded state with the chosen local/account-backed persistence model after deployment is stable.
