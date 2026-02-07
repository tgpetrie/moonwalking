# Sentiment + Alerts Redesign Tracker (single source of truth)

## Non-negotiables
- No UI refactors beyond what this tracker explicitly asks for.
- No new “extra dashboards” or surprise features.
- Keep backend endpoints stable unless a checklist item explicitly changes them.
- Every change must map to a checkbox. If it doesn’t map, it doesn’t ship.

## Goal
Replace the current sentiment/alerts experience with a real, trustworthy system:
- Sentiment is real and explainable (with sources + freshness).
- Alerts are deterministic, deduped, and readable.
- UI reflects system health (stale, down, lag) without lying.

## Current architecture (truth we enforce)
- Frontend polls a backend aggregate (data bundle).
- Backend can proxy sentiment pipeline and also compute local “market heat”.
- Alerts should be generated server-side and returned in the bundle (or a dedicated endpoint), not invented on the client.

## Checklist

### A) Define the contract (API + data shapes)
- [ ] A1: Decide canonical endpoints (keep or adjust):
  - `/api/data` (bundle)
  - `/api/sentiment-basic` (fast local)
  - `/api/sentiment/latest` (pipeline proxy)
  - `/api/alerts` OR alerts included inside `/api/data`
- [x] A2: Define JSON schemas for: (Proof: backend/api_contracts.py:15, backend/api_contracts.py:69, backend/api_contracts.py:82, backend/app.py:1321, backend/app.py:7238)
  - SentimentCard payload (fields, types, null rules)
  - Alert item payload (id, ts, type, severity, symbol, window, pct, price, meta)
  - Meta health payload (pipeline ok, staleSeconds, lastOkTs, error)
- [x] A3: Write “null rules”: (Proof: backend/docs/null_rules.md:1, backend/app.py:1362, frontend/src/components/DashboardShell.jsx:200, backend/cache.py:38)
  - When to return null vs 0
  - What “stale” means and how it displays

### B) Real sentiment sources (minimal, free, reliable)
- [x] B1: Fear & Greed index source wiring (cached, rate-limited) (Proof: backend/sentiment_data_sources.py:6, backend/sentiment_data_sources.py:18, backend/app.py:1694, backend/app.py:1890)
- [x] B2: Funding proxy (or omit cleanly if not available yet) (Proof: backend/app.py:1396)
- [x] B3: Local market heat remains first-class (breadth/volatility/impulse mix) (Proof: backend/app.py:1678, backend/app.py:1698)
- [x] B4: Source attribution + timestamp surfaced in payload (Proof: backend/app.py:1381, backend/app.py:1386)
- [x] B5: Hard timeout and fallback behavior (never block bundle) (Proof: backend/sentiment_data_sources.py:24, backend/app.py:1890, backend/app.py:1905)

### C) Alert engine redesign (deterministic, deduped, useful)
- [ ] C1: Define alert types and thresholds registry (single file)
- [ ] C2: Implement alert ID + dedupe rules (symbol+type+window+bucket)
- [ ] C3: Cooldown + TTL rules (per type/window)
- [x] C4: Alert text generator (consistent, compact, no spam) (Proof: backend/alert_text.py:54, backend/app.py:3683, backend/moonwalking_alert_system.py:388)
- [ ] C5: Include “why” metadata (the computed features that triggered it)

### D) UI integration (minimal but honest)
- [ ] D1: SentimentCard renders real values with “stale/down” states
- [ ] D2: Alerts stream renders types/severity correctly (no misclassification)
- [ ] D3: Add small health indicator (pipeline ok/stale) with timestamp
- [ ] D4: No style bleed into terminal/intelligence panel

### E) Proof steps (must pass twice)
- [ ] P1: `./start_local.sh` runs clean
- [ ] P2: Backend returns stable JSON (no missing keys) for 5 consecutive polls
- [ ] P3: Simulate pipeline down → UI shows stale/down, no crashes
- [ ] P4: Alerts dedupe works (no repeated spam on same move)
- [ ] P5: Restart and confirm same behavior

## Notes / Findings
- Keep a running list: files touched, thresholds changed, payload decisions.
