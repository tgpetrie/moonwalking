# Sentiment Popup Reliability Fix - Verification Guide

## Changes Made

### 1. Symbol Normalization in Dashboard.jsx
- Added `normalizeSentimentSymbol()` helper function
- Converts product IDs (BTC-USD, ETH-USD) to base symbols (BTC, ETH)
- Handles multiple formats: `-USD`, `/USD`, `_USD`

### 2. Enhanced handleInfo Handler
- Now normalizes symbols before setting state
- Prevents invalid/null symbols from being passed to popup

### 3. Global Event Listener Backstop
- Added global `openInfo` event listener as failsafe
- Ensures popup opens even if `onInfo` prop isn't wired correctly
- Works in parallel with direct prop passing

### 4. Optional Debug Mode
- Set `localStorage.setItem("mw_debug_sentiment", "1")` to enable debug logs
- Tracks both Dashboard event handling and popup opening
- Remove with `localStorage.removeItem("mw_debug_sentiment")`

## Verification Checklist

### Basic Functionality
- [ ] Click info button on 1-minute gainers row → popup opens
- [ ] Click info button on 3-minute gainers row → popup opens
- [ ] Click info button on 3-minute losers row → popup opens
- [ ] Click info button on watchlist row → popup opens (if watchlist has items)
- [ ] Popup shows correct symbol in header
- [ ] Popup fetches sentiment data successfully
- [ ] No console errors during popup operation

### Symbol Format Verification
1. Open browser console
2. Run: `localStorage.setItem("mw_debug_sentiment", "1")`
3. Refresh page
4. Click any info button
5. Verify console shows:
   ```
   [sentiment] openInfo event: { raw: "BTC-USD", normalized: "BTC" }
   [SentimentPopup] Opened with symbol: BTC
   ```
6. Confirm backend receives base symbol (BTC, not BTC-USD)

### Edge Cases
- [ ] Click info on multiple different tokens rapidly
- [ ] Popup switches tokens correctly without getting stuck
- [ ] Click info, close popup, click info again → works reliably
- [ ] No duplicate popups or event listener leaks

### Backend Compatibility
- [ ] Check sentiment API endpoint accepts base symbols
- [ ] Verify `/api/sentiment/latest?symbol=BTC` works
- [ ] Verify `/api/sentiment/latest?symbol=BTC-USD` fails or auto-converts
- [ ] If backend expects product IDs, adjust normalization logic

## Files Modified

1. **frontend/src/Dashboard.jsx**
   - Added symbol normalization helper
   - Enhanced handleInfo with normalization
   - Added global openInfo event listener
   - Added optional debug logging

2. **frontend/src/components/SentimentPopupAdvanced.jsx**
   - Added debug logging on mount
   - No functional changes (already correct)

3. **frontend/src/components/TokenRowUnified.jsx**
   - No changes needed (already dispatches events correctly)

## Debug Commands

```javascript
// Enable debug mode
localStorage.setItem("mw_debug_sentiment", "1");
location.reload();

// Disable debug mode
localStorage.removeItem("mw_debug_sentiment");
location.reload();

// Test symbol normalization manually
function normalizeSentimentSymbol(input) {
  if (!input) return null;
  const s = String(input).trim().toUpperCase();
  return s.replace(/\/USD$/i, "").replace(/-USD$/i, "").replace(/_USD$/i, "");
}
console.log(normalizeSentimentSymbol("BTC-USD")); // "BTC"
console.log(normalizeSentimentSymbol("ETH/USD")); // "ETH"
console.log(normalizeSentimentSymbol("SOL_USD")); // "SOL"
```

## Known Issues & Future Improvements

### Current Limitations
- Assumes sentiment API expects base symbols (BTC vs BTC-USD)
- If API actually expects product IDs, normalization should be disabled
- Only handles USD pairs (doesn't handle BTC-EUR, etc.)

### If Popup Still Doesn't Open
1. Check browser console for errors
2. Verify TokenRowUnified dispatches `openInfo` event
3. Verify Dashboard event listener is registered
4. Check if another component is stopping event propagation
5. Verify SentimentPopupAdvanced renders when selectedSymbol is truthy

### If Backend Fetch Fails
1. Check Network tab for sentiment API requests
2. Verify symbol parameter format in request URL
3. Check backend logs for errors
4. Confirm sentiment service is running
5. Verify CORS headers if API is on different port

## Performance Notes

- Global event listener has zero overhead when not triggered
- Symbol normalization is O(1) string operation
- Debug mode localStorage check is wrapped in try/catch
- No memory leaks (event listeners cleaned up on unmount)

## Rollback Instructions

If issues arise, revert these commits:
```bash
git log --oneline frontend/src/Dashboard.jsx | head -1
git revert <commit-hash>
```

Or restore from git:
```bash
git checkout HEAD~1 frontend/src/Dashboard.jsx
git checkout HEAD~1 frontend/src/components/SentimentPopupAdvanced.jsx
```
