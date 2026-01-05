# Manual Test: Sentiment Popup Reliability

## Setup Complete ✓

The following changes have been implemented:

1. **Symbol normalization** in Dashboard.jsx
2. **Global event listener** as failsafe backstop
3. **Debug logging** (optional, enable via localStorage)

## Quick Test (5 minutes)

### Test 1: Basic Functionality
1. Open http://localhost:5173 in browser
2. Wait for dashboard to load
3. Click the info icon (ⓘ) on ANY token row in:
   - 1-minute gainers table
   - 3-minute gainers table
   - 3-minute losers table
   - Watchlist (if you have items)

**Expected:** Popup opens showing sentiment analysis

**If popup doesn't open:**
- Check browser console for errors
- Verify selectedSymbol state changes in React DevTools
- Enable debug mode (see below)

### Test 2: Symbol Format Validation
1. Open browser console (F12)
2. Run: `localStorage.setItem("mw_debug_sentiment", "1")`
3. Refresh page
4. Click any info icon
5. Look for console logs:
   ```
   [sentiment] openInfo event: { raw: "XXX", normalized: "YYY" }
   [SentimentPopup] Opened with symbol: YYY
   ```

**Expected:** Raw symbol might be "BTC-USD", normalized should be "BTC"

### Test 3: Multiple Clicks
1. Click info on token #1 → popup opens
2. Close popup
3. Click info on token #2 → popup opens with different data
4. Click info on token #3 while #2 is still open → popup switches instantly

**Expected:** No stuck popups, no duplicate popups

### Test 4: Backend Integration
1. With popup open, check Network tab
2. Look for requests to `/api/sentiment/latest?symbol=XXX`
3. Verify request completes successfully (status 200)
4. If 404 or error, check backend logs

## Debug Mode

Enable detailed logging:
```javascript
localStorage.setItem("mw_debug_sentiment", "1");
location.reload();
```

Disable:
```javascript
localStorage.removeItem("mw_debug_sentiment");
location.reload();
```

## Common Issues

### Popup doesn't open at all
1. Check if `selectedSymbol` state is being set (React DevTools)
2. Check console for JavaScript errors
3. Verify SentimentPopupAdvanced component renders
4. Check if CSS is hiding the popup (`display: none`)

### Popup opens but no data / loading forever
1. Check Network tab for failed requests
2. Verify backend URL in frontend/.env.local
3. Check if sentiment service is running
4. Verify CORS headers on backend

### Wrong symbol passed to backend
1. Enable debug mode
2. Check console logs for normalization
3. Verify backend expects base symbols (BTC) not product IDs (BTC-USD)
4. If backend needs product IDs, disable normalization

## Rollback

If you need to undo these changes:
```bash
cd /Users/cdmxx/Documents/moonwalkings
git diff frontend/src/Dashboard.jsx
git checkout HEAD frontend/src/Dashboard.jsx
git checkout HEAD frontend/src/components/SentimentPopupAdvanced.jsx
```

## Success Criteria

✓ Info button opens popup on first click
✓ Popup shows correct symbol
✓ Popup fetches data successfully
✓ No console errors
✓ Works across all tables (1m, 3m gainers, 3m losers, watchlist)
✓ Can switch between tokens smoothly
