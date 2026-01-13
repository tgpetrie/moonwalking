# Alert System Reference

Complete alert type reference matching backend `moonwalking_alert_system.py`.

## Alert Types

All alerts display with consistent icons, labels, and colors across:
- Intelligence Log (AnomalyStream)
- Token Row badges
- Floating notifications

### Alert Type Configuration

| Icon | Type | Label | Color | Description |
|------|------|-------|-------|-------------|
| 🚀 | MOONSHOT | MOONSHOT | Green `#10b981` | Massive pump detected |
| 📉 | CRATER | CRATER | Dark Red `#dc2626` | Major dump detected |
| 🌊 | SENTIMENT_SPIKE | SENTIMENT | Blue `#3b82f6` | Social sentiment explosion |
| 🐋 | WHALE_MOVE | WHALE | Cyan `#06b6d4` | Large volume anomaly |
| ⚖️ | DIVERGENCE | DIVERGENCE | Purple `#a855f7` | Price vs sentiment mismatch |
| 📈 | BREAKOUT | BREAKOUT | Amber `#f59e0b` | Technical breakout |
| 🔥 | FOMO_ALERT | FOMO | Red `#ef4444` | FOMO/Fear spike detected |
| 👤 | STEALTH_MOVE | STEALTH | Indigo `#6366f1` | Quiet accumulation |
| 📰 | NEWS_CATALYST | NEWS | Violet `#8b5cf6` | News-driven movement |
| 💰 | ARBITRAGE | ARBITRAGE | Teal `#14b8a6` | Cross-exchange opportunity |

### Severity Levels

| Icon | Severity | Color | CSS Tone |
|------|----------|-------|----------|
| 🔴 | CRITICAL | Red `#dc2626` | tone-red |
| 🟠 | HIGH | Orange-Red `#ef4444` | tone-orange |
| 🟡 | MEDIUM | Amber `#f59e0b` | tone-gold |
| 🟢 | LOW | Blue `#3b82f6` | tone-cyan |
| 🔵 | INFO | Gray `#6b7280` | tone-mint |

## Implementation Files

### Unified Configuration
- **`frontend/src/config/alertConfig.js`** - Single source of truth for all alert types

### Components Using Alerts
1. **`frontend/src/components/AnomalyStream.jsx`** - Intelligence Log
2. **`frontend/src/components/TokenRowUnified.jsx`** - Token row badges
3. **`frontend/src/components/FloatingAlertContainer.jsx`** - Toast notifications

### Backend Source
- **`backend/moonwalking_alert_system.py`** - Alert type enum definitions

## Example Display

### Intelligence Log
```
[14:32:45] 🚀 MOONSHOT BTC-USD Massive pump detected score 0.85 [Trade]
[14:32:12] 🌊 SENTIMENT ETH-USD Social sentiment explosion score 0.72 [Trade]
[14:31:58] ⚖️ DIVERGENCE DOGE-USD Price vs sentiment mismatch score 0.68 [Trade]
```

### Token Row Badge
```
┌─────────────────────────────────────┐
│ 🔥 FOMO  1  BTC-USD  $45,234  +5.2% │ ← Pulsing red glow
└─────────────────────────────────────┘
```

### Floating Notification
```
┌──────────────────────────────────────┐
│ 🐋 WHALE                         × │
│ ETH-USD                             │
│ Large volume anomaly detected       │
│ 🕐 2m ago          85% confidence    │
└──────────────────────────────────────┘
```

## Color Coding Strategy

- **Alert Type** colors take priority over severity colors
- **Green** = Bullish momentum (MOONSHOT)
- **Red** = Bearish momentum (CRATER, FOMO)
- **Blue** = Sentiment-driven (SENTIMENT_SPIKE)
- **Purple** = Divergence signals (DIVERGENCE)
- **Amber/Orange** = Breakout/Technical (BREAKOUT)
- **Cyan** = Volume anomalies (WHALE)
- **Indigo** = Stealth moves (STEALTH_MOVE)
- **Violet** = News catalysts (NEWS_CATALYST)
- **Teal** = Arbitrage opportunities (ARBITRAGE)

## Glass Morphism Styling

All alert displays use consistent glass morphism:
- Dark semi-transparent backgrounds (`rgba(0, 0, 0, 0.3-0.9)`)
- Backdrop blur (`blur(8px-16px)`)
- Colored borders matching alert type
- Subtle glow effects with alert color
- Smooth animations (2-3s pulse cycles)
