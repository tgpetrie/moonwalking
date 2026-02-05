# Sentiment Fix Verification

This script captures the steps already shared by the reviewer. Run each block in a separate terminal to exercise the backend, API, and frontend.

---
## 1. Backend health & sentiment route
```bash
cd backend
python app.py
```
Let Flask bind to `http://127.0.0.1:5001`. In another terminal, verify:
```bash
curl -sS http://127.0.0.1:5001/api/health
curl -sS "http://127.0.0.1:5001/api/sentiment/latest?symbol=BTC" | jq .
```
Both should return JSON (no 404/connection errors).

## 2. Frontend dev server
```bash
cd frontend
npm run dev
```
Ensure Vite picks up `frontend/.env.local`. The console should show that it proxies `/api` to the backend port (5001).

## 3. Smoke-check via browser
- Open <http://localhost:5173>
- Wait for the dashboard to load (banners / tables appear)
- Click the small info (ℹ️) button on any row in the gainers/losers tables.
- Expect the advanced sentiment popup to open, show the selected symbol in the header, and display a numeric score (pain text should not be “NaN”).
- Hover over the popup or trigger charts to ensure the gauge renders without console NaN warnings.

## 4. Network verification (DevTools)
Confirm the following requests complete successfully:
- `GET /api/data` → status 200, no 5174 port references.
- `GET /api/sentiment/latest?symbol=...` → status 200, no 8001 host.
- No hook-order warnings appear in the browser console.

## 5. Optional automation check
```bash
# Backend only
curl -sS http://127.0.0.1:5001/api/sentiment/latest?symbol=ETH
# Frontend only (after npm run dev)
curl -sS http://localhost:5173/api/sentiment/latest?symbol=ETH
```
Both should hit Flask and return the same payload.

---
Document any deviations or remaining issues (hooks, NaNs, 8001 logs) in this file before closing the ticket.
