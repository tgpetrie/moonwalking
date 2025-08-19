// src/app.jsx
import React, { Suspense, lazy } from 'react'

const TopBannerScroll = lazy(() => import('./components/TopBannerScroll.jsx'))
const BottomBannerScroll = lazy(() => import('./components/BottomBannerScroll.jsx'))
const Gainers1m = lazy(() => import('./components/GainersTable1m.jsx'))
const Gainers3m = lazy(() => import('./components/GainersTable.jsx'))      // 3-min
const Losers3m  = lazy(() => import('./components/LosersTable.jsx'))
const Watchlist = lazy(() => import('./components/Watchlist.jsx'))
const AlertsIndicator = lazy(() => import('./components/AlertsIndicator.jsx'))

export default function App() {
  return (
    <div className="min-h-screen bg-black text-white">
      <Suspense fallback={<div className="p-6">Loading…</div>}>
        <AlertsIndicator />
        <TopBannerScroll />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
          <Gainers1m />
          <Gainers3m />
          <Losers3m />
        </div>
        <BottomBannerScroll />
        <div className="p-6">
          <Watchlist />
        </div>
      </Suspense>
    </div>
  )
}