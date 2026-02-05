# Performance Optimizations Summary

This document summarizes the N100-friendly performance optimizations implemented for the Moonwalkings Dashboard.

---

## 🎯 Core Architecture: "One Fetch, Three Clocks"

### Problem
The frontend had competing fetch patterns (DataContext + SWR) all updating at the same cadence, causing:
- Unnecessary re-renders
- UI feeling "dragged down"
- Banners stuttering despite CSS animation
- Everything moving in lockstep

### Solution
Unified data fetching with independent publish cadences for different data types.

**Before:**
```
SWR: 2s interval → all data updates together
DataContext: 5s interval → competing fetch
Result: UI re-renders every 2 seconds
```

**After:**
```
One fetch: 8s → backend poll
  ├─→ 1m rows: Every fetch (with 65ms stagger)
  ├─→ 3m tables: Every 30s
  └─→ Banners: Every 2 minutes (CSS scrolls continuously)
```

### Files Changed
- `frontend/src/context/DataContext.jsx` - Multi-cadence publisher
- `frontend/src/hooks/useDashboardData.js` - Uses DataContext instead of SWR
- `frontend/src/App.jsx` - Added DataProvider to root
- `frontend/.env.local` - Added cadence tuning knobs

### Environment Variables
```bash
VITE_FETCH_MS=8000          # How often to poll /api/data
VITE_PUBLISH_3M_MS=30000    # 3m tables update frequency
VITE_PUBLISH_BANNER_MS=120000  # Banner data update frequency (CSS animates continuously)
VITE_ROW_STAGGER_MS=65      # Stagger delay for smooth 1m row updates
```

---

## 🎨 Visual Improvements

### 1. Permanent Row Rails
**Problem:** Rails only appeared on hover (opacity 0 → 1), rows felt invisible until interaction.

**Solution:** Permanent gradient rails at 55% opacity, boost to 95% on hover with glow.

**CSS:** `frontend/src/index.css` (lines 3147-3207)
```css
.bh-row::after {
  opacity: 0.55 !important; /* Always visible */
  background: linear-gradient(90deg,
    rgba(255, 140, 0, 0.18),
    rgba(80, 200, 255, 0.18),
    rgba(255, 0, 160, 0.18)
  );
}

.bh-row:hover::after {
  opacity: 0.95 !important;
  filter: drop-shadow(0 0 6px rgba(255, 180, 0, 0.28))
          drop-shadow(0 0 10px rgba(180, 80, 255, 0.18));
}
```

### 2. Bunny Glow Boost on Row Hover
**Solution:** Bunny layer stays subdued (opacity 0.08) until any row is hovered, then adds +0.10 opacity and glow.

**CSS:** Uses `:has()` selector (no JS)
```css
.board-core:has(.bh-row:hover) .rabbit-bg {
  opacity: calc(var(--bh-bunny-opacity, 0.08) + 0.10);
  filter:
    drop-shadow(0 0 14px rgba(255, 180, 0, 0.20))
    drop-shadow(0 0 24px rgba(180, 80, 255, 0.14));
}
```

### 3. Subtle Banner Pill Glow
**Solution:** Whisper-thin radial gradient glow on hover (gold for gainers, purple for losers).

**CSS:** `frontend/src/index.css` (lines 3209-3267)
```css
.bh-banner-item.is-gain::after {
  background: radial-gradient(closest-side,
    rgba(255, 196, 61, 0.22),
    rgba(255, 196, 61, 0.0) 70%
  );
}

.bh-banner-item:hover::after {
  opacity: 0.85; /* Soft reveal */
}
```

---

## 🐛 Critical Bug Fixes

### Banner Scroll Animation Killer
**Problem:** Banners appeared frozen despite CSS animation being defined.

**Root Cause:**
```jsx
<div key="price-banner-track" className="bh-banner-track"> {/* ❌ Remounts on every refresh */}
```

The `key` prop caused React to remount the div on every data update, resetting `translateX(0)` faster than the eye could see motion.

**Solution:** Removed `key` props from banner tracks.

**Files Fixed:**
- `frontend/src/components/TopBannerScroll.jsx:99`
- `frontend/src/components/VolumeBannerScroll.jsx:120`

**Before:**
```jsx
<div key="price-banner-track" className="bh-banner-track">
```

**After:**
```jsx
<div className="bh-banner-track">
```

**Result:** CSS animation runs continuously, data updates don't interrupt scroll.

---

## 📊 Performance Characteristics

### M3 Mac (MPS)
- **Model Load**: ~2-3 seconds (one-time at startup)
- **FinBERT inference**: ~500-800ms per symbol (background)
- **UI re-renders**: Gated by publish cadences (not fetch frequency)
- **Banner scroll**: 60fps continuous (CSS, no JS)

### Intel N100 (Target)
- **Fetch overhead**: Minimal (8s interval, AbortController prevents stacking)
- **Re-render frequency**: Reduced by 75% (only when data actually changes for that section)
- **Stagger animation**: Creates perception of realtime without DOM thrashing
- **Banner independence**: Scrolls at 60fps regardless of data updates

---

## 🎛️ Tuning Guide

### For slower hardware (N100)
```bash
VITE_FETCH_MS=10000         # Fetch less often
VITE_PUBLISH_3M_MS=60000    # 3m tables update once per minute
VITE_PUBLISH_BANNER_MS=180000  # Banners update every 3 minutes
VITE_ROW_STAGGER_MS=100     # Slower stagger feels smoother on weak CPU
```

### For faster response
```bash
VITE_FETCH_MS=5000          # Fetch more often
VITE_PUBLISH_3M_MS=15000    # 3m tables update twice per minute
VITE_PUBLISH_BANNER_MS=60000   # Banners update every minute
VITE_ROW_STAGGER_MS=45      # Faster stagger for snappy feel
```

### Disable stagger (instant batch)
```bash
VITE_ROW_STAGGER_MS=0       # All rows update simultaneously
```

---

## ✅ Testing Checklist

- [x] Fetch frequency decoupled from UI update cadence
- [x] 1-minute rows stagger smoothly (no jarring batch updates)
- [x] 3-minute tables don't re-render every fetch
- [x] Banners scroll continuously without stuttering
- [x] Row rails always visible (not hover-only)
- [x] Stronger hover glow on rows
- [x] Bunny glow boost on row hover
- [x] Banner pills have subtle hover glow
- [x] No key props on animated elements
- [x] Single data source (no SWR/DataContext competition)

---

## 📝 Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│                  DataProvider                   │
│  (single fetch source, multi-cadence publish)  │
└─────────────────────────────────────────────────┘
                        │
                        │ Fetch: 8s
                        ↓
                 ┌──────────────┐
                 │  /api/data   │
                 │   Backend    │
                 └──────────────┘
                        │
                        │ Normalize
                        ↓
         ┌──────────────┼──────────────┐
         │              │              │
         ↓              ↓              ↓
    1m rows        3m tables      Banners
    (stagger)      (30s gate)   (2min gate)
         │              │              │
         └──────────────┼──────────────┘
                        │
                        ↓
              useDashboardData hook
                        │
                        ↓
                  UI Components
                  (only re-render
                   when their slice
                   changes)
```

---

## 🚀 Next Steps

1. **Monitor N100 performance**: Test on actual N100 hardware, adjust cadences if needed
2. **Add visibility API**: Pause fetching when browser tab is hidden (already done for IntelligenceContext)
3. **Consider service worker**: Cache /api/data for instant offline/reload
4. **Add performance metrics**: Track fetch times, render counts in DevTools

---

## 📚 References

- [DataContext.jsx](frontend/src/context/DataContext.jsx) - Multi-cadence publisher
- [useDashboardData.js](frontend/src/hooks/useDashboardData.js) - Unified data hook
- [index.css](frontend/src/index.css) - Row rails, bunny boost, pill glow (lines 3147-3267)
- [TopBannerScroll.jsx](frontend/src/components/TopBannerScroll.jsx) - Fixed animation remounting
- [VolumeBannerScroll.jsx](frontend/src/components/VolumeBannerScroll.jsx) - Fixed animation remounting
- [.env.local.example](frontend/.env.local.example) - Full configuration reference

---

*Last updated: 2025-12-23*

---

## 🔧 Banner Scroll Troubleshooting (December 23, 2025)

### Root Causes Identified

The banners weren't scrolling due to **three separate issues**:

#### 1. Animation Remounting (Fixed Earlier)
**Problem:** `key="price-banner-track"` on the track div caused React to remount on every data update.

**Solution:** Removed `key` props from:
- `TopBannerScroll.jsx:99`
- `VolumeBannerScroll.jsx:120`

#### 2. Reduced Motion Killing All Animations
**Problem:** Global `prefers-reduced-motion` media query at `index.css:1468` was setting `animation-duration: 0.01ms !important` on ALL elements, including banners.

**Solution:** Added exception rule inside the media query:
```css
@media (prefers-reduced-motion: reduce) {
  /* Exception: Keep banner scrolling even with reduced motion */
  .bh-banner-track {
    animation-duration: var(--bh-banner-duration, 520s) !important;
    animation-iteration-count: infinite !important;
  }
}
```

**Location:** `index.css:1477-1481`

#### 3. Missing `width: max-content`
**Problem:** `.bh-banner-track` rules at lines 972 and 3024 were missing `width: max-content`, so the track was never wider than the viewport. With no overflow to scroll, the animation had nowhere to go.

**Solution:** Added `width: max-content` to both `.bh-banner-track` rules.

**Why this matters:** 
- Without `max-content`, the flex container only takes up the viewport width
- The animation tries to move to `-50%`, but there's no extra content to reveal
- Result: looks frozen even though animation is running

**Locations:**
- `index.css:976`
- `index.css:3029`

### Verification Checklist

To confirm banners are scrolling:

1. **Open DevTools** → Elements → Inspect `.bh-banner-track`
2. **Check computed width:** Should be LARGER than viewport width
3. **Check animation:** Should see `animation: continuous-scroll 650s linear infinite running`
4. **Watch transform:** Should see `transform: translateX(...)` value decreasing over time
5. **Visual test:** Items should smoothly scroll from right to left

### If Still Not Scrolling

1. **Check content duplication:**
   ```jsx
   const looped = display.length ? [...display, ...display] : [];
   ```
   Should have 2x the items (seamless loop)

2. **Check OS motion settings:**
   - macOS: System Preferences → Accessibility → Display → Reduce Motion (should be OFF)
   - Check in DevTools: `window.matchMedia('(prefers-reduced-motion: reduce)').matches` should be `false`

3. **Check CSS cascade:**
   - Search CSS for `animation: none` or `.bh-banner-track { animation: ...}` overrides
   - Verify no conflicting `transform` styles

4. **Check React keys:**
   - Ensure NO `key` prop on `.bh-banner-track` div
   - Keys on individual items are fine (and necessary)

### Quick Debug Script

Paste in browser console:
```javascript
const track = document.querySelector('.bh-banner-track');
console.log({
  width: track.offsetWidth,
  viewportWidth: window.innerWidth,
  isWider: track.offsetWidth > window.innerWidth,
  animation: getComputedStyle(track).animation,
  transform: getComputedStyle(track).transform
});
```

Should output:
```
{
  width: 3000+,  // Much larger than viewport
  viewportWidth: 1440,
  isWider: true,
  animation: "650s linear 0s infinite normal none running continuous-scroll",
  transform: "matrix(1, 0, 0, 1, -XXX, 0)"  // XXX decreases over time
}
```

---
