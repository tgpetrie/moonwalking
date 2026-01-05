# 1-Minute Gainers: Intelligent Smooth Reordering

## Overview

The 1-minute gainers table now uses an intelligent reordering system that balances responsiveness with stability. It catches rockets fast without feeling twitchy or chaotic.

## How It Works

### Core Techniques

1. **EMA Smoothing** - Exponential Moving Average of % change reduces noise
2. **Min-Stay Lock** - Rows stay visible for minimum time after appearing
3. **Hysteresis Swaps** - Position changes require beating incumbent by margin
4. **Vanish Grace** - Recently-visible coins don't disappear instantly
5. **Commit Cadence** - UI updates on controlled rhythm, not every tick
6. **Buffer Rows** - Extra candidates beyond visible prevent cutoff thrashing

### Two Modes

**Smooth (Default)**
- Balanced feel: fast enough to catch moves, stable enough to read
- Good for most users who want live updates without sensory overload
- Updates ~650ms, min-stay ~2.2s, swap margin 0.18%

**Predator (Optional)**
- Aggressive timing for traders who want immediate response
- Tighter locks, faster commits, more bubble passes
- Updates ~280ms, min-stay ~0.9s, swap margin 0.08%

## Usage

### Enable Predator Mode

```javascript
// In browser console or app code:
localStorage.setItem("mw_1m_mode", "predator");
location.reload();
```

### Switch Back to Smooth

```javascript
localStorage.setItem("mw_1m_mode", "smooth");
location.reload();
```

### Enable Debug Logging

```javascript
localStorage.setItem("mw_debug_1m", "1");
location.reload();
```

You'll see logs like:
```
[1m] mode=smooth scored=45 grace=2 desired=16
[1m] commit: BTC:5.23 ETH:4.91 SOL:3.45 MATIC:2.88 AVAX:2.34
```

### Disable Debug

```javascript
localStorage.removeItem("mw_debug_1m");
location.reload();
```

## Mode Comparison

| Feature | Smooth | Predator |
|---------|--------|----------|
| EMA Alpha | 0.30 | 0.55 |
| Commit Interval | 650ms | 280ms |
| Min Stay | 2200ms | 900ms |
| Swap Margin | 0.18% | 0.08% |
| Bubble Passes | 2 | 4 |
| Vanish Grace | 1600ms | 800ms |
| Feel | River | Strobe |

## Behavior Examples

### Smooth Mode (Default)

**Scenario: BTC spikes from +2% to +5%**
- EMA smooths: 2.0 → 2.9 → 3.8 → 4.5
- Rises within ~2 seconds
- Doesn't jump on brief noise spike

**Scenario: SHIB drops from +3% to +1%**
- Min-stay lock keeps it visible for 2.2s
- Vanish grace gives it 1.6s more if it drops out
- Total: ~4s before disappearing (not instant cut)

### Predator Mode

**Scenario: BTC spikes from +2% to +5%**
- EMA reacts faster: 2.0 → 3.7 → 4.8
- Rises within ~0.5 seconds
- May jump on brief spikes

**Scenario: SHIB drops from +3% to +1%**
- Min-stay lock keeps it 0.9s
- Vanish grace gives 0.8s more
- Total: ~1.7s before disappearing (quick cut)

## Technical Details

### EMA Calculation

```javascript
ema = prevEma * (1 - alpha) + currentPct * alpha
```

- Lower alpha = smoother, slower to react
- Higher alpha = more reactive, tracks raw changes

### Hysteresis Swaps

Challenger at position i+1 must beat incumbent at i by margin:

```javascript
if (scoreChallenger - scoreIncumbent > swapMargin) {
  swap(i, i+1);
}
```

This prevents tiny float differences from causing churn.

### Vanish Grace Period

When a coin drops out of feed but was recently visible:

```javascript
if (now - lastSeenAt < vanishGraceMs) {
  includeWithDecayedScore(ema * 0.92);
}
```

This makes the board feel continuous instead of blink-cut.

### Commit Cadence

UI updates happen at controlled intervals:

```javascript
setInterval(() => {
  const nextRows = computeStableRanking();
  if (signatureChanged(nextRows)) {
    setDisplayRows(nextRows);
  }
}, commitMs);
```

Prevents runaway updates when data changes rapidly.

## Performance

- **CPU**: Chill, even with 50+ tokens in feed
- **Memory**: Auto-prunes meta map (2min TTL)
- **No React Key Warnings**: Proper identity tracking
- **No Event Listener Leaks**: All refs cleaned up

## Troubleshooting

### Table feels too slow (smooth mode)
Try predator mode:
```javascript
localStorage.setItem("mw_1m_mode", "predator");
location.reload();
```

### Table feels too twitchy (predator mode)
Switch to smooth:
```javascript
localStorage.setItem("mw_1m_mode", "smooth");
location.reload();
```

### Rows jumping around randomly
1. Enable debug mode
2. Check console for score values
3. Verify EMA is being computed (not raw % bouncing)
4. Check swap margin is being applied

### Rows disappearing too fast
- Smooth mode: 2.2s lock + 1.6s grace = ~3.8s total
- Predator mode: 0.9s lock + 0.8s grace = ~1.7s total
- If still too fast, consider custom preset

## Custom Presets

You can add your own preset by editing the PRESETS object in GainersTable1Min.jsx:

```javascript
const PRESETS = {
  smooth: { ... },
  predator: { ... },
  custom: {
    alpha: 0.40,
    commitMs: 500,
    minStayMs: 1500,
    swapMargin: 0.12,
    bubblePasses: 3,
    vanishGraceMs: 1200,
    bufferRows: 7,
    spring: { type: "spring", stiffness: 600, damping: 38, mass: 0.85 },
  },
};
```

Then set:
```javascript
localStorage.setItem("mw_1m_mode", "custom");
location.reload();
```

## Files Modified

- **frontend/src/components/GainersTable1Min.jsx**
  - Enhanced preset system with smooth/predator modes
  - Added vanish grace period
  - Improved EMA scoring
  - Applied spring config from preset
  - Added debug logging

## Implementation Notes

### Why EMA instead of raw %?

Raw % bounces on every tick:
```
Raw: 2.1 → 5.2 → 1.8 → 4.5 → 2.3 → 6.1
EMA: 2.1 → 3.0 → 2.6 → 3.2 → 2.9 → 4.0
```

EMA smooths out noise while still tracking genuine moves.

### Why min-stay locks?

Without locks, coins can churn in/out rapidly:
```
Frame 1: BTC ETH SOL MATIC AVAX
Frame 2: BTC ETH LINK MATIC AVAX  (SOL dropped, LINK in)
Frame 3: BTC ETH SOL MATIC AVAX   (SOL back, LINK out)
Frame 4: BTC ETH LINK MATIC AVAX  (SOL out again!)
```

With 2.2s lock, once SOL appears, it stays minimum 2.2s.

### Why hysteresis margin?

Prevents micro-swaps from float precision:
```
Without margin:
Position 3: AVAX 3.1234%
Position 4: MATIC 3.1235%  → swap!
Next frame:
Position 3: MATIC 3.1233%
Position 4: AVAX 3.1234%   → swap back!
```

With 0.18% margin, MATIC needs 3.30%+ to swap.

### Why vanish grace?

Coins can temporarily drop below threshold due to network blips or backend processing. Grace period prevents:
```
Frame 1: [BTC ETH SOL]
Frame 2: [BTC ETH ---]  ← SOL vanished instantly
Frame 3: [BTC ETH SOL]  ← SOL back (confusing!)
```

With grace, SOL stays visible through brief dropouts.

## Acceptance Criteria

✓ Reorders no faster than commitMs (smooth: 650ms, predator: 280ms)
✓ Rows don't pop in/out when % is near threshold
✓ Genuine rockets rise within 1-2 seconds (smooth) or <1s (predator)
✓ No React key warnings
✓ No memory leaks (auto-prunes every 2 minutes)
✓ CPU stays chill
✓ Mode persists across refreshes
✓ Debug mode works without affecting performance

## Future Improvements

Potential enhancements (not implemented):

1. **Visual mode indicator**: Show "SMOOTH" or "PREDATOR" badge
2. **UI toggle**: Button to switch modes without console
3. **Keyboard shortcut**: Shift+P to toggle smooth/predator
4. **Per-user preference**: Save mode to backend user profile
5. **Auto-detect**: Switch to predator during high volatility
6. **Custom preset UI**: Let users tune parameters in settings

## Related Files

- `/frontend/src/Dashboard.jsx` - Sentiment popup fix
- `/frontend/src/components/TokenRowUnified.jsx` - Row rendering
- `/frontend/src/hooks/useDataFeed.js` - Data source
