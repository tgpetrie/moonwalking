# Moonwalkings Master Spec (MW_SPEC)

This document is the single source of truth for ports, data contracts, UI layout rules, alert taxonomy boundaries, watchlist and sentiment truth rules, and repo-wide copy standards.

This file contains RULES only (no tasks).
Tasks live in MW_BACKLOG.md.


## 0) Non-negotiables

0.1 Real data only
- Do not fabricate or smooth by inventing values.
- If data is missing or stale, the UI must say OFFLINE / STALE / UNAVAILABLE and preserve last-good state within defined TTLs.

0.2 Minimal edits only
- Prefer targeted edits to existing CSS/JS.
- Do not refactor component structure or create new components unless explicitly requested.

0.3 No emojis in repo deliverables
- No emojis in docs, README, UI copy intended for release.
- Exception: alerts content may contain emojis (alerts-only), if desired.

0.4 Typography is Raleway everywhere
- All UI typography uses Raleway.
- Do not introduce new fonts.

0.5 Canonical identity
- Canonical asset key is product_id.
- Display symbol is base symbol only (no “-USD” in UI).


## 1) Ports, hosts, and environment (canonical)

1.1 Canonical local-dev ports
- Backend (board API): http://127.0.0.1:5003
- Frontend (Vite): http://127.0.0.1:5173
- Sentiment is served via the same backend base unless explicitly separated by a dedicated service.

1.2 Allowed environment variables (frontend)
- VITE_API_BASE_URL: base URL for the board backend (default must be 127.0.0.1:5003 in local dev)
- VITE_PROXY_TARGET: proxy target for Vite (must match VITE_API_BASE_URL in local dev)
- VITE_SENTIMENT_BASE_URL (or equivalent): must resolve to the same backend base in local dev unless intentionally separate

1.3 Forbidden behavior
- The frontend must not silently “try random ports” in production behavior.
- Any fallback behavior must be explicit, logged in debug mode only, and must not persist a wrong port.

1.4 LocalStorage keys (allowed)
- mw_backend_base (only if it equals the canonical base in local dev)
- mw_last_good_data
- mw_last_good_at
- mw_watchlist
- mw_debug_1m, mw_debug_sentiment, mw_debug_volume (debug toggles only)
- mw_1m_mode (presentation mode only)

1.5 5002 policy
- Port 5002 is legacy and must not be used by the active board or persisted as backend base.
- It may exist only in archived docs or explicit migration notes, not in active start scripts, docker-compose defaults, or frontend runtime defaults.


## 2) Live data and freshness (truth contracts)

2.1 Board data source
- The dashboard’s market data comes from /data on the board backend (:5003).

2.2 Last-good behavior (never vanish)
- If a fetch returns empty arrays or missing required keys, the UI MUST NOT wipe the board.
- Keep last-good snapshot for a bounded TTL:
  - 1m table: keep last-good up to 60s
  - 3m tables: keep last-good up to 120s
  - banners: keep last-good up to 180s
- If TTL expires with no valid refresh:
  - show STALE/OFFLINE state
  - freeze reorder animations
  - keep last visible rows until reconnect or manual refresh

2.3 Single orchestrator rule (no split brains)
- Exactly one context/provider may poll /data and publish updates to the UI.
- No secondary polling loops may mutate the same token arrays.
- Row identity must be stable and keyed by product_id.

2.4 Fetch cadence vs publish cadence
- Fetch cadence can be fast.
- UI publish cadence must prevent strobe:
  - 1m can publish frequently (alive feeling)
  - 3m publishes slower than 1m
  - banners animate continuously in CSS; only items refresh on publish cadence


## 3) Data shape contract (backend to frontend)

3.1 Required top-level arrays (names may vary only if mapped once centrally)
- gainers_1m: array of token rows
- gainers_3m: array of token rows
- losers_3m: array of token rows
- banner_1h_price: array of banner items (1h price change)
- banner_1h_volume: array of banner items (1h volume change)

3.2 Token row minimum fields
- product_id (canonical key)
- symbol (base display symbol)
- price_now (number)
- pct_1m (number or null)
- pct_3m (number or null)
- ts_ms or age_s (timestamp or derived age)

3.3 Banner item minimum fields
- product_id or symbol (prefer product_id)
- symbol (base display symbol)
- currentPrice
- pctChange
- link (Advanced Trade URL) or enough info to build it reliably

3.4 Display symbol rule
- UI must never show “-USD”.
- UI uses display symbol only (BTC, SOL, AMP).
- product_id stays internal and is used for identity and linking.

3.5 Dedupe rule
- Dedupe by product_id at the final step before publishing to UI.
- A product_id must not appear twice in the same table or banner list.


## 4) Layout hierarchy (page structure)

4.1 Visual hierarchy order
1) Top banner: 1-hour price change movers
2) 1-minute gainers table
3) Side-by-side 3-minute gainers and 3-minute losers tables
4) Bottom banner: 1-hour volume change movers
5) Watchlist + Intelligence Log panels (if present in the design)

4.2 One board wrapper rule
- The entire page must sit under one canonical board wrapper/grid system.
- No second board layer, overlay seam, tint split, or “two worlds” effect.


## 5) Table layout contracts

5.1 1-minute gainers table contract (strict)
If there are 4 or fewer tokens available:
- Single column, full width.
- Show up to 4 rows.

If there are more than 4 tokens available:
- Switch to two columns inside the same panel.
- Left column shows ranks 1–4.
- Right column shows ranks 5–8.
- Show More reveals ranks 9–16 (two columns of 8).

Verification tests (must match this contract)
- Count 1, 2, 3, 4: single column full width
- Count 5, 6, 7, 8: two columns, 4 left + up to 4 right
- Show More reveals up to 16 total: 8 left + 8 right

5.2 3-minute tables contract
- Default visible is top 8.
- Show More reveals up to 16.
- Both 3m tables must follow the same cap and reveal behavior.

5.3 Row alignment contract
- Token name and symbol are left-aligned.
- Right cluster is right-aligned:
  - price and percent tight together
  - star/info has slightly more breathing room but remains right-aligned
- Watchlist rows must match the same rails and right edge alignment.


## 6) Banners contract

6.1 Banner behavior
- Both banners scroll continuously.
- Hover may glow/zoom, but scroll must not pause.

6.2 Direction rule
- Top banner scroll direction: one direction
- Bottom banner scroll direction: opposite direction

6.3 Banner content rules
Top banner (price)
- Shows 1-hour price change movers.
- Sorting must be correct.
- If it is “gainers only” by spec, pct must be >= 0 and strictly descending.

Bottom banner (volume)
- Ranks by 1-hour volume percent change (not raw volume).
- Sorting must be correct and explicitly by percent change.


## 7) Alerts system boundaries (board-wide)

7.1 Alerts source of truth
- Alerts UI must render real Moonwalking alerts only (main alert taxonomy).
- Trend/score feeds must not appear anywhere in Alerts UI.

7.2 Alerts placement
- No toast spam or popups covering the board.
- Alerts entry is a floating button with unread count badge only.
- Clicking opens a glass drawer/panel matching the Sentiment panel design language.

7.3 Alerts organization
- Alerts must be organizable by taxonomy category (grouped sections by type).
- Intelligence Log must render the same alert objects in its matrix/list style (not reinvented as new card UI).

7.4 Alert row requirements
- Symbol display (no “-USD”)
- age or timestamp
- severity/type chips
- brief message
- Advanced Trade link


## 8) Watchlist contract (baseline truth)

8.1 Meaning
- Watchlist stores a per-asset baseline at the moment the user adds it.
- Watchlist shows:
  - current price
  - percent change since added (computed from baseline)
  - optional: added time or age

8.2 Storage
- Store watchlist items in localStorage key: mw_watchlist
- Each entry stores:
  - product_id
  - symbol (base display symbol)
  - added_price
  - added_ts_ms

8.3 No duplicates
- A product_id can appear only once in watchlist.

8.4 Display and alignment
- Watchlist rows use the same rails and row layout contract as tables.
- Watchlist must not go blank due to a single fetch blip; it may render from last-good snapshot.


## 9) Sentiment contract (real, per-symbol, never fabricated)

9.1 Real-only rule
- Sentiment must never be invented.
- If missing/offline:
  - show UNAVAILABLE / OFFLINE / STALE
  - show last-updated timestamp if cached exists
- Forbidden: null -> 0.5 default presented as real signal.

9.2 Per-symbol correctness
- Sentiment opened for a token must use by-symbol data if available.
- If only market-wide sentiment exists:
  - label it as market-wide
  - lower confidence indicator
  - do not present it as symbol-specific

9.3 Caching and rate control
- Per-symbol sentiment requests must be cached with TTL.
- Opening tabs must not fan out extra requests (one open = one poll loop max).
- If backend is unreachable: fall back to last-good and mark STALE.

9.4 Fear and Greed handling
- If Fear and Greed is null:
  - show “—” for that field
  - do not replace with midpoint


## 10) Performance and “alive” motion

10.1 Stability rules
- Rows keyed by product_id (never by rank or index).
- Token rows must be memoized (React memo) with a narrow props compare.

10.2 Reorder hygiene
- Add hysteresis to reduce jitter:
  - re-sort on cadence or threshold, not on every micro-change

10.3 Hover effects rule
- Hover spotlight/bloom must be GPU-cheap:
  - opacity, transform, background-position on contained elements
  - no full-page repaint-on-mousemove patterns
- Row-local hover only (no global flash states)


## 11) Visual semantics

11.1 Color semantics
- Current price uses the correct mint/teal tone per the gold reference.
- Gainers/losers color semantics must match the design system.
- Text standard is cream/off-white beige for readability, unless explicitly overridden by the design system.

11.2 No stray dividers
- No random underline rules under headers.
- No stray divider above rows.


## 12) Verification checklist (fast, practical)

Ports
- Backend is :5003
- Frontend is :5173
- No runtime traffic to :5002

Data
- /data includes all required arrays
- No duplicate product_id within a list
- UI never shows “-USD”

Banners
- Continuous scroll, no hover pause
- Opposite directions top vs bottom

Tables
- 1m table follows strict 4 / 8 / 16 contract
- 3m tables follow 8 / 16 contract

Watchlist
- Baseline stored at add time
- Change since added computed correctly
- No duplicates

Sentiment
- Per-symbol differs when sources exist
- Offline states are honest; no fake 0.5 defaults
