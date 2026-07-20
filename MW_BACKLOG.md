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

### P1.5 Indicator legend and Coin Pressure chart controls

Status: Done

- The board exposes one expandable control named `Legend` that explains row cues, recent-context markers, persistence, rank movement, and row actions.
- The small blue recent-context marker and small purple persistence dot are named explicitly.
- Cue definitions disclose their exact thresholds and source layer; board fallbacks now match the canonical alert engine.
- Moonwalking uses a white moon mark, aggregate volume uses a whale, and Heating uses a distinct heat mark.
- The legend closes on outside click or Escape, and all three board headings own their correctly colored underline.
- Coin Pressure chart-source controls use the popup's dark glass, purple, and cyan design language instead of browser-default buttons.
- The empty 1-hour price banner explains its real-baseline warm-up instead of looking like a failed data request.

Verification: frontend build and test suite.

### P2.1 Deploy the current one-box build

Status: Open

Scope: deploy `deploy/homeserver/` to the selected Oracle ARM VM, configure Tailscale and the persistent data directory, then verify login and watchlist sync from two devices.

### P2.2 Add real coin-specific social providers

Status: Open

Scope: implement provider modules for approved Reddit/RSS or other real sources, with rate limits, provenance, TTLs, and explicit unavailable states. Do not add a provider merely to fill empty UI sections.

### P2.3 Personal Coinbase integration

Status: Done

- Added authenticated, configured-owner-only `/api/portfolio` access.
- Coinbase CDP credentials stay server-side and are documented for encrypted Railway variables.
- Stage 1 checks key permissions first and refuses keys with Trade or Transfer enabled.
- Added balances, held funds, current valuation, allocation, open-order visibility, and weighted Advanced Trade fill cost basis.
- Transferred-in or history-uncovered quantity is marked partial or unavailable instead of receiving an invented acquisition price.
- Replaced the member portfolio placeholder with a private cockpit that combines portfolio truth with the existing live-strength feed.
- Historical probabilities, target ranges, and protection levels remain explicitly unavailable until comparable evidence is adequate.
- No order, cancel, transfer, or withdrawal route was added.

Verification: all 92 runnable backend tests passed (65 provider-dependent tests skipped), all 35 frontend tests passed, the production frontend build passed, Python compilation passed, and route inspection confirmed that `/api/portfolio` exposes GET only.

### P2.4 Persist portfolio and settings

Status: Open

Scope: replace product-shell seeded state with the chosen local/account-backed persistence model after deployment is stable.

### P2.5 Calibrate indicator thresholds

Status: Open

Scope: implement `docs/SIGNAL_SYSTEM_V1_PROPOSAL.md`: preserve v0 as a versioned baseline, build full-universe relative returns and quote-volume history, run a shadow v1 engine, measure forward outcomes, then release evidence-based thresholds instead of silently tuning them by feel.

### P1.6 Alert and volume signal audit

Status: Done

- Confirmed frontend price fallbacks match the executable v0 backend thresholds.
- Measured live and retained alert frequency and established that detector telemetry is too noisy for direct notifications.
- Audited the candle cache, SQLite volume pipeline, active/recent alert contract, frontend unread behavior, and current external sentiment coverage.
- Documented polling-time window errors, partial-universe breadth, raw-unit volume gates, limited historical retention, and proxy social-field risks.
- Produced a versioned relative-signal, volume-history, confidence, and delivery proposal.
- Added Event Evolution: raw detector hits remain available as `Pulse`, while related per-symbol hits become evolving `Signals` with Building, Breakout, Moonwalking, and Reversal Risk states.
- Added `The Read`, a deterministic conditional interpretation on every evolving Signal. It summarizes whether the evidence favors continuation, remains early, conflicts, or shows reversal/downside risk without producing buy/sell instructions or invented historical statistics.
- Corrected mislabeled poll-count windows to wall-clock minute samples, populated full-universe returns before breadth, normalized volume gates to quote USD, and made per-alert expiry canonical.
- Extended raw minute-volume retention to 48 hours and added 90-day hourly quote-volume rollups.
- Added a high-confidence `notify` slice with per-symbol cooldown, a six-per-hour global budget, transition dedupe, opt-in browser notifications, and configurable email, Telegram, and Discord delivery.
- Added a persistent local-service runner so leaving the launching terminal does not stop the local app.
- Added live Coinbase context to each grouped Signal: full-market relative movement, sampled aggressive spot flow, and bid/ask spread risk. Context is capped at two layman-friendly tags and cannot increase notification volume.
- Added a durable forward-outcome recorder for every published signal transition, including 5/15/30/60-minute returns, target-before-adverse grading, and measured comparable-event history after a 20-event minimum.
- Added truthful provider-readiness rows for CoinGlass derivatives, Arkham labeled on-chain flows, and CoinMarketCal catalysts; they remain `not_configured` until licensed credentials and adapters are supplied.

Verification: 65 backend tests passed (65 provider-dependent tests skipped), 28 frontend tests passed, production frontend build passed, live Signals/Pulse switching passed, and the browser console remained clean.
