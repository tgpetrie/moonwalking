# Moonwalkings / CBMo4ers — main.md

A compact, enforceable spec for contributors and agents. Treat this as the source-of-truth for how the app runs **locally** and on **Cloudflare** (Free + $5 Premium tier). Keep it pragmatic; ship over polish.

---

## 0) TL;DR

- **Run locally first**, then ship to Cloudflare.
- Two deploy tiers:
  - **Free** (Cloudflare Free): Pages + Worker, uses **real live data** with local/in-memory caching only.
  - **Premium** ($5 Worker tier): Durable Objects for persistent snapshots + richer metrics.
- **Two frontends:**
  - **JSX** (desktop-first): `frontend/src/App.jsx`
  - **TSX** (mobile/PWA): `frontend/src/mobile/App.tsx`
- **Backend:** Flask (`backend/app.py`) with SWR metadata on all component endpoints.
- **Metrics:** `/api/metrics` (JSON, under SWR) + `/metrics.prom` (Prometheus text). Health: `/health` and `/api/health`.
- **Data Integrity:** Free + Premium tiers both consume **live data only** (no mocks). This pledge is exposed in API responses.

---

## 1) Local Development (required)

**Prereqs:** Python 3.11+, Node 20+, npm/pnpm, OpenSSL.

**Env:**
- `backend/.env` → `PORT=5001`, `ALLOW_ORIGIN=http://127.0.0.1:3100`
- `frontend/.env.local` → `VITE_API_URL=http://127.0.0.1:5001`

**Run:**
```bash
# Backend
cd backend && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python app.py

# Frontend (separate terminal)
cd frontend && npm install && npm run dev

Smoke:

curl -s http://127.0.0.1:5001/api/health | jq
curl -s http://127.0.0.1:5001/metrics.prom | head -40
curl -s http://127.0.0.1:5001/api/metrics | jq '.one_min_market,.price_fetch,.circuit_breaker,.data_integrity'
curl -s http://127.0.0.1:5001/api/component/top-movers-bar | jq '.swr'
curl -s -X POST http://127.0.0.1:5001/api/config -H 'content-type: application/json' -d '{"flags":{"demo":true}}' | jq
```


---

2) Rules of the App (contract)
	1.	All component routes return swr metadata.
	2.	Metrics endpoints are mandatory:
	•	GET /api/metrics → { ok, status, uptime_seconds, errors_5xx, one_min_market, price_fetch, circuit_breaker, data_integrity, swr }
	•	GET /metrics.prom → Prometheus text (stable snake_case).
	3.	Health endpoints are fast: /health returns { ok: true }, /api/health returns { status: 'ok', uptime_seconds, errors_5xx, data_integrity }.
	4.	Error policy: never 500 without JSON; prefer { ok:false, error }.
	5.	Design parity: JSX and TSX read identical JSON contracts.
	6.	Security: no secrets in repo; env vars only.
	7.	Free tier must use live data only — zero mocks.

---

3) Frontend variants
	•	Desktop (JSX): frontend/src/App.jsx (dashboard: top banner, gainers/losers, volume).
	•	Mobile (TSX/PWA): frontend/src/mobile/App.tsx (touch-optimized, reduced motion, same schemas).

---

4) Cloudflare Deployment
	•	Free: Pages hosts built frontend; Worker proxies to backend; caching is in-memory; all data is live.
	•	Premium ($5): Durable Objects store 1-minute/1-hour snapshots; more metrics; background jobs.

Deploy:

cd frontend && npm run build
wrangler pages deploy --project-name moonwalking


---

5) Testing

pytest -q backend/test_swr_endpoints.py::test_swr_block_present
pytest -q backend -k "metrics or config or price_fetch"


---

6) Data Integrity Pledge (API-visible)

We operate exclusively on live market data across all tiers. No simulated, delayed, or fabricated data is allowed. This pledge is published in:
	•	GET /api/health → .data_integrity
	•	GET /api/metrics → .data_integrity

Caching layers serve performance only; never mock substitutes.

If the market sleeps, the feed sleeps. No illusions.

---

If you want, I can also add two tiny Prometheus lines so ops can scrape the pledge:

data_integrity_live_data_only 1
data_integrity_mocks_allowed 0

Say the word and I’ll point you to the exact place to emit them in `metrics_prom()`.
