# Phase 1: Canonical Sentiment Integration - COMPLETE

**Date:** 2026-01-13 05:30 PST
**Status:** ✅ WIRED UP, TESTING IN PROGRESS

---

## What We Accomplished

### ✅ Step 1: Copied `compute_final_sentiment.py` to Backend
- **File:** `/Users/cdmxx/Documents/moonwalkings/backend/compute_final_sentiment.py`
- **Status:** ✅ Created
- **Contents:** Full canonical scoring engine with tier/confidence/decay formulas

### ✅ Step 2: Created `sentiment_source_mapper.py`
- **File:** `/Users/cdmxx/Documents/moonwalkings/backend/sentiment_source_mapper.py`
- **Status:** ✅ Created
- **Functions:**
  - `map_pipeline_to_sources()` - Converts sentiment pipeline output to SourceValue list
  - `map_market_features()` - Converts price data to market_features format
  - `compute_token_sentiment()` - Main integration function
  - `tier_to_severity()` - Maps tier + confidence to CRITICAL/HIGH/MEDIUM/INFO

### ✅ Step 3: Wired into `app.py` Alert Generation
- **File:** `/Users/cdmxx/Documents/moonwalkings/backend/app.py`
- **Location:** Line ~2806 in `_emit_impulse_alert()`
- **Integration:**
```python
# CANONICAL SENTIMENT INTEGRATION: Compute severity using tier + confidence + price
try:
    from sentiment_source_mapper import compute_token_sentiment, tier_to_severity

    # Get sentiment data (cache or fetch from pipeline)
    sentiment_data = _sentiment_cache_lookup(sym_clean)
    if sentiment_data is None or sentiment_data[1]:  # If stale/missing
        sentiment_resp = requests.get(
            _pipeline_url(f'/sentiment/latest?symbol={sym_clean}'),
            timeout=2.0
        )
        if sentiment_resp.ok:
            sentiment_data = (sentiment_resp.json(), False, time.time())
            _sentiment_cache_set(sym_clean, sentiment_data[0])

    # Build price data
    price_data = {
        'price': float(price),
        'change_1m': change_1m or 0,
        'change_3m': change_3m or 0,
        'timestamp': now_ts,
        'streak': 0
    }

    # Compute canonical sentiment score
    result = compute_token_sentiment(
        symbol=sym_clean,
        sentiment_data=sentiment_data[0],
        price_data=price_data
    )

    # Use tier + confidence for severity
    severity = tier_to_severity(result['tier'], result['confidence_0_1'])

except Exception as e:
    # Fallback to price-only severity
    severity = _severity_from_changes(None, change_3m, change_1m)
```

---

## How It Works Now

### Old Flow (Price-Only)
```
Price change detected → _severity_from_changes() → CRITICAL/HIGH/MEDIUM/INFO
```

### New Flow (Sentiment + Price)
```
1. Price change detected
   ↓
2. Fetch sentiment data from pipeline (cache or API call)
   ↓
3. map_pipeline_to_sources()
   - Fear & Greed Index → SourceValue(weight=1.2)
   - Overall sentiment → SourceValue(weight=0.9)
   - Reddit → SourceValue(weight=0.75)
   - Twitter → SourceValue(weight=0.70)
   - Telegram → SourceValue(weight=0.60)
   - 4chan → SourceValue(weight=0.45)
   ↓
4. map_market_features()
   - mom_1m, mom_3m, mom_15m, mom_1h (momentum)
   - vol_z_1h (volume z-score)
   - breakout_15m (breakout indicator)
   - streak_1m (consecutive closes)
   ↓
5. compute_final_sentiment()
   - Market backbone score (0-100)
   - Overlay adjustment (±15 points from sentiment)
   - Combined score → tier (none/watch/moderate/strong/extreme)
   - Confidence decay based on tier + source coverage
   ↓
6. tier_to_severity()
   - extreme tier + confidence > 0.75 → CRITICAL
   - strong tier + confidence > 0.65 → HIGH
   - moderate tier + confidence > 0.50 → MEDIUM
   - else → INFO
   ↓
7. Frontend AnomalyStream.jsx
   - CRITICAL → [EXTREME]
   - HIGH → [VERY HIGH]
   - MEDIUM → [HIGH]
```

---

## Severity Mapping

### Canonical Scoring → Alert Severity

| Tier | Confidence | Alert Severity | UI Label |
|------|------------|----------------|----------|
| extreme | > 0.75 | CRITICAL | [EXTREME] |
| strong | > 0.65 | HIGH | [VERY HIGH] |
| moderate | > 0.50 | MEDIUM | [HIGH] |
| watch/none | any | INFO | (no label) |

### What Determines Tier?

**Score thresholds:**
- 80-100 → "extreme" (massive move + strong sentiment)
- 60-80 → "strong" (significant move + sentiment confirmation)
- 40-60 → "moderate" (notable move + some sentiment)
- 20-40 → "watch" (small move or weak sentiment)
- 0-20 → "none" (negligible)

**Score formula:**
```
score_total = (0.80 * market_score) + (0.20 * (market_score + overlay_adj))

where:
  market_score = 70% momentum + 30% participation
  overlay_adj = ±15 points from sentiment sources
```

### What Determines Confidence?

**Factors:**
1. **Freshness decay:** Stronger tiers require fresher data
   - extreme tier: 2min half-life
   - strong tier: 3.5min half-life
   - moderate tier: 7min half-life

2. **Coverage penalty:** Missing sentiment sources lower confidence
   - Full coverage (all sources) = 1.0
   - Partial coverage = linear penalty
   - Missing all sources = ~0.5 (market data only)

3. **Volatility dampener:** Extremely hot markets reduce confidence
   - rv_15m > 1.0 → confidence penalty up to -30%

**Confidence floors by tier:**
- extreme: 0.30 minimum
- strong: 0.26 minimum
- moderate: 0.22 minimum
- watch: 0.18 minimum

---

## Example Calculations

### Example 1: Strong Bullish Alert

**Inputs:**
- BTC pumps +25% in 1h (price change)
- Fear & Greed Index: 78 (unsigned 0.78)
- Overall sentiment: 0.82 (signed +0.64)
- Reddit: 0.85 (signed +0.70)
- Twitter: 0.78 (signed +0.56)
- All sources fresh (< 2 min old)

**Calculation:**
```
market_score = (
  0.70 * momentum_score +  // +25% → normalized ~0.90
  0.30 * participation     // high volume → 0.85
) = 88.5

overlay_adj = (
  1.2 * 0.56 +  // fear_greed weight * (0.78*2-1)
  0.9 * 0.64 +  // overall sentiment
  0.75 * 0.70 + // reddit
  0.70 * 0.56   // twitter
) / (1.2 + 0.9 + 0.75 + 0.70) * 15 = +9.2 points

score_total = 0.80 * 88.5 + 0.20 * (88.5 + 9.2) = 90.3

tier = "extreme" (90.3 >= 80)
confidence = 0.92 (fresh data, full coverage, normal volatility)

severity = tier_to_severity("extreme", 0.92) = "CRITICAL"
```

**UI Display:**
```
[04:25:32] 🚀 MOONSHOT BTC-USD [EXTREME] BTC pumping 25.0% in 1h with 5.2x volume!
```

---

### Example 2: Weak Bearish Alert

**Inputs:**
- ETH drops -8% in 1h (price change)
- Fear & Greed Index: 45 (unsigned 0.45)
- Overall sentiment: 0.40 (signed -0.20)
- Only reddit available (twitter/telegram/4chan offline)
- Data is 10 minutes old

**Calculation:**
```
market_score = (
  0.70 * momentum_score +  // -8% → normalized ~0.35
  0.30 * participation     // normal volume → 0.50
) = 39.5

overlay_adj = (
  1.2 * (-0.10) +  // fear_greed: 0.45*2-1 = -0.10
  0.9 * (-0.20)    // overall sentiment
) / (1.2 + 0.9) * 15 = -2.1 points

score_total = 0.80 * 39.5 + 0.20 * (39.5 - 2.1) = 39.1

tier = "watch" (39.1 < 40)

freshness = exp_decay(600s, 900s_half_life) = 0.66  // 10min old, watch tier
coverage = (1.2 + 0.9) / (1.2 + 0.9 + 0.75 + 0.70) = 0.60  // missing twitter/telegram/4chan

confidence = 0.66 * (0.60 + 0.40 * 0.60) = 0.55

severity = tier_to_severity("watch", 0.55) = "INFO"
```

**UI Display:**
```
[04:25:32] 📉 CRATER  ETH-USD  ETH dumping 8.0% in 1h
```
(No [EXTREME]/[VERY HIGH]/[HIGH] label because severity is INFO)

---

## Testing Status

### ✅ Integration Complete
- Code deployed to `/Users/cdmxx/Documents/moonwalkings/backend/`
- Backend restarted (PID 24438)
- Frontend running (PID 24450)
- Sentiment pipeline running (port 8002)

### ⏳ Waiting for Alerts
- Backend needs 3-5 minutes to accumulate streak data
- First alerts should appear when:
  - 3 consecutive 1m periods show same direction (breakout/crater)
  - OR any token moves > 2.5% in single period

### 🔍 How to Verify It's Working

**Check backend logs for canonical sentiment calls:**
```bash
tail -f /tmp/mw_backend.log | grep -E "(tier|confidence|SourceValue)"
```

**Check alerts with tier/confidence:**
```bash
curl -s http://127.0.0.1:5173/data | jq '.alerts[0] | {symbol, severity, tier, confidence_0_1}'
```

**Expected output when working:**
```json
{
  "symbol": "BTC-USD",
  "severity": "HIGH",
  "tier": "strong",
  "confidence_0_1": 0.72
}
```

---

## Fallback Behavior

If sentiment integration fails (pipeline down, timeout, error), the system **falls back to price-only severity**:

```python
except Exception as e:
    logging.debug(f"Sentiment integration failed for {sym_clean}, using price-only: {e}")
    severity = _severity_from_changes(None, change_3m, change_1m)
```

This ensures alerts always work, even if sentiment pipeline is unavailable.

---

## What's Next

### Immediate Testing (Next 5-10 minutes)
1. Wait for first alert to generate
2. Verify severity includes tier/confidence
3. Check UI displays correct intensity labels

### Phase 2 (2-3 hours)
- Add funding rates data source
- Fix pipeline to include `by_source_tier` structure
- Add Google AI classification to pipeline output
- Increase confidence scores from 0.50-0.60 → 0.70-0.90

### Phase 3 (2-3 hours)
- Add historical resolution stats
- Track alert hit rates, MFE/MAE
- Create `/api/alerts/performance` endpoint

---

## Files Modified

1. ✅ **backend/compute_final_sentiment.py** - Created (canonical scoring engine)
2. ✅ **backend/sentiment_source_mapper.py** - Created (pipeline integration)
3. ✅ **backend/app.py** - Modified (line ~2806, wired up canonical scoring)
4. ✅ **frontend/src/components/AnomalyStream.jsx** - Already updated (maps severity to intensity labels)

---

## Expected Behavior

### Before (Price-Only)
```
BTC pumps 25% → severity = HIGH (based only on magnitude)
→ UI shows: [VERY HIGH]
```

### After (Canonical Sentiment)
```
BTC pumps 25% + Fear & Greed 78 + Reddit bullish + Twitter bullish
→ market_score = 88.5
→ overlay_adj = +9.2 points
→ score_total = 90.3
→ tier = "extreme", confidence = 0.92
→ severity = CRITICAL
→ UI shows: [EXTREME]
```

**Key difference:** Sentiment amplifies or dampens price signals based on social/news data.

---

**Status:** ✅ Phase 1 complete. Waiting for first alerts to verify integration is working.

**Next:** Open browser at http://127.0.0.1:5173 and watch Intelligence Log for alerts with intensity labels!
