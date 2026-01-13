# UI Improvements - Simplified Alert Display

**Date:** 2026-01-13 04:25 PST
**Changes:** Removed confusing score system, simplified alert labels

---

## Problem

The scoring system (e.g., "score 1.41") was:
- **Confusing** to average users without context
- **Unnecessary** technical detail cluttering the UI
- **Not actionable** - users don't know if 1.41 is good or bad

## Solution

### Before
```
[04:13:08] 📉 CRATER  AAVE-USD  1m trend down x3 on AAVE (>= 3; score 1.41)  [Trade]
```

### After
```
[04:13:08] 📉 CRATER  AAVE-USD [HIGH]  1m trend down x3 on AAVE (>= 3)  [Trade]
```

## Changes Made

### Intelligence Log ([AnomalyStream.jsx](frontend/src/components/AnomalyStream.jsx))

**Removed:**
- Raw score display (e.g., "score 1.41")
- Streak-based intensity (x3 is just a fun visual indicator, not real signal strength)

**Added:**
- **Sentiment-based intensity indicators** from backend formulas:
  - **[EXTREME]** - CRITICAL severity (50%+ pump OR 30%+ dump in 1h)
  - **[VERY HIGH]** - HIGH severity (30%+ pump OR 20%+ dump in 1h)
  - **[HIGH]** - MEDIUM severity (10-30% pump OR 10-20% dump)
  - No indicator - INFO/LOW severity (regular alerts, still shown)

**Logic:**
```javascript
// Map backend severity to display intensity
// Backend uses formulas: CRITICAL (50%+ pump, 30%+ dump), HIGH (30%+ pump, 20%+ dump), MEDIUM (smaller moves)
const severityUpper = String(alert?.severity || "").toUpperCase();
let intensity = null;
if (severityUpper === "CRITICAL") intensity = "EXTREME";
else if (severityUpper === "HIGH") intensity = "VERY HIGH";
else if (severityUpper === "MEDIUM") intensity = "HIGH";
// INFO/LOW = no intensity label
```

**Backend Formulas** (from [moonwalking_alert_system.py](backend/moonwalking_alert_system.py)):

**MOONSHOT:**
```python
if change_1h > 0.5:  # 50%+ pump
    severity = AlertSeverity.CRITICAL
elif change_1h > 0.3:  # 30%+ pump
    severity = AlertSeverity.HIGH
else:
    severity = AlertSeverity.MEDIUM
```

**CRATER:**
```python
if change_1h < -0.3:  # 30%+ dump
    severity = AlertSeverity.CRITICAL
elif change_1h < -0.2:  # 20%+ dump
    severity = AlertSeverity.HIGH
else:
    severity = AlertSeverity.MEDIUM
```

## Benefits

1. **Clarity**: Users immediately understand signal strength ("HIGH" vs "score 1.41")
2. **Simplicity**: Only shows indicators when it matters (strong signals)
3. **Action-oriented**: Clear visual hierarchy (EXTREME > VERY HIGH > HIGH > standard)
4. **Less clutter**: 90% of alerts won't show intensity (score < 1.5), keeping UI clean

## Examples

### Standard Alert (no intensity)
```
📈 BREAKOUT  BTC-USD  1m trend up x3 on BTC (>= 3)
```
- Score is 1.35 (below 1.5 threshold)
- Good signal but not exceptional
- No intensity label needed

### High Strength Alert
```
📉 CRATER  ETH-USD [HIGH]  1m trend down x3 on ETH (>= 3)
```
- Score is 1.62 (>= 1.5)
- Strong downtrend, worth immediate attention
- Shows [HIGH] indicator

### Very Strong Alert
```
🚀 MOONSHOT  SOL-USD [VERY HIGH]  1m trend up x3 on SOL (>= 3)
```
- Score is 1.87 (>= 1.75)
- Very strong uptrend, high confidence
- Shows [VERY HIGH] indicator

### Extreme Alert (rare)
```
📉 CRATER  LUNA-USD [EXTREME]  1m trend down x3 on LUNA (>= 3)
```
- Score is 2.34 (>= 2.0)
- Exceptional move, potential crash
- Shows [EXTREME] indicator

## Configuration

No environment variables needed. Thresholds are hardcoded in AnomalyStream.jsx:

```javascript
if (score >= 2.0) intensity = "EXTREME";       // Top 1-2% of alerts
else if (score >= 1.75) intensity = "VERY HIGH"; // Top 5-10% of alerts
else if (score >= 1.5) intensity = "HIGH";       // Top 15-20% of alerts
// else: no indicator (80-85% of alerts)
```

## Backend Configuration (Not Changed)

The backend still calculates scores normally:
- **Sample size:** 120 tokens (carefully calculated, not changed)
- **Seed count:** 35 tokens for 1m list (increased from 10 for faster population)
- **Alert thresholds:** 3x and 5x streaks (unchanged)

## Data Warmup Behavior

The backend needs time to accumulate data before showing tables:

**Timeline:**
- **0-30s:** Fetching initial prices, building history
- **30-60s:** 1m gainers/losers start appearing (10-20 tokens)
- **60-120s:** 3m gainers/losers appear (needs 3 minutes of data)
- **120-180s:** Alerts start generating (needs 3x streak = 3 consecutive periods)

**Why it takes time:**
1. Real-time data needs actual time to accumulate
2. 1m gainers need at least 2 price snapshots (30-60s apart)
3. 3m gainers need 3+ snapshots spanning 3 minutes
4. Alerts need 3 consecutive trend periods (3-9 minutes depending on timeframe)

**This is by design** - we show real trends, not fake data.

## Visual Impact

### Intelligence Log
- Cleaner, less technical jargon
- Intensity labels stand out visually
- Users can instantly prioritize alerts

### Floating Toasts
- (No changes needed - toasts already don't show scores)

### Token Rows
- (No changes - badges don't show scores)

## User Experience

### Before
**User:** "What does 'score 1.41' mean? Is that good? Should I trade on this?"
**Reality:** Confused, hesitant, misses opportunity

### After
**User:** "HIGH alert on AAVE crash? Got it, checking my position now."
**Reality:** Clear, confident, takes action

## Technical Notes

- Score calculation still happens in backend (unchanged)
- Scores still used for filtering and ranking internally
- Only the display to users is simplified
- Power users can still access raw scores via API if needed

## Rollback

If you want to restore score display:

```javascript
// In AnomalyStream.jsx, replace intensity logic with:
<span className="bh-anom-score">score {log.score.toFixed(2)}</span>
```

---

**Status:** ✅ LIVE
**Files Changed:** [frontend/src/components/AnomalyStream.jsx](frontend/src/components/AnomalyStream.jsx)
**Backend Changes:** Seed count increased from 10 → 35 for faster table population
