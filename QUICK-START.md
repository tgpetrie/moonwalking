# Advanced Sentiment Popup - Quick Start

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies (30 seconds)

```bash
cd /Users/cdmxx/Documents/moonwalkings/frontend
npm install
```

This installs Chart.js which has been added to your `package.json`.

### Step 2: Import CSS (10 seconds)

Add this line to your main entry file (`src/main.jsx` or `src/App.jsx`):

```javascript
import './styles/sentiment-popup-advanced.css';
```

For example, in `src/main.jsx`:

```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import './styles/sentiment-popup-advanced.css';  // ← Add this line

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### Step 3: Add the Button Anywhere (1 minute)

```javascript
import SentimentTriggerButton from './components/SentimentTriggerButton';

function YourComponent() {
  return (
    <div>
      {/* Your existing content */}
      <SentimentTriggerButton symbol="BTC" />
    </div>
  );
}
```

**That's it!** Click the button and the advanced sentiment popup will appear. 🎉

---

## 📍 Where to Add It

### Option A: In Your Sentiment Card Header

```jsx
// In any sentiment display component
<div className="card-header flex items-center justify-between">
  <h3>Market Sentiment</h3>
  <SentimentTriggerButton symbol="BTC" />
</div>
```

### Option B: In Your Insights Panel "Market Mood" Tab

Replace your existing `InsightsPanel.jsx` import with the enhanced version:

```javascript
// In your main file where InsightsPanel is used
import InsightsPanel from './components/InsightsPanelWithSentiment';
```

I've already created `InsightsPanelWithSentiment.jsx` which includes the sentiment button in the "Market Mood" tab.

### Option C: In Your Navigation/Header

```jsx
<header className="app-header">
  <h1>CBMoovers</h1>
  <div className="header-actions">
    <SentimentTriggerButton />
  </div>
</header>
```

### Option D: In Your Gainers Table

Add a column with info icons:

```jsx
// In GainersTable or similar
<td>
  <SentimentTriggerButton symbol={row.symbol} />
</td>
```

---

## 🎨 What You Get

### 4 Interactive Tabs

1. **Overview** - Stats grid, animated gauge, top insight
2. **Live Sources** - Clickable source cards (Fear & Greed, Reddit, Twitter, News)
3. **Charts** - Sentiment trends, source breakdown, correlation with price
4. **Key Insights** - AI-generated market analysis

### Features

✅ Real-time data from your backend (`/sentiment/latest`)
✅ Chart.js visualizations
✅ Glass morphism UI matching BHABIT theme
✅ Keyboard shortcuts (ESC to close)
✅ Fully responsive
✅ Accessibility features (ARIA labels, keyboard navigation)
✅ Auto-refresh on manual click

---

## 🔧 Customization

### Change Colors

Edit `frontend/src/styles/sentiment-popup-advanced.css`:

```css
:root {
    --sentiment-pos: #45ffb3;   /* Bullish - currently mint green */
    --sentiment-neu: #f1b43a;   /* Neutral - currently gold */
    --sentiment-neg: #ae4bf5;   /* Bearish - currently purple */
}
```

### Add/Remove Data Sources

Edit the `SOURCE_METADATA` object in `SentimentPopupAdvanced.jsx`:

```javascript
const SOURCE_METADATA = {
  'Your Custom Source': {
    url: 'https://example.com',
    description: 'Description here',
    tier: 'tier-1',
    icon: '🔥',
    weight: 0.85
  }
};
```

---

## 📊 Data Requirements

The popup works with your existing backend at `/sentiment/latest`. Expected format:

```json
{
  "overall": 0.68,
  "fearGreedIndex": 62,
  "sourceBreakdown": { "tier1": 2, "tier2": 3, "tier3": 0 },
  "socialBreakdown": { "reddit": 0.72, "twitter": 0.65 },
  "sentimentHistory": [
    { "timestamp": "2025-12-06T10:00:00Z", "sentiment": 0.68, "price": 45000 }
  ]
}
```

✅ Your backend already provides this via `useSentimentLatest` hook
✅ Data is normalized by your `normalizeSentiment` adapter
✅ No backend changes needed!

---

## 🐛 Troubleshooting

### Charts not showing?

```bash
npm list chart.js
# Should show: chart.js@4.4.0

# If not:
npm install chart.js@^4.4.0
```

### Popup not styling correctly?

Make sure CSS is imported in your main file:

```javascript
import './styles/sentiment-popup-advanced.css';
```

### Data not loading?

Check your backend is running and `/sentiment/latest` returns data:

```bash
curl http://localhost:8001/sentiment/latest
```

---

## 📚 Full Documentation

For advanced usage, see [INTEGRATION-GUIDE.md](./INTEGRATION-GUIDE.md)

---

## 🎯 Example: Complete Integration

Here's a complete example adding it to your app header:

```jsx
// src/App.jsx
import React from 'react';
import './index.css';
import './styles/sentiment-popup-advanced.css';
import SentimentTriggerButton from './components/SentimentTriggerButton';

function App() {
  return (
    <div className="app">
      <header className="header">
        <h1>CBMoovers Dashboard</h1>
        <nav>
          <SentimentTriggerButton />
        </nav>
      </header>

      <main>
        {/* Your existing dashboard */}
      </main>
    </div>
  );
}

export default App;
```

---

## ✅ Checklist

- [ ] Run `npm install`
- [ ] Import CSS in main file
- [ ] Add `<SentimentTriggerButton />` somewhere
- [ ] Test the popup opens
- [ ] Check data loads from backend
- [ ] Customize colors if needed

**You're done!** Enjoy your advanced sentiment UI. 🚀

---

## 🎬 What Happens When You Click

1. **Popup opens** with smooth animation
2. **Data loads** from your backend via `useSentimentLatest`
3. **Overview tab shows**: Overall score, Fear & Greed, source counts, animated gauge
4. **Charts tab**: Interactive Chart.js visualizations
5. **Sources tab**: Clickable cards with live data sources
6. **Insights tab**: AI-generated market analysis

All using your **real backend data** with **zero backend changes required**.
