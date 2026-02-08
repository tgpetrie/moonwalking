# Sentiment + Alerts Redesign Tracker (single source of truth)

## Governing Rule
**Mode 2 (Chat-evidenced)** governs this tracker.
- Tracker anchors (file:line) = leads, not proof.
- DONE only flips when C-proof (pasted snippet / grep / curl / screenshot) exists in chat.
- T-proof = anchor references exist in tracker text.
- C-proof = evidence pasted into conversation or logged here.

## Non-negotiables
- No UI refactors beyond what this tracker explicitly asks for.
- No new "extra dashboards" or surprise features.
- Keep backend endpoints stable unless a checklist item explicitly changes them.
- Every change must map to a checkbox. If it doesn't map, it doesn't ship.

## Goal
Replace the current sentiment/alerts experience with a real, trustworthy system:
- Sentiment is real and explainable (with sources + freshness).
- Alerts are deterministic, deduped, and readable.
- UI reflects system health (stale, down, lag) without lying.

## Current architecture (truth we enforce)
- Frontend polls a backend aggregate (data bundle).
- Backend can proxy sentiment pipeline and also compute local "market heat".
- Alerts should be generated server-side and returned in the bundle (or a dedicated endpoint), not invented on the client.

## Checklist

### A) Define the contract (API + data shapes)

#### A1: Decide canonical endpoints
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: vite.config.js:38-42 proxy rules, DataContext.jsx:483 fetch(/data), SentimentCard.jsx:49 fetch(sentimentBasic), app.py /api/alerts handler
- [x] C-proof evidence: Decision: `/api/data` is the canonical dashboard bundle (all tables + alerts + meta). `/api/sentiment-basic` is canonical for the SentimentCard (fast local). `/api/alerts` is canonical for standalone alert feeds. `/api/sentiment/latest` is a pipeline proxy (optional, not required). All three canonical endpoints confirmed working via runtime polls (P2/P4/P5)
- **Decision**: Canonical dashboard contract is `/api/data`. Supporting endpoints `/api/sentiment-basic` and `/api/alerts` remain valid for isolated cards/tools.

#### A2: Define JSON schemas (SentimentCard, Alert, MetaHealth)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/api_contracts.py:15, :69, :82, backend/app.py:1321, :7238
- [x] C-proof evidence: api_contracts.py read in chat — MetaHealth(:15), SentimentBasicPayload(:69), AlertMetrics(:82), AlertItem(:96) all with typed fields + null defaults

#### A3: Write "null rules" (null vs 0, stale definition + display)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/docs/null_rules.md:1, backend/app.py:1362, frontend/src/components/DashboardShell.jsx:200, backend/cache.py:38
- [x] C-proof evidence: null_rules.md read in chat — 270 lines covering null vs 0 global rules, 4 stale thresholds (backend 60s, frontend 20s, cache SWR 900s, SentimentCard 2/10min), per-field null rules for sentiment-basic (17 fields) + alerts (8 fields) + MetaHealth (5 fields), 3 JSON examples (fresh/stale/down)

---

### B) Real sentiment sources (minimal, free, reliable)

#### B1: Fear & Greed index source wiring (cached, rate-limited)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/sentiment_data_sources.py:6, :18, backend/app.py:1694, :1891
- [x] C-proof evidence: sentiment_data_sources.py:6 FNG_URL="https://api.alternative.me/fng/", :18 fetch_fear_and_greed_index() with timeout=5. app.py:1694 _FG_CACHE+_FG_TTL_S=300. app.py:1891 _fetch_fear_and_greed_cached() TTL check + stale-serve on failure

#### B2: Funding proxy (or omit cleanly if not available yet)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:1397
- [x] C-proof evidence: app.py:1397 hardcoded "btc_funding": {"rate_percentage": None} — no external call, omitted cleanly

#### B3: Local market heat remains first-class (breadth/volatility/impulse)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:1679, :1699, :1388
- [x] C-proof evidence: app.py:1679 _MARKET_HEAT_COMPONENT_KEYS 11 fields (green_1m/red_1m/green_3m/red_3m/total_symbols/avg_return_1m/3m/volatility/momentum_alignment/breadth_1m/3m). :1699 _compute_market_heat() pure local, no network. :1388 served first-class in payload as market_heat{score,regime,label,confidence,components,reasons}

#### B4: Source attribution + timestamp surfaced in payload
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:1382, :1387
- [x] C-proof evidence: app.py:1382 meta.source="internal", :1387 payload.timestamp=ISO string. Both in /api/sentiment-basic handler

#### B5: Hard timeout and fallback behavior (never block bundle)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/sentiment_data_sources.py:24, backend/app.py:1699, :1910, backend/cache.py:38
- [x] C-proof evidence: Market heat pure local (no network, :1699). F&G hard 5s timeout (sentiment_data_sources.py:24). Stale-serve on F&G failure (app.py:1910 returns _FG_CACHE["data"]). Cache SWR 15min (cache.py:38 stale_seconds=900)

---

### C) Alert engine redesign (deterministic, deduped, useful)

#### C1: Define alert types and thresholds registry (single file)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:3496-3519
- [x] C-proof evidence: app.py:3496 ALERT_IMPULSE_1M_THRESH=1.25%, :3497 3M=2.0%, :3498 COOLDOWN=90s, :3499 DEDUPE_DELTA=0.35, :3500 TTL=5min, :3501 VOLATILITY_SPIKE=2.0. Per-type cooldowns via callers: whale 120s(:4056), divergence 180s(:3883), stealth 300s(:4112), fomo/fear 600s(:4286). _WINDOW_S_MAP + _DEFAULT_COOLDOWN_BY_WS at :3515-3519

#### C2: Implement alert ID + dedupe rules (symbol+type+window+bucket)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:3604-3652, :3655-3734
- [x] C-proof evidence: _emit_alert(:3604) key=type::symbol, compares magnitude vs prev+dedupe_delta, checks direction flip, within_cooldown gate. emit_alert(:3655) same pattern with _BASIC_ALERT_EMIT_TS/VAL/DIR. Alert IDs: f"{type}_{product_id}_{timestamp_ms}" at :3783. Two independent streams (alerts_log_main + alerts_basic_log) with independent dedupe state

#### C3: Cooldown + TTL rules (per type/window)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:3498, :3799, :3632-3644, :3698-3710
- [x] C-proof evidence: Per-type cooldowns: impulse 90s, whale 120s, divergence 180s, stealth 300s, fomo/fear 600s. TTL via expires_at at :3799 (now + 5min). Update-in-place at :3632-3644 bumps event_count + metrics.pct when magnitude grows within cooldown. Same pattern in emit_alert at :3698-3710

#### C4: Alert text generator (consistent, compact, no spam)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/alert_text.py:54-258
- [x] C-proof evidence: alert_text.py:54 build_alert_text() — single function, 15+ kind branches (impulse/moonshot/crater/breakout/dump/divergence/volatility_spike/whale_move/whale_absorption/whale_surge/stealth_move/fomo_alert/fear_alert/seed + moonwalking system types). Returns (message, title). Formatting via _fmt_pct/_fmt_ratio/_fmt_price helpers. Called from _emit_impulse_alert at app.py:3774

#### C5: Include "why" metadata (computed features that triggered it)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: backend/app.py:3522 inject_bridge_fields, backend/api_contracts.py:82 AlertMetrics, frontend/src/utils/alertClassifier.js:14 extractAlertPct
- [x] C-proof evidence: inject_bridge_fields(:3522) builds metrics{pct,window_s,price,price_now,price_then,volume,vol_change_pct} from alert+meta+extra. Called from _emit_alert, emit_alert, _normalize_alert, _seed_alerts_once. AlertMetrics schema at api_contracts.py:82. Frontend extractAlertPct prefers metrics.pct at alertClassifier.js:14-21

---

### D) UI integration (minimal but honest)

#### D1: SentimentCard renders real values with "stale/down" states
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: frontend/src/components/cards/SentimentCard.jsx:6, :49, :89, :142, :190
- [x] C-proof evidence: SentimentCard.jsx:6 freshnessLabel() — <2min=fresh, <10min=recent, else stale. :49 polls API_ENDPOINTS.sentimentBasic. :72-87 mapBasicSentiment extracts overallSentiment(score/100)+fearGreedIndex. :89 SentimentCardBody renders Overall+F&G stats. :142 shows freshness label. :190 "Sentiment offline." on error+no data

#### D2: Alerts stream renders types/severity correctly (no misclassification)
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: frontend/src/components/AnomalyStream.jsx:347 extractAlertPct, frontend/src/utils/alertClassifier.js:75 deriveAlertType, AlertsDock.jsx:105 extractAlertPct
- [x] C-proof evidence: AnomalyStream(:347) calls extractAlertPct(a) → pct = extracted.pct ?? pickNumber fallback. AlertsDock(:105) calls extractAlertPct(a) → effectivePct → deriveAlertType. deriveAlertType(:75) classifies by exact type match then magnitude thresholds. Both use _asNum for string-safe null handling

#### D3: Add small health indicator (pipeline ok/stale) with timestamp
- [x] **DONE** (C-proven 2026-02-07)
- [x] T-proof anchors: frontend/src/components/DashboardShell.jsx:200, :202, :239
- [x] C-proof evidence: DashboardShell.jsx:200 STALE_THRESHOLD=20s. :202-213 status useMemo: LIVE/WARMING/STALE/DEGRADED/OFFLINE from fatal+error+warming+staleSeconds+partialStreak. :215-218 lastUpdatedLabel from lastUpdated||lastGoodTs. :239 renders bh-status-pill with status class + live-updated-time

#### D4: No style bleed into terminal/intelligence panel
- [x] **DONE** (C-proven 2026-02-07, structural)
- [x] T-proof anchors: frontend/src/index.css:5782-5792
- [x] C-proof evidence: CSS guard at index.css:5782 + Playwright runtime DOM proof: 8 bh-intel-line elements all show boxShadow="none", afterBoxShadow="none", afterContent="none". rowsInsideIntelPanel=0 (zero .bh-row/.token-row leaked). Screenshot p3_healthy_final.png confirms intel panel renders terminal-clean with no row glow bleed

---

### E) Proof steps (must pass twice)

#### P1: `./start_local.sh` runs clean
- [x] **DONE** (C-proven 2026-02-07)
- [x] C-proof evidence: Line 357 fixed (quoting `"${frontend_ok}"`). Rerun output pasted: zero errors, zero warnings. `[start.local] frontend root is responding` + `[start.local] backend /data is responding`. Both http://127.0.0.1:5003 and :5173 return 200

#### P2: Backend returns stable JSON (no missing keys) for 5 consecutive polls
- [x] **DONE** (C-proven 2026-02-07)
- [x] C-proof evidence: 5 consecutive `curl /api/sentiment-basic` polls pasted in chat. All return: ok=true, timestamp(ISO), market_heat{score,regime,label,confidence,11 components,reasons}, fear_greed{value=6,classification="Extreme Fear"}, btc_funding{rate_percentage=null}, meta{ok=true,pipelineRunning=true,staleSeconds,lastOkTs,error=null,source="internal",stale=false}. Zero missing keys across all 5 polls

#### P3: Simulate pipeline down → UI shows stale/down, no crashes
- [x] **DONE** (C-proven 2026-02-07)
- [x] C-proof evidence: Backend killed (`kill $(cat /tmp/mw_backend.pid)`), confirmed unreachable (curl returns connection refused). Playwright runtime DOM proof in fresh incognito context (no cache/localStorage): pill text="OFFLINE", class="bh-status-pill bh-status-pill--offline". Empty data tables (hasData=0). rootChildren>0 (no white screen). No crash. Screenshot p3_offline.png confirms degraded UI state

#### P4: Alerts dedupe works (no repeated spam on same move)
- [x] **DONE** (C-proven 2026-02-07)
- [x] C-proof evidence: `curl /api/data` alerts section pasted in chat. 9 alerts total, no spam. fear_alert::MARKET has event_count=2 (update-in-place working — fired twice, 1 entry, count bumped). Every alert has dedupe_key (e.g. IMPULSE_1M:SUKU-USD:60), cooldown_s=45, metrics.pct typed. `curl /api/alerts` shows 2 alerts with full bridge fields (dedupe_key, cooldown_s, event_count, metrics)

#### P5: Restart and confirm same behavior
- [x] **DONE** (C-proven 2026-02-07)
- [x] C-proof evidence: Full stop (kill backend+frontend+pipeline) → confirmed backend unreachable → `bash start_local.sh` → backend responds 200 → post-restart `curl /api/sentiment-basic` returns identical schema: ok=true, all keys present, meta.ok=true, stale=false, staleSeconds=7, fear_greed.value=6

---

## Score: 21/21 DONE
## Remaining: None

## Notes / Findings
- Keep a running list: files touched, thresholds changed, payload decisions.
- 2026-02-07: Converted to Mode 2 dual-layer format. All items demoted pending chat-evidenced proof.
- 2026-02-07: Bulk static C-proof pass — 16 items proven from source reads.
- 2026-02-07: Runtime sweep — P1-P5 + D4 proven. start_local.sh line 357 has pre-existing bash corruption (not our change). All endpoints return stable JSON, dedupe works (event_count incrementing), restart preserves behavior.
- 2026-02-07: A1 closed — canonical endpoints decided: `/api/data` (dashboard bundle), `/api/sentiment-basic` (SentimentCard), `/api/alerts` (standalone feeds). `/api/sentiment/latest` is optional pipeline proxy.
- 2026-02-07: P3 re-proven with Playwright incognito context (fresh load with backend dead → OFFLINE pill, no crash). D4 re-proven with Playwright computed styles (boxShadow=none on all intel-line elements, zero leaked rows).
- 2026-02-07: **21/21 — tracker complete.**
