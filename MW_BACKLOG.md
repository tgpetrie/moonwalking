# Moonwalkings Living Backlog

Rules live in `MW_SPEC.md`. This file records durable work status.

Status keys: Open, In progress, Done, Blocked.

## In progress - instant radar, 2026-10-30

- Executable prospective forward/onset label contract and synthetic tests
  are implemented on `codex/instant-radar-20261028`; see
  `docs/research/INSTANT_TARGET_LABELS_20261029.md`.
- First audit campaign hour completed with REST-reconciled sampled coverage;
  thin-product side evidence is insufficient, so the overall gate is false.
- Both source-based Gemini responses have been reproduced/triaged. An opt-in
  v2 draft adds forward-window coverage and named timing references, and
  adapts Claude's baseline cutoff. V1 stays the default; 130 tests pass. Read
  `docs/research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md`.
- Claude's independent v2 code review completed at `10b0f96`; Codex accepted
  its catalog/version fix through `92fb51d`. 316 targeted checks pass. Read
  `docs/research/INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md`.
- Gemini v2 design response is received, source-hash checked and reconciled in
  `docs/research/INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md`. Whole-window and
  forward-peak fractions stay separate; cutoffs remain causal; explicit null
  reasons are proposed. Synthetic cases reject using broad event association
  to erase failed fixed-horizon predictions. Study freeze/fitting stay off.
- Additive versioned diagnostics plus offline sparse recorder and causal
  baseline builder are implemented at `8211262`; 346 targeted checks pass,
  including 30 new cases. Target evaluator/contracts remain unchanged.
  See `docs/research/INSTANT_OFFLINE_PIPELINE_20261030.md`.
- Independent offline review `f2cc436` is accepted through `ab95159`, with the
  last-known-monotonic clock fix and producer/reason improvements. 356 targeted
  checks pass. See `docs/research/INSTANT_OFFLINE_REVIEW_ACCEPTANCE_20261030.md`.
- Next: bounded replay of preserved feed data, verify real-data/health and immutable
  target-sample adapters, freeze association/exposure and the remaining
  study rules, resolve remaining audit evidence,
  then freeze recorder/features/readiness before prospective collection and
  fitting. Historical validation remains locked. Live scoring is unchanged.

## Done and verified on 2026-09-02

### P3.1 Local AI credit-saving helper

Status: Done

- Added a local-only helper for grounded project questions, tracked-diff review,
  and log triage through Ollama.
- Added a double-click Windows launcher for a responsive Moonwalking-styled browser
  interface with Project Chat, Change Review, and Log Triage workspaces.
- The helper supplies real project sources directly, blocks common credential
  files, and instructs the model to report missing evidence instead of inventing it.
- Documented which repetitive tasks belong on the local model and which risky or
  complex work should remain with hosted Codex or Claude models.

Verification: Python compilation, grounded project-question check, synthetic log
triage check, GUI-to-Ollama request, desktop and mobile browser checks with no
horizontal overflow or console errors, and confirmation that `qwen3.5:9b` ran
through Ollama on the GPU.

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

### P2.7 Design empirical range tails

Status: Open

Scope: If the product later needs `near_support` / `near_resistance` to mean empirical per-coin tail conditions, first declare the historical window, minimum observation/sample policy, completed-history-only computation, persistence and cold-start behavior, and explicit insufficient-history fallback. Do not substitute global percentiles or hidden in-memory state.

### P2.8 Design historical relative-volume ranking

Status: Open

Scope: If `volume_ratio` should ever express a rank rather than a fixed multiplier, first declare the exact historical ratio definition, the denominator/lookback window, the minimum number of comparable observations, the completed-candle policy, the extended-fetch or persistence policy, cold-start behavior, and the insufficient-history fallback. Historical observations must use strictly prior candles so no denominator contains future volume. Do not rank the current fetch window in place, and do not substitute a global percentile.

### P2.6 Portfolio Risk Board (sell-side levels, applied across real holdings)

Status: Open

Problem: `sell_side_intelligence.py` / `position_levels.py` and the
`/api/risk-levels/<product_id>` route already compute real, explainable
support/resistance, an ATR-based stop-limit, a resistance-based profit
target, and a scored top-risk signal per coin, and `RiskLevelsChart.jsx`
already renders it as an interactive candlestick chart with a click-to-explain
level list. Single-coin levels are already wired into the Coin Pressure popup,
including its dedicated Risk Levels tab. The combined branch includes the
completed-candle chart. There is no portfolio-wide view that walks a user's
actual holdings and shows this for each of them.

Scope:

- New backend route `GET /api/risk-levels/portfolio` that reuses
  `build_sell_plan` per symbol but batches the work: pull the coin list from
  the authenticated `/api/portfolio` holdings (P2.3) — falling back to the
  watchlist for guests/no-portfolio sessions — share one candle fetch per
  symbol across the batch instead of one request per card, and return an
  array of plans plus per-symbol `available: false` with a reason for any
  coin that does not have enough candle history (never invent a level).
- New `PortfolioRiskBoard.jsx` view: a card grid, one card per held coin,
  sorted with `top_signal.status === "high"` ("Protect now") first, then
  "watch", then "clear". Each card is compact, not a full chart:
  - Symbol, current price, and position size/value pulled from the same
    portfolio holdings data already surfacing in the Coinbase cockpit (P2.3),
    so risk is shown next to what's actually at stake, not just price.
  - A single-row horizontal "range position" gauge using the `range_zone`
    field `position_levels.py` already computes (`near_support` ...
    `near_resistance`) — a tick on a support-to-resistance bar, so the visual
    read is instant without needing the full candlestick chart per card.
  - The top-signal label/tone as a colored chip (reuse the existing
    tone vocabulary: negative/caution/neutral) and its single clearest
    reason string.
  - Distance to stop and distance to resistance as plain-language deltas
    ("2.1% above stop", "4.8% below resistance"), not just raw prices.
  - Click/tap expands the card in place into the existing full
    `RiskLevelsChart` for that symbol (reuse the component as-is; do not
    fork it) rather than navigating away, so scanning the board stays fast.
- A portfolio-summary strip above the grid: counts by status ("2 protect now
  · 3 watch · 6 clear") and, since real position sizing is already available
  from P2.3, an aggregate "capital at risk to stop" figure (sum of
  `quantity * max(current_price - stop_trigger_price, 0)` across held coins
  with an available plan, equivalently current position value times the
  stop-distance fraction). Label it as the price distance to the trigger,
  not a guaranteed loss limit: stop-limit execution is not guaranteed.
  Watchlist-only coins without actual position sizes do not contribute to
  this dollar total. Already-breached triggers are flagged separately.
  Coins with no available plan are counted and named separately, never
  silently dropped from the total.
- Explicit empty/degraded states: no portfolio connected -> fall back to
  watchlist coins with a visible label saying so; a coin with insufficient
  candle history -> a named "not enough history yet" card, never omitted
  and never filled with a guessed level.
- Refresh cadence matches the existing board polling convention already used
  elsewhere (check `LiveStatusBar`/board refresh interval) rather than
  inventing a new one; a manual refresh control follows the existing
  `ManualRefreshButton` pattern.

Explicitly out of scope: no order placement, no push notification changes,
no new risk math — this wires up what P2.x already built rather than
computing anything new. If the batched endpoint reveals the per-symbol
candle-fetch cost is too high for a full portfolio on every poll, caching
that fetch is in scope; changing the underlying stop/target math is not.

Suggested build order (own branch/worktree per AGENTS.md/CLAUDE.md):
1. Backend: `/api/risk-levels/portfolio` batching + shared candle cache,
   with `test_risk_levels_route.py`-style coverage for the batch shape,
   the no-portfolio fallback, and the insufficient-history case.
2. Frontend: `PortfolioRiskBoard.jsx` + a compact `RiskLevelCard.jsx`,
   wired to the new batch route, with the existing `RiskLevelsChart`
   reused for the expanded state. Component tests follow the existing
   `ScorecardPage.test.jsx` / `WatchlistPanel.test.jsx` style.
3. Add the board to navigation/routing where the Coinbase cockpit (P2.3)
   or Watchlist is currently reached, so it's actually discoverable.

Verification (match the bar set by prior P-items): backend route + batch
tests passing, frontend component tests passing, full test suite green,
manual pass confirming the board reflects real portfolio holdings (or the
labeled watchlist fallback), a coin with thin history shows its named
unavailable state instead of a fabricated level, and the aggregate
capital-at-risk figure is spot-checked by hand against the per-card numbers.

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

### P2.7 Entry-side (buy-side) read on the Risk Board

Status: Done

Problem: the risk levels work answers only sell-side questions - where the
stop belongs, where support and resistance sit, whether top risk is elevated.
A holder or a buyer also needs the entry-side read: is this building strength,
is it breaking out on real volume, is it reclaiming support after weakness, is
it too extended to chase, where is invalidation if entering, and is the
reward acceptable from here. None of that existed.

Added:

- `backend/entry_signal_intelligence.py`, a pure module beside
  `sell_side_intelligence.py`. `build_entry_read` classifies one coin as
  `Breakout watch`, `Support reclaim`, `Pullback watch`, `Too extended`,
  `Invalidated - wait`, or `No entry signal`, and returns an entry zone, an
  invalidation price and distance, a reward-to-risk reference against the
  measured resistance, and reason strings that each name a real field.
- Every threshold is reused from a module that already ships rather than
  hand-tuned here: the `range_position_pct` 15/85 band edges from
  `position_levels`, `volume_ratio >= 1.5` from `sell_side_intelligence`,
  live-signal `confidence >= 78` from `alert_events.derive_event_read`, and
  the `risk_pct > 6` wide-risk band from `sell_side_intelligence`. The
  declared thresholds are echoed in `methodology.thresholds` so the UI can
  disclose them.
- No entry price is invented. The support/reclaim zone and the invalidation
  price are taken from the matching `build_sell_plan` output, so the
  protection read and the entry read on one card can never name two different
  levels. When price is above the measured range the read says there is no
  overhead reference instead of extrapolating a target.
- A reversal or fading warning, a down signal direction, or price at or below
  the structural support routes to `Invalidated - wait` with an evidence score
  of zero, ahead of every constructive branch.
- `outcome_validated`, `history_available` and `order_placement` are all
  false, and no probability is quoted, because comparable entry outcomes have
  not been measured yet.
- `portfolio_risk.build_risk_board` attaches the entry read to every row off
  the same quote and the same levels, adds `entry_status` per row and
  `summary.entry_counts`, and leaves protection-first row ordering unchanged.
- `GET /api/risk-levels/<product_id>` returns the entry read alongside the
  plan.
- `PortfolioRiskBoard.jsx` renders two labeled reads per card - Protection and
  Entry - with a second tone chip, the entry zone, the invalidation distance,
  the reward-to-risk reference, and the declared-cue evidence score, plus an
  entry summary strip. A row without an entry read says so instead of
  implying a clear entry.

Two corrections came out of the live pass and are included above: a
mid-range coin whose reward no longer covers its risk now reads `Poor reward
from here` rather than `Too extended`, which was inaccurate for a coin at 52%
of its range, and the reason that decided the label is now always stated
first, because the collapsed card shows only that one.

Verification run: the backend suite passes at 569 tests, including the 13
existing Portfolio Risk Board route tests and 17 new entry tests. The four new
frontend entry tests and the five existing Portfolio Risk Board tests pass.
The Flask app was started against live Coinbase data and both
`/api/risk-levels/BTC` and `/api/risk-levels/portfolio` were exercised over a
17-coin watchlist. Real data produced `Support reclaim` (AAVE, bottom 15% of
range), `Invalidated - wait` (ICP, live reversal warning, ahead of its
top-of-range position), `Too extended`, `Poor reward from here`, `No entry
signal`, and named unavailable states, and the entry invalidation price
matched the protection plan's invalidation price on every row.

Caveat on that run: it was executed in a Linux container against the same
commit, not on the Windows checkout, because the desktop shell was unavailable
this session. Three sentiment-service test files were excluded there for
missing optional subpackages unrelated to this work.

Windows verification: the full backend suite passed with local coverage addopts
disabled because this checkout's Windows environment is missing `pytest-cov`
(`573 passed, 65 skipped`). The production frontend build and full frontend
test suite passed (`39 files, 491 tests`). `npm run guardrails` passed. Flask
and Vite were started locally on ports 5003 and 5173, `/api/risk-levels/BTC`
and `/api/risk-levels/portfolio?symbols=BTC,ETH,SOL` returned live Coinbase
plans with entry reads, and a headless browser render of `/risk-board` against
that live payload showed three cards, entry text, stop/invalidation fields, and
an expanded chart with no console errors.

### P2.8 Watchlist market workspace

Status: In progress

The authenticated watchlist now requests quotes for every symbol in the
selected list, so coverage is not limited to the board worker's rotating
market sample. Cards show real Coinbase prices, measured 1m/3m/1h/24h changes,
and explicit unavailable or stale states. Per-list preferences include card,
compact, and list views, performance sorting, optional score and notes, and
copying selected symbols into a smaller list. Crypto logos use a public asset
image with a symbol fallback; stock logos are supported but stock quote data
remains unavailable until a stock feed is connected.

Verification: 10 targeted backend tests and 4 watchlist frontend tests pass;
the full frontend suite passes (`40 files, 495 tests`). A live authenticated
browser pass returned `81/81 matched` quotes for the current list.
