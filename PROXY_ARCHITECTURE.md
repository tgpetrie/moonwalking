# Proxy-First Architecture - Enforcement Documentation

**Decision Date:** 2026-01-12  
**Status:** ✅ ENFORCED

## Decision: PROXY-FIRST

### Why Proxy-First?

1. **Single Origin Policy** - Browser requests same origin (localhost:5173), no CORS issues
2. **Simpler Configuration** - Backend URL configured once in vite.config.js
3. **Production Parity** - Mirrors production nginx/reverse proxy setup
4. **Clean Code** - Frontend uses relative paths, no host/port hardcoding
5. **Zero Ambiguity** - No fallback roulette or multiple backend candidates

## Architecture Flow

```
Browser (localhost:5173)
    ↓ fetch("/data")
Vite Dev Proxy
    ↓ proxies to http://127.0.0.1:5003/data
Flask Backend (port 5003)
    ↓ returns JSON
Vite Dev Proxy
    ↓ forwards response
Browser receives data
```

## Files Changed

### 1. `frontend/src/context/DataContext.jsx`

**BEFORE (❌ Direct with fallback roulette):**
```javascript
const candidates = [];
if (backendBase) candidates.push(backendBase);
["http://127.0.0.1:5003", "http://127.0.0.1:5002"].forEach((b) => {
  if (!candidates.includes(b)) candidates.push(b);
});
// Tries multiple URLs, caches backend host in localStorage
```

**AFTER (✅ Proxy-first):**
```javascript
// PROXY-FIRST ARCHITECTURE: Always use relative path
const url = "/data";
const res = await fetch(url, {
  signal: controller.signal,
  headers: { Accept: "application/json" },
  cache: "no-store"
});
```

**Changes:**
- Line 316-389: Removed candidate array and multi-URL fallback logic
- Line 154: Set backendBase to "/data" (constant, no localStorage lookup)
- Line 189-211: Removed baseUrl parameter from persistLastGood()
- Line 213: Removed baseUrl parameter from applySnapshot()
- Removed MW_BACKEND_KEY constant

### 2. `frontend/vite.config.js`

**BEFORE:**
```javascript
const target =
  process.env.VITE_PROXY_TARGET ||
  process.env.VITE_API_BASE_URL ||
  'http://127.0.0.1:5003'
```

**AFTER:**
```javascript
// PROXY-FIRST ARCHITECTURE: Single canonical backend
const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5003'
```

Proxy configuration remains:
```javascript
proxy: {
  '/data': { target, changeOrigin: true },
  '/api': { target, changeOrigin: true },
  '/api/sentiment': { target, changeOrigin: true },
  '/sentiment': { target, changeOrigin: true },
}
```

### 3. `frontend/.env.local`

**BEFORE:**
```env
VITE_API_BASE=http://127.0.0.1:5003
VITE_API_BASE_URL=http://127.0.0.1:5003
VITE_SENTIMENT_BASE_URL=http://127.0.0.1:5003
```

**AFTER:**
```env
# PROXY-FIRST ARCHITECTURE: Backend proxy target (used by vite.config.js)
VITE_PROXY_TARGET=http://127.0.0.1:5003
```

**Removed:**
- `VITE_API_BASE` (unused)
- `VITE_API_BASE_URL` (caused confusion)
- `VITE_SENTIMENT_BASE_URL` (sentiment API uses /api proxy)

## Alert System Verification

### Alert Type Mapping Correctness

Backend emits lowercase types (e.g., "breakout", "moonshot", "crater").

Frontend `alertConfig.js` normalizes to uppercase:
```javascript
const normalized = String(alertType).toUpperCase().replace(/\s+/g, "_");
// "breakout" → "BREAKOUT" → matches ALERT_CONFIG.BREAKOUT
```

**Verified Mappings:**
| Backend Type | Normalized | Frontend Config | Icon | Color |
|--------------|------------|-----------------|------|-------|
| breakout | BREAKOUT | ✅ BREAKOUT | 📈 | #f59e0b |
| moonshot | MOONSHOT | ✅ MOONSHOT | 🚀 | #10b981 |
| crater | CRATER | ✅ CRATER | 📉 | #dc2626 |
| sentiment_spike | SENTIMENT_SPIKE | ✅ SENTIMENT_SPIKE | 🌊 | #3b82f6 |
| whale_move | WHALE_MOVE | ✅ WHALE_MOVE | 🐋 | #06b6d4 |
| divergence | DIVERGENCE | ✅ DIVERGENCE | ⚖️ | #a855f7 |
| fomo_alert | FOMO_ALERT | ✅ FOMO_ALERT | 🔥 | #ef4444 |
| stealth_move | STEALTH_MOVE | ✅ STEALTH_MOVE | 👤 | #6366f1 |
| news_catalyst | NEWS_CATALYST | ✅ NEWS_CATALYST | 📰 | #8b5cf6 |
| arbitrage | ARBITRAGE | ✅ ARBITRAGE | 💰 | #14b8a6 |

### Alert Normalization Flow

1. **Backend** (`/data` endpoint) returns:
```json
{
  "id": "LTC-USD-1m-2026-01-12T18:23:45.776535",
  "type": "breakout",
  "severity": "medium",
  "symbol": "LTC-USD",
  "message": "1m trend up x3 on LTC",
  "score": 1.58
}
```

2. **DataContext.normAlert()** (line 47-76) normalizes:
```javascript
{
  id: "LTC-USD-1m-2026-01-12T18:23:45.776535",
  alert_type: "BREAKOUT",  // ← uppercased
  severity: "MEDIUM",      // ← uppercased
  severity_lc: "medium",   // ← preserved for CSS
  symbol: "LTC-USD",
  message: "1m trend up x3 on LTC",
  score: 1.58,
  ts_ms: 1736704425776
}
```

3. **alertConfig.getAlertConfig()** returns:
```javascript
{
  icon: "📈",
  label: "BREAKOUT",
  displayName: "📈 BREAKOUT",
  color: "#f59e0b"
}
```

4. **Components render:**
- **AnomalyStream**: `[18:23:45] 📈 BREAKOUT LTC-USD 1m trend up x3 on LTC score 1.58 [Trade]`
- **TokenRowUnified**: Badge with `📈 BREAK` and amber glow
- **FloatingAlertContainer**: Toast with `📈 BREAKOUT` title

## Network Tab Verification

**After changes, Network tab shows:**

```
Request URL: http://localhost:5173/data
Request Method: GET
Status Code: 200 OK
```

**NOT:**
- ❌ `http://127.0.0.1:5003/data` (direct)
- ❌ `http://127.0.0.1:5002/data` (fallback)

**Response Headers include:**
```
Access-Control-Allow-Origin: http://127.0.0.1:5173
Content-Type: application/json
```

## Acceptance Criteria - All Met ✅

- ✅ One canonical fetch path (proxy-first) with no ambiguity
- ✅ Network tab shows requests to :5173 (proxy), not :5003 (direct)
- ✅ Alerts show correct icons + labels + severity tones in Intelligence Log
- ✅ Trade links open correctly (trade_url preserved from backend)
- ✅ No duplicate alert mapping code in multiple components
- ✅ alertConfig covers ALL emitted backend types with proper normalization
- ✅ Zero localStorage backend URL caching
- ✅ Zero multi-candidate fallback logic

## Testing Commands

```bash
# Start backend (must be on 5003)
cd backend
python app.py  # Should listen on 127.0.0.1:5003

# Start frontend (proxy mode)
cd frontend
npm run dev    # Vite dev server on 127.0.0.1:5173

# Verify proxy working
curl http://127.0.0.1:5173/data
# Should return backend /data response (proxied)

# Verify backend direct (for comparison)
curl http://127.0.0.1:5003/data
# Should return same data

# Open browser
open http://127.0.0.1:5173
# Open DevTools → Network
# Look for /data requests
# Should show: localhost:5173/data (NOT :5003/data)
```

## Production Deployment

In production, nginx/reverse proxy will handle the same routing:

```nginx
location /data {
    proxy_pass http://backend:5003/data;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /api {
    proxy_pass http://backend:5003/api;
}
```

Frontend build artifacts are static files served by nginx, backend runs on separate service.

## Troubleshooting

**Problem:** Browser shows CORS errors  
**Solution:** Ensure Vite dev server is running and proxy is configured

**Problem:** 404 on /data  
**Solution:** Verify backend is running on port 5003

**Problem:** Network shows :5003 requests  
**Solution:** Clear browser cache, hard reload (Cmd+Shift+R)

**Problem:** Alerts not showing icons  
**Solution:** Check backend `type` field matches alertConfig keys (case-insensitive)

## Summary

**Architecture:** PROXY-FIRST ✅  
**Ambiguity:** ZERO ✅  
**Fallback Roulette:** ELIMINATED ✅  
**Alert Coverage:** COMPLETE ✅  
**Network Path:** /data (proxied to :5003) ✅
