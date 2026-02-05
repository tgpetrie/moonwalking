# CBMoovers Sentiment Popup - Quick Start Guide

## 🎯 What You're Getting

A production-ready, real-time sentiment analysis popup that:
- ✅ Aggregates data from 5+ live sources (Fear & Greed, CoinGecko, Reddit, News)
- ✅ Interactive Chart.js visualizations with 24h sentiment trends
- ✅ Clickable source verification links (builds trust)
- ✅ Smart BUY/HOLD/WAIT recommendations
- ✅ Auto-refreshes every 30 seconds
- ✅ Mobile-responsive with BHABIT design system
- ✅ Accessibility compliant (ARIA labels, keyboard navigation)
- ✅ Analytics tracking hooks (Google Analytics, Mixpanel ready)

## 📦 Files Included

```
sentiment-popup-production.html  ← Complete HTML structure
sentiment-popup-production.css   ← Use your existing sentiment-popup.css
sentiment-popup-production.js    ← Full JavaScript with real API integration
API-INTEGRATION-GUIDE.md         ← Backend API implementation guide
```

## ⚡ 5-Minute Integration

### Step 1: Copy Files

```bash
# Your project structure should look like this:
cbmoovers/
├── index.html                          # Your main dashboard
├── css/
│   ├── sentiment-popup.css             # Rename to sentiment-popup-production.css
│   └── main.css
├── js/
│   ├── sentiment-popup-production.js   # ← Copy this file
│   └── app.js
└── api/
    └── sentiment.py                    # ← Your backend (see API-INTEGRATION-GUIDE.md)
```

### Step 2: Add to Your Dashboard HTML

In your `index.html`, add these to the `<head>`:

```html
<!-- Chart.js for visualizations -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>

<!-- Sentiment Popup CSS -->
<link rel="stylesheet" href="css/sentiment-popup-production.css">
```

Before closing `</body>` tag:

```html
<!-- Sentiment Popup JS -->
<script src="js/sentiment-popup-production.js"></script>
```

### Step 3: Add the Popup HTML

Copy ONLY the overlay section from `sentiment-popup-production.html` (starting from `<div class="sentiment-overlay"...` to its closing `</div>`) and paste it right before your closing `</body>` tag.

### Step 4: Add Trigger Button

Find your existing sentiment card and add an info icon:

```html
<div class="sentiment-card">
    <div class="card-header">
        <h3>Market Sentiment</h3>
        
        <!-- ADD THIS INFO BUTTON -->
        <button class="sentiment-info-btn" 
                onclick="sentimentPopup.open()" 
                aria-label="View detailed sentiment analysis">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 16v-4M12 8h.01"/>
            </svg>
        </button>
    </div>
    
    <div class="sentiment-score">68</div>
    <!-- rest of your card -->
</div>
```

Add this CSS for the button:

```css
.sentiment-info-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(174, 75, 245, 0.1);
    border: 1px solid rgba(174, 75, 245, 0.3);
    border-radius: 6px;
    color: #ae4bf5;
    cursor: pointer;
    transition: all 200ms ease;
}

.sentiment-info-btn:hover {
    background: rgba(174, 75, 245, 0.2);
    transform: translateY(-1px);
}

.sentiment-info-btn svg {
    width: 16px;
    height: 16px;
}
```

### Step 5: Configure API Endpoint

Open `js/sentiment-popup-production.js` and update line 28:

```javascript
detectEnvironment() {
    const hostname = window.location.hostname;
    
    // Production
    if (hostname === 'cbmoovers.com' || hostname === 'www.cbmoovers.com') {
        return 'https://api.cbmoovers.com';  // ← Your production API
    }
    
    // Staging
    if (hostname === 'staging.cbmoovers.com') {
        return 'https://staging-api.cbmoovers.com';
    }
    
    // Local development
    return 'http://localhost:8001';  // ← Your local API
}
```

### Step 6: Set Up Backend API

See `API-INTEGRATION-GUIDE.md` for complete backend implementation.

Quick version:

```bash
pip install fastapi uvicorn httpx pydantic
python sentiment_api.py  # Runs on http://localhost:8001
```

### Step 7: Test

1. Open your dashboard
2. Click the info icon on your sentiment card
3. Popup should open with loading state
4. Data should populate from your API within 2-3 seconds
5. Try all 4 tabs: Overview, Live Sources, Charts, Key Insights
6. Click "Refresh Now" button
7. Press ESC or click outside to close

## 🎨 Customization

### Change Refresh Interval

```javascript
// In sentiment-popup-production.js, line 29
this.REFRESH_INTERVAL = 60000; // Change to 60 seconds (1 minute)
```

### Add Custom Source

```javascript
// In sentiment-popup-production.js, add to SOURCE_METADATA object
'Your Source Name': {
    url: 'https://yoursource.com',
    description: 'Description of your data source',
    tier: 'tier-2',  // tier-1, tier-2, or tier-3
    icon: '📊',
    weight: 0.75,
    updateFrequency: 'Real-time'
}
```

### Customize Colors

The popup uses your existing BHABIT design system colors. To tweak:

```css
/* In sentiment-popup-production.css */
:root {
    --sentiment-neg: #ae4bf5;  /* Purple for bearish */
    --sentiment-pos: #45ffb3;  /* Mint for bullish */
    --sentiment-neu: #f1b43a;  /* Orange for neutral */
}
```

## 📊 Expected API Response

Your `/sentiment/latest` endpoint should return:

```json
{
  "overall_sentiment": 0.68,
  "fear_greed_index": 62,
  "total_sources": 5,
  "timestamp": "2024-12-06T10:30:00Z",
  "source_breakdown": {
    "tier1": 2,
    "tier2": 3,
    "tier3": 0
  },
  "sources": [
    {
      "name": "Fear & Greed Index",
      "score": 62,
      "tier": 1,
      "last_update": "2024-12-06T10:30:00Z"
    }
  ],
  "sentiment_history": [
    {
      "timestamp": "2024-12-06T10:00:00Z",
      "score": 65,
      "fear_greed": 60
    }
  ]
}
```

Full schema in `API-INTEGRATION-GUIDE.md`.

## 🔧 Troubleshooting

### Popup doesn't open
- Check console for errors
- Verify `sentiment-popup-production.js` is loaded
- Ensure `#sentimentOverlay` element exists in DOM

### No data showing
- Check API endpoint in browser: `http://localhost:8001/sentiment/latest`
- Verify CORS is configured correctly
- Check browser console for fetch errors

### Charts not rendering
- Verify Chart.js CDN is loaded
- Open Charts tab while console is open to see errors
- Check that `sentiment_history` data is in correct format

### Styling looks off
- Ensure `sentiment-popup-production.css` is loaded
- Check for CSS conflicts with your main styles
- Verify Raleway font is loading

## 📈 Analytics Tracking

The popup includes built-in analytics hooks. To enable:

### Google Analytics

```html
<!-- Add to your <head> -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_MEASUREMENT_ID');
</script>
```

Events tracked automatically:
- `sentiment_popup_opened`
- `sentiment_popup_closed`
- `sentiment_tab_changed`
- `sentiment_data_loaded`
- `sentiment_manual_refresh`
- `source_link_clicked`

### Mixpanel

```html
<!-- Add to your <head> -->
<script type="text/javascript">
  (function(f,b){...mixpanel initialization...})();
  mixpanel.init("YOUR_TOKEN");
</script>
```

Same events will automatically track to Mixpanel.

## 🚀 Going to Production

1. **Update API_BASE** in `sentiment-popup-production.js`
2. **Minify files** for faster loading:
   ```bash
   npx terser sentiment-popup-production.js -o sentiment-popup-production.min.js
   npx clean-css sentiment-popup-production.css -o sentiment-popup-production.min.css
   ```
3. **Update HTML** to use `.min.js` and `.min.css`
4. **Test on staging** environment first
5. **Monitor errors** with error tracking (Sentry, LogRocket)
6. **Set up uptime monitoring** for API endpoint

## ✅ Pre-Launch Checklist

- [ ] All files copied to correct directories
- [ ] Dependencies (Chart.js) loaded
- [ ] Popup HTML added to dashboard
- [ ] Trigger button styled and functional
- [ ] API endpoint configured
- [ ] Backend API running and responding
- [ ] Tested on desktop (Chrome, Firefox, Safari)
- [ ] Tested on mobile (iOS Safari, Android Chrome)
- [ ] All 4 tabs displaying correctly
- [ ] Auto-refresh working
- [ ] Source links verified and clickable
- [ ] Analytics tracking enabled
- [ ] Error handling tested (try with API offline)

## 📚 Additional Resources

- **API Documentation**: See `API-INTEGRATION-GUIDE.md`
- **Design System**: Uses existing BHABIT colors/typography
- **Chart.js Docs**: https://www.chartjs.org/docs/latest/
- **Accessibility**: WCAG 2.1 AA compliant

## 🆘 Need Help?

Common issues and solutions:

1. **"Overlay element not found"**
   → Make sure you copied the entire `<div class="sentiment-overlay">` block

2. **"API returned 404"**
   → Check that your backend is running on the configured port

3. **"Charts not animating"**
   → Clear browser cache, verify Chart.js CDN is accessible

4. **"Data shows but looks wrong"**
   → Verify your API response matches the expected format

---

**You're all set!** 🎉

Your sentiment popup is now:
- ✅ Pulling real-time data from multiple sources
- ✅ Providing actionable insights to users
- ✅ Building trust with source verification links
- ✅ Positioning CBMoovers as a serious market intelligence tool
- ✅ Funneling users toward your premium BHABIT ecosystem

This is the **"intelligent gateway drug"** we discussed - giving users so much value upfront that they'll want more of what BHABIT has to offer.
