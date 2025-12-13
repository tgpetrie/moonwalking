# Advanced Sentiment Popup - Integration Guide

## Overview

This guide shows you how to integrate the advanced sentiment analysis popup into your CBMoovers/BHABIT application.

## What's Included

### New Components

1. **SentimentPopupAdvanced.jsx** - Main popup component with 4 tabs:
   - Overview (stats, gauge, top insights)
   - Live Sources (clickable source cards with metadata)
   - Charts (Chart.js visualizations: trend, breakdown, correlation)
   - Key Insights (AI-generated analysis)

2. **SentimentTriggerButton.jsx** - Reusable trigger button

3. **sentiment-popup-advanced.css** - Complete styling (glass morphism, purple/teal/gold theme)

### Dependencies Added

- `chart.js@^4.4.0` - For interactive charts

## Installation

### Step 1: Install Dependencies

```bash
cd frontend
npm install
```

This will install Chart.js which was added to your `package.json`.

### Step 2: Import CSS in Your Main File

Add this to your main entry point (e.g., `src/main.jsx` or `src/App.jsx`):

```javascript
import './styles/sentiment-popup-advanced.css';
```

## Usage Examples

### Option 1: Add to Existing Sentiment Card

Update your existing sentiment card header to include the trigger button:

```jsx
import SentimentTriggerButton from './components/SentimentTriggerButton';

function YourSentimentCard() {
  return (
    <div className="sentiment-card">
      <div className="card-header flex justify-between items-center">
        <h3>Market Sentiment</h3>
        <SentimentTriggerButton symbol="BTC" />
      </div>
      {/* Rest of your sentiment card */}
    </div>
  );
}
```

### Option 2: Add to InsightsPanel

Integrate into your insights tab:

```jsx
// In InsightsPanel.jsx
import SentimentTriggerButton from './components/SentimentTriggerButton';

function InsightsPanel() {
  return (
    <div className="insights-panel">
      <div className="section-header">
        <h2>Market Mood</h2>
        <SentimentTriggerButton />
      </div>
      {/* Your existing content */}
    </div>
  );
}
```

### Option 3: Add to MetricsPanel Sentiment Tab

```jsx
// In MetricsPanel.jsx
import SentimentTriggerButton from './components/SentimentTriggerButton';

function MetricsPanel() {
  return (
    <div className="metrics-panel">
      {/* ... */}
      <div className="sentiment-tab">
        <div className="tab-header">
          <span>Sentiment</span>
          <SentimentTriggerButton symbol={activeSymbol} />
        </div>
        <SentimentCard />
      </div>
    </div>
  );
}
```

### Option 4: Add to GainersTable Rows

Add an info icon to each row in your gainers table:

```jsx
// In GainersTable1Min.clean.jsx
import SentimentTriggerButton from './components/SentimentTriggerButton';

function GainersTableRow({ symbol, ...rest }) {
  return (
    <tr>
      <td>{symbol}</td>
      <td>{/* price data */}</td>
      <td>{/* volume data */}</td>
      <td>
        <SentimentTriggerButton symbol={symbol} className="inline-flex" />
      </td>
    </tr>
  );
}
```

### Option 5: Standalone Integration

Use the popup directly anywhere in your app:

```jsx
import { useState } from 'react';
import SentimentPopupAdvanced from './components/SentimentPopupAdvanced';

function MyComponent() {
  const [showSentiment, setShowSentiment] = useState(false);

  return (
    <>
      <button onClick={() => setShowSentiment(true)}>
        View Sentiment Analysis
      </button>

      <SentimentPopupAdvanced
        isOpen={showSentiment}
        onClose={() => setShowSentiment(false)}
        symbol="BTC"
      />
    </>
  );
}
```

## Data Integration

### How It Works with Your Existing Backend

The component uses your existing `useSentimentLatest` hook, which fetches from `/sentiment/latest`. The data is automatically normalized by your `normalizeSentiment` adapter.

### Expected Data Format

The component expects this structure (already provided by your backend):

```javascript
{
  overall: 0.68,                    // 0-1 range (converted to 0-100 for display)
  fearGreedIndex: 62,               // 0-100
  sourceBreakdown: {
    tier1: 2,
    tier2: 3,
    tier3: 0
  },
  socialBreakdown: {
    reddit: 0.72,
    twitter: 0.65,
    telegram: 0.78,
    news: 0.70
  },
  sentimentHistory: [
    {
      timestamp: "2025-12-06T10:00:00Z",
      sentiment: 0.68,
      fearGreed: 62,
      price: 45000
    }
    // ... more history points
  ],
  timestamp: "2025-12-06T12:00:00Z"
}
```

### If Your Data Structure Differs

If your backend returns data in a different format, you can either:

1. **Update the normalizeSentiment adapter** (recommended):
   ```javascript
   // In frontend/src/adapters/normalizeSentiment.js
   export function normalizeSentiment(raw) {
     // Map your backend structure to the expected format
   }
   ```

2. **Create a custom hook wrapper**:
   ```javascript
   // In a new file: useSentimentAdvanced.js
   import useSentimentLatest from './useSentimentLatest';

   export default function useSentimentAdvanced(symbol) {
     const { data, ...rest } = useSentimentLatest(symbol);

     // Transform data to match popup expectations
     const transformedData = data ? {
       overall: data.yourOverallField,
       fearGreedIndex: data.yourFGField,
       // ... etc
     } : null;

     return { data: transformedData, ...rest };
   }
   ```

## Customization

### Color Scheme

Edit CSS variables in `sentiment-popup-advanced.css`:

```css
:root {
    --sentiment-pos: #45ffb3;   /* Bullish color */
    --sentiment-neu: #f1b43a;   /* Neutral color */
    --sentiment-neg: #ae4bf5;   /* Bearish color */
}
```

### Source Metadata

Edit the `SOURCE_METADATA` object in `SentimentPopupAdvanced.jsx` to:
- Add new data sources
- Update URLs
- Change tier classifications
- Modify weights

```javascript
const SOURCE_METADATA = {
  'Your Custom Source': {
    url: 'https://example.com',
    description: 'Description of your source',
    tier: 'tier-1',
    icon: '🔥',
    weight: 0.80,
    updateFrequency: 'Real-time'
  },
  // ... existing sources
};
```

### Tab Content

To add/remove tabs, edit the tab navigation in `SentimentPopupAdvanced.jsx`:

```jsx
<button
  className={`tab-btn ${activeTab === 'newtab' ? 'active' : ''}`}
  onClick={() => setActiveTab('newtab')}
>
  <svg>...</svg>
  New Tab
</button>

{/* Then add corresponding content */}
{activeTab === 'newtab' && (
  <section className="tab-panel active">
    {/* Your custom content */}
  </section>
)}
```

## Chart Customization

### Modify Chart Styles

Edit the chart initialization functions in `SentimentPopupAdvanced.jsx`:

```javascript
const initTrendChart = () => {
  chartInstancesRef.current.trend = new ChartJS(canvas, {
    type: 'line',
    data: {
      // Your data
    },
    options: {
      // Customize colors, fonts, scales, etc.
      plugins: {
        legend: {
          labels: {
            color: '#yourcolor',
            font: { family: 'YourFont' }
          }
        }
      }
    }
  });
};
```

### Add New Charts

1. Create a new ref: `const newChartRef = useRef(null);`
2. Add canvas to JSX: `<canvas ref={newChartRef} />`
3. Initialize in `initCharts()` function
4. Clean up in useEffect cleanup

## Performance Optimization

### Lazy Loading

For better initial load times, lazy load the popup:

```javascript
import { lazy, Suspense } from 'react';

const SentimentPopupAdvanced = lazy(() => import('./components/SentimentPopupAdvanced'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <SentimentPopupAdvanced ... />
    </Suspense>
  );
}
```

### Chart Memory Management

Charts are automatically destroyed when:
- The component unmounts
- The user switches away from the Charts tab

This prevents memory leaks.

## Keyboard Shortcuts

The popup already supports:
- **ESC** - Close popup
- **Tab navigation** - Navigate between tabs and interactive elements

## Accessibility

The component includes:
- ARIA labels and roles
- Keyboard navigation support
- Screen reader announcements
- Focus management

## Troubleshooting

### Charts Not Displaying

1. **Check console for errors**: Chart.js registration issues
2. **Verify Chart.js installed**: `npm list chart.js`
3. **Check canvas refs**: Ensure refs are properly attached

### Data Not Loading

1. **Check network tab**: Is `/sentiment/latest` returning data?
2. **Verify hook**: Is `useSentimentLatest` working in other components?
3. **Check normalization**: Is data structure matching expectations?

### Styling Issues

1. **CSS not imported**: Add `import './styles/sentiment-popup-advanced.css'` to main file
2. **Z-index conflicts**: Popup uses `z-index: 9999`
3. **Font loading**: Ensure Raleway font is loaded in your app

### Chart.js Errors

```bash
# Reinstall if needed
npm uninstall chart.js
npm install chart.js@^4.4.0
```

## Example: Full Integration in App.jsx

```jsx
import React from 'react';
import './styles/sentiment-popup-advanced.css';
import SentimentTriggerButton from './components/SentimentTriggerButton';

function App() {
  return (
    <div className="app">
      <header>
        <h1>CBMoovers Dashboard</h1>
        <div className="header-actions">
          <SentimentTriggerButton symbol="BTC" />
        </div>
      </header>

      <main>
        {/* Your existing dashboard components */}
      </main>
    </div>
  );
}

export default App;
```

## Next Steps

1. **Run `npm install`** to install Chart.js
2. **Import the CSS** in your main file
3. **Choose an integration option** from the examples above
4. **Test with your live data** from the backend
5. **Customize** colors, sources, and content as needed

## Support & Resources

- Chart.js Docs: https://www.chartjs.org/docs/latest/
- Your Backend API: `http://localhost:8001/sentiment/latest`
- Existing Components: `frontend/src/components/cards/SentimentPanel.jsx`

## Advanced Features

### Add Auto-Refresh

The component already refreshes on manual button click. To add auto-refresh when open:

```javascript
useEffect(() => {
  if (!isOpen) return;

  const interval = setInterval(() => {
    refresh();
  }, 30000); // 30 seconds

  return () => clearInterval(interval);
}, [isOpen, refresh]);
```

### Track Analytics

Add tracking when popup opens:

```javascript
const handleOpen = () => {
  setIsPopupOpen(true);

  // Track with your analytics
  if (typeof gtag !== 'undefined') {
    gtag('event', 'sentiment_popup_opened', {
      symbol: symbol
    });
  }
};
```

## Summary

You now have a **production-ready, advanced sentiment analysis popup** that:

✅ Integrates seamlessly with your existing backend
✅ Uses your existing data hooks (`useSentimentLatest`)
✅ Matches your BHABIT design system
✅ Includes Chart.js visualizations
✅ Has 4 information-rich tabs
✅ Is fully accessible and responsive
✅ Requires minimal setup (just install and import)

Enjoy your enhanced sentiment UI! 🚀
