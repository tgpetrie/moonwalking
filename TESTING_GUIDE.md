# Divergence Engine Testing Guide

This guide will help you test the complete Divergence Engine implementation (Phase 4 - Sprint 1).

---

## 🔧 Prerequisites

### 1. Install Redis
```bash
# macOS
brew install redis
brew services start redis

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

### 2. Set Environment Variables

Create `backend/.env`:
```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (defaults shown)
REDIS_URL=redis://localhost:6379/0
INTEL_TTL_SECONDS=300
INTEL_STALE_SECONDS=900
INTEL_REFRESH_WORKERS=4
INTEL_MAX_SYMBOLS=50
```

Create `frontend/.env.local`:
```bash
VITE_API_BASE=http://127.0.0.1:5001
VITE_INTEL_POLL_MS=300000
VITE_USE_MOCK=false
```

---

## 🧪 Test Plan

### **Test 1: Backend Health Check**

Verify the intelligence subsystem loads correctly.

```bash
# Terminal 1: Start backend
cd backend
python app.py

# Terminal 2: Check health
curl -sS http://127.0.0.1:5001/api/health-intelligence | jq
```

**Expected Response:**
```json
{
  "success": true,
  "version": "v1",
  "data": {
    "status": "ok",
    "time": "2025-12-23T...",
    "redis_ok": true,
    "engine_loaded": true,
    "model": {
      "name": "ProsusAI/finbert",
      "device": "mps",  // or "cpu" on N100
      "quantized": false
    }
  }
}
```

**Look for in logs:**
```
📍 Loading FinBERT on device: MPS
✅ FinBERT loaded successfully on mps
✅ Gemini 1.5 Flash connected for narrative analysis
✅ Redis connected: redis://localhost:6379/0
🔄 Refresher initialized with 4 workers on mps
✅ Intelligence API blueprint registered
```

---

### **Test 2: Single Symbol Report**

Test individual intelligence report generation.

```bash
curl -sS "http://127.0.0.1:5001/api/intelligence-report/BTC" | jq
```

**First Call (Cache Miss):**
```json
{
  "success": true,
  "version": "v1",
  "data": {
    "symbol": "BTC",
    "price": 104123.45,
    "metrics": {
      "finbert_score": 0.0,
      "finbert_label": "Neutral",
      "fear_greed_index": null,
      "social_volume": null,
      "confidence": 0.0,
      "divergence": "none"
    },
    "freshness": "building",  // ← Building stub returned immediately
    ...
  }
}
```

**Second Call (~2 seconds later):**
```json
{
  "success": true,
  "version": "v1",
  "data": {
    "symbol": "BTC",
    "metrics": {
      "finbert_score": 0.42,
      "finbert_label": "Bullish",
      "fear_greed_index": 28,
      "social_volume": null,
      "confidence": 0.89,
      "divergence": "bullish_divergence"  // ← Divergence detected!
    },
    "freshness": "fresh",  // ← Real report now cached
    ...
  }
}
```

**Look for in logs:**
```
🚀 Triggered refresh for BTC
🔨 Computing report for BTC
✅ Refreshed: BTC on mps
```

---

### **Test 3: Batch Request (Critical)**

This is the key test - verify batch fetching works correctly.

```bash
curl -sS "http://127.0.0.1:5001/api/intelligence-reports?symbols=BTC,ETH,SOL" | jq
```

**Expected Response:**
```json
{
  "success": true,
  "version": "v1",
  "data": {
    "BTC": { "symbol": "BTC", "metrics": {...}, "freshness": "fresh" },
    "ETH": { "symbol": "ETH", "metrics": {...}, "freshness": "building" },
    "SOL": { "symbol": "SOL", "metrics": {...}, "freshness": "fresh" }
  }
}
```

**Look for in logs:**
```
🚀 Triggered 3 refreshes
```

**Performance Check:**
- First call: Returns immediately with "building" stubs
- Wait 2-3 seconds
- Second call: Should be <50ms (cached)

---

### **Test 4: SWR Cache Behavior**

Verify Stale-While-Revalidate works correctly.

```bash
# 1. Get fresh report
curl -sS "http://127.0.0.1:5001/api/intelligence-report/BTC" | jq '.data.freshness'
# Output: "fresh"

# 2. Wait 6 minutes (TTL = 5 minutes)
sleep 360

# 3. Request again - should return stale + trigger refresh
curl -sS "http://127.0.0.1:5001/api/intelligence-report/BTC" | jq '.data.freshness'
# Output: "stale"

# 4. Immediately request again - should be "fresh" now
curl -sS "http://127.0.0.1:5001/api/intelligence-report/BTC" | jq '.data.freshness'
# Output: "fresh"
```

---

### **Test 5: Frontend Integration**

#### **Step 1: Enable Mock Mode (Quick UI Test)**

```bash
# frontend/.env.local
VITE_USE_MOCK=true
```

```bash
cd frontend
npm run dev
```

1. Open http://localhost:5173
2. Add BTC, ETH, SOL to watchlist
3. **Within 1 second**, you should see:
   - Green pulsing dots next to symbols
   - "FB: 0.90" and "F&G: 20" in metrics
4. Hover over pulse → Should show mock narrative

**Verify in Browser DevTools:**
- Network tab: **NO requests** to `/api/intelligence-reports`
- Console: No errors

---

#### **Step 2: Test Real Backend**

```bash
# frontend/.env.local
VITE_USE_MOCK=false
VITE_INTEL_POLL_MS=30000  # 30 seconds for testing (faster feedback)
```

```bash
# Restart frontend
npm run dev
```

1. Add BTC to watchlist
2. **Open DevTools Network Tab**
3. Filter by "intelligence"
4. **Expected behavior:**
   - 1 request to `/api/intelligence-reports?symbols=BTC`
   - NO requests to `/api/intelligence-report/BTC` (per-row fetching)
   - Request repeats every 30 seconds

5. Add ETH to watchlist
6. **Expected:**
   - Next poll: `/api/intelligence-reports?symbols=BTC,ETH` (batched!)

7. **Tab Visibility Test:**
   - Switch to another tab
   - Wait 2 minutes
   - Switch back
   - **Expected:** Immediate request triggered

---

### **Test 6: Divergence Detection**

Create a scenario where divergence triggers.

**Option A: Mock Data**
Edit `backend/sentiment_intelligence.py`:

```python
def fetch_fear_greed_index() -> Optional[int]:
    return 18  # Force low Fear & Greed (retail fear)

def fetch_top_headlines(symbol: str) -> List[str]:
    return [
        f"{symbol} receives institutional investment from BlackRock",
        f"Major banks adopt {symbol} for settlements",
        f"{symbol} integration announced by Fortune 500 companies"
    ]
```

Restart backend and check:
```bash
curl -sS "http://127.0.0.1:5001/api/intelligence-report/BTC" | jq '.data.metrics.divergence'
# Expected: "bullish_divergence"
```

**Option B: Wait for Real Divergence**
Monitor the watchlist over time. When divergence occurs, you'll see:
- 🟢 Green pulse (Bullish divergence)
- 🔴 Red pulse (Bearish divergence)

---

## ✅ Acceptance Criteria Checklist

- [ ] **Health**: `/api/health-intelligence` returns `success: true`, `redis_ok: true`, `engine_loaded: true`
- [ ] **Batch endpoint**: `/api/intelligence-reports?symbols=BTC,ETH` returns map with both symbols
- [ ] **Cache behavior**: Second call to same symbol is <50ms (cached)
- [ ] **SWR**: After TTL expires, returns stale data while refreshing in background
- [ ] **Frontend batching**: Only ONE request per poll cycle (check Network tab)
- [ ] **No per-row requests**: Adding 5 symbols = 1 batch request, not 5 individual requests
- [ ] **Tab visibility**: Polling pauses when tab hidden, resumes when visible
- [ ] **Pulse UI**: Divergence shows green/red pulse animation
- [ ] **Mock mode**: Works without backend running

---

## 🐛 Troubleshooting

### "Redis connection failed"
```bash
redis-cli ping  # Check Redis is running
brew services start redis  # Start if needed
```

### "Failed to load FinBERT"
```bash
# Check PyTorch/MPS
python -c "import torch; print(torch.backends.mps.is_available())"
```

### "Gemini API error"
```bash
# Check API key
echo $GEMINI_API_KEY
```

### Frontend shows no data
1. Check backend is running: `curl http://127.0.0.1:5001/api/health-intelligence`
2. Check CORS in browser console
3. Verify `.env.local` has `VITE_API_BASE=http://127.0.0.1:5001`

### Watchlist shows "—" for metrics
This is normal for symbols with no cached report yet. Wait 2-3 seconds for background refresh to complete.

---

## 📊 Performance Benchmarks (M3 Mac)

Expected performance on Mac M3:

- **Model Load**: ~2-3 seconds (one-time at startup)
- **Single Report (cache miss)**: ~500-800ms (FinBERT inference)
- **Single Report (cache hit)**: <10ms
- **Batch 10 symbols (all miss)**: ~800ms (parallel inference)
- **Batch 10 symbols (all hit)**: <20ms

**N100 will be ~3x slower for inference, but cache performance is identical.**

---

## 🚀 Next Steps After Testing

Once all tests pass:

1. **Phase 5**: Integrate real RSS feeds into `fetch_top_headlines()`
2. **Phase 6**: ONNX quantization for N100 migration
3. **Production**: Deploy with systemd + Cloudflare Tunnel

---

## 📝 Test Results Log Template

```
Date: ____________________
Tester: __________________

[ ] Test 1: Backend Health Check - PASS/FAIL
    Notes: _______________________________

[ ] Test 2: Single Symbol Report - PASS/FAIL
    Notes: _______________________________

[ ] Test 3: Batch Request - PASS/FAIL
    Notes: _______________________________

[ ] Test 4: SWR Cache Behavior - PASS/FAIL
    Notes: _______________________________

[ ] Test 5: Frontend Mock Mode - PASS/FAIL
    Notes: _______________________________

[ ] Test 6: Frontend Real Backend - PASS/FAIL
    Notes: _______________________________

[ ] Test 7: Divergence Detection - PASS/FAIL
    Notes: _______________________________

Overall Status: PASS/FAIL
```
