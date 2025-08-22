// frontend/src/app.jsx
import React, { lazy, Suspense } from 'react'

const AlertsIndicator = lazy(() => import('./components/AlertsIndicator.jsx'))
const MarketPanels   = lazy(() => import('./components/MarketPanels.jsx'))

export default function App() {
  return (
    <div className="app-shell">
      <Suspense fallback={<div className="p-4 text-sm text-zinc-400">Loading…</div>}>
        <AlertsIndicator />
        <MarketPanels />
      </Suspense>
    </div>
  )
}