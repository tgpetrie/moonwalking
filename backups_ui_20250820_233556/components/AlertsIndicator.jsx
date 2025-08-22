import React, { useEffect, useState } from 'react'
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api'

function normalizeAlerts(payload) {
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.alerts)) return payload.alerts
  return []
}

export default function AlertsIndicator() {
  const [alerts, setAlerts] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true

    // 1) Instant paint from last socket snapshot (if any)
    try {
      const snap = sessionStorage.getItem('alerts:last')
      if (snap) {
        const parsed = JSON.parse(snap)
        const items = normalizeAlerts(parsed)
        if (alive && items.length) setAlerts(items)
      }
    } catch {}

    // 2) SWR HTTP refresh
    ;(async () => {
      try {
        const payload = await fetchWithSWR(API_ENDPOINTS.alertsRecent)
        if (!alive) return
        const items = normalizeAlerts(payload)
        setAlerts(items)
      } catch (e) {
        if (!alive) return
        setErr(e?.message || String(e))
      }
    })()

    return () => { alive = false }
  }, [])

  if (err) {
    return <div className="text-sm text-red-500">Alerts error: {err}</div>
  }
  
  const count = alerts.length
  const latest = alerts[0]
  const label = count === 0 ? 'No alerts' : `${count} alert${count > 1 ? 's' : ''}`

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-slate-700/60 bg-slate-800/40 text-slate-200">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${count ? 'bg-emerald-500' : 'bg-slate-500'}`} />
      <span className="text-sm font-medium">{label}</span>
      {latest?.symbol && (
        <span className="text-xs text-slate-400">• latest: {(latest.symbol || latest.ticker || latest.asset || '').toUpperCase()}</span>
      )}
    </div>
  )
}