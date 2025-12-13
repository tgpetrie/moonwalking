# Advanced Sentiment Popup - Cheat Sheet

## 🚀 Installation (30 seconds)

```bash
cd frontend
npm install
```

## 📥 Import CSS (add to src/main.jsx or src/App.jsx)

```javascript
import './styles/sentiment-popup-advanced.css';
```

## 🎯 Basic Usage

```jsx
import SentimentTriggerButton from './components/SentimentTriggerButton';

// Add anywhere:
<SentimentTriggerButton symbol="BTC" />
```

## 📍 Common Integration Points

### In Header
```jsx
<header>
  <h1>CBMoovers</h1>
  <SentimentTriggerButton />
</header>
```

### In Sentiment Card
```jsx
<div className="card-header">
  <h3>Sentiment</h3>
  <SentimentTriggerButton symbol={symbol} />
</div>
```

### In Insights Panel (Market Mood Tab)
```jsx
// Replace import:
import InsightsPanel from './components/InsightsPanelWithSentiment';
```

### Standalone
```jsx
import { useState } from 'react';
import SentimentPopupAdvanced from './components/SentimentPopupAdvanced';

function Custom() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Sentiment</button>
      <SentimentPopupAdvanced isOpen={open} onClose={() => setOpen(false)} />
    </>
  );
}
```

## 🎨 Customize Colors

Edit `frontend/src/styles/sentiment-popup-advanced.css`:

```css
:root {
    --sentiment-pos: #45ffb3;   /* Bullish (green) */
    --sentiment-neu: #f1b43a;   /* Neutral (gold) */
    --sentiment-neg: #ae4bf5;   /* Bearish (purple) */
}
```

## 📊 Data Sources

Edit `SentimentPopupAdvanced.jsx`:

```javascript
const SOURCE_METADATA = {
  'Your Source': {
    url: 'https://example.com',
    description: 'Description',
    tier: 'tier-1',  // tier-1, tier-2, or tier-3
    icon: '🔥',
    weight: 0.85,
    updateFrequency: 'Real-time'
  }
};
```

## 🔧 Props Reference

### SentimentTriggerButton
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `symbol` | string | `'BTC'` | Asset symbol |
| `className` | string | `''` | Additional CSS classes |

### SentimentPopupAdvanced
| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `isOpen` | boolean | ✅ | Controls visibility |
| `onClose` | function | ✅ | Close handler |
| `symbol` | string | ❌ | Asset symbol (default: 'BTC') |

## ⌨️ Keyboard Shortcuts

- **ESC** - Close popup
- **Tab** - Navigate elements

## 📱 Responsive Breakpoints

- **Desktop**: 700px+
- **Tablet**: 480px - 700px
- **Mobile**: < 480px

## 🎯 Tab Structure

1. **Overview** - Stats, gauge, top insight
2. **Live Sources** - Source cards with links
3. **Charts** - 4 Chart.js visualizations
4. **Key Insights** - AI analysis

## 🔍 Troubleshooting

### Charts not showing?
```bash
npm install chart.js@^4.4.0
```

### Styles broken?
```javascript
// Add to main file:
import './styles/sentiment-popup-advanced.css';
```

### Data not loading?
```bash
# Check backend running:
curl http://localhost:8001/sentiment/latest
```

## 📂 File Locations

```
frontend/src/
├── components/
│   ├── SentimentPopupAdvanced.jsx       ← Main popup
│   ├── SentimentTriggerButton.jsx       ← Button
│   └── InsightsPanelWithSentiment.jsx   ← Example
└── styles/
    └── sentiment-popup-advanced.css      ← All styles
```

## 📚 Documentation

- **Quick Start**: [QUICK-START.md](./QUICK-START.md)
- **Full Guide**: [INTEGRATION-GUIDE.md](./INTEGRATION-GUIDE.md)
- **Overview**: [SENTIMENT-POPUP-README.md](./SENTIMENT-POPUP-README.md)
- **Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)

## 🎨 Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Mint Green | `#45ffb3` | Bullish, Tier 1 |
| Gold | `#f1b43a` | Neutral, Tier 2 |
| Purple | `#ae4bf5` | Bearish, Tier 3 |
| Teal | `#00d4aa` | Absolute values |
| Pink | `#ff6b9d` | Alerts |

## 📊 Data Format Expected

```javascript
{
  overall: 0.68,                    // 0-1 (shown as 0-100)
  fearGreedIndex: 62,               // 0-100
  sourceBreakdown: {
    tier1: 2, tier2: 3, tier3: 0
  },
  socialBreakdown: {
    reddit: 0.72, twitter: 0.65
  },
  sentimentHistory: [
    {
      timestamp: "2025-12-06T10:00:00Z",
      sentiment: 0.68,
      fearGreed: 62,
      price: 45000
    }
  ]
}
```

## 🧪 Testing Checklist

- [ ] Button renders
- [ ] Popup opens on click
- [ ] ESC closes popup
- [ ] All 4 tabs work
- [ ] Charts render
- [ ] Data loads
- [ ] Refresh works
- [ ] Links open
- [ ] Mobile responsive

## ⚡ Performance Tips

1. **Lazy load**: Import with `React.lazy()` if needed
2. **Chart cleanup**: Automatic on unmount
3. **SWR caching**: 30-second TTL
4. **Conditional render**: Only active tab visible

## 🔐 Security

✅ All HTML sanitized
✅ External links use `rel="noopener noreferrer"`
✅ No inline event handlers
✅ React automatic XSS protection

## 🌐 Browser Support

✅ Chrome 90+
✅ Firefox 88+
✅ Safari 14+
✅ Edge 90+
❌ IE11 (not supported)

## 💡 Pro Tips

1. **Multiple symbols**: Pass different `symbol` prop to each button
2. **Custom styling**: Use `className` prop + CSS specificity
3. **Analytics**: Add tracking to `onClose` handler
4. **Auto-refresh**: Add interval in useEffect when popup is open

## 📞 Quick Links

- **Chart.js Docs**: https://www.chartjs.org/docs/latest/
- **React Hooks**: https://react.dev/reference/react/hooks
- **SWR Docs**: https://swr.vercel.app/

## ✨ Features at a Glance

✅ 4 interactive tabs
✅ Chart.js visualizations
✅ Real-time data
✅ Glass morphism UI
✅ Fully responsive
✅ Keyboard accessible
✅ Zero backend changes
✅ Drop-in ready

## 🎉 That's It!

You're ready to use the advanced sentiment popup. Happy coding! 🚀
