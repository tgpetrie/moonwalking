import { useEffect, useMemo, useRef, useState } from 'react'
import { endpoints } from '../lib/api'

type SWRBlock = {
  source: string
  cached_at: number
  ttl: number
  stale_window: number
  served_cached: boolean
  ttl_seconds: number
  revalidate_seconds?: number
  note?: string
}

type TopMoversAPI = {
  component?: string
  data?: Array<{
    symbol: string
    current?: number
    current_price?: number
    price_change_percentage_3min?: number
    price_change_1h?: number
  }>
  swr?: SWRBlock
}

const fmt = (n: number | undefined, d = 2) =>
  typeof n === 'number' && isFinite(n) ? n.toFixed(d) : '—'

export default function TopMovers() {
  const [payload, setPayload] = useState<TopMoversAPI | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number | null>(null)

  const ttlLeft = useMemo(() => {
    if (!payload?.swr) return null
    const now = Math.floor(Date.now() / 1000)
    const expires = (payload.swr.cached_at || 0) + (payload.swr.ttl_seconds || payload.swr.ttl || 0)
    return Math.max(0, expires - now)
  }, [payload?.swr])

  async function fetchOnce() {
    setError(null)
    try {
  const res = await fetch(endpoints.topMoversBar, { headers: { accept: 'application/json' } })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const json: TopMoversAPI = await res.json()
      setPayload(json)
    } catch (e: any) {
      setError(e?.message || 'fetch failed')
    }
  }

  useEffect(() => {
    fetchOnce()
    // background ticker to keep TTL countdown smooth
    timer.current = window.setInterval(() => {
      // trigger re-render while SWR countdown runs
      setPayload((p) => (p ? { ...p } : p))
    }, 1000) as unknown as number
    return () => {
      if (timer.current) window.clearInterval(timer.current)
    }
  }, [])

  useEffect(() => {
    if (ttlLeft === 0) {
      fetchOnce()
    }
  }, [ttlLeft])

  const rows = payload?.data || []

  return (
    <div style={{ padding: 16, fontFamily: 'ui-sans-serif, system-ui' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>Top Movers</h2>
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          {payload?.swr ? (
            <>
              <span>source: {payload.swr.source}</span>
              <span> · ttl: {payload.swr.ttl_seconds ?? payload.swr.ttl}s</span>
              <span> · refresh in: {ttlLeft ?? '—'}s</span>
            </>
          ) : (
            <span>no swr</span>
          )}
        </div>
      </div>

      {error && (
        <div style={{ color: 'crimson', marginBottom: 12 }}>Error: {error}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 8 }}>
        {rows.slice(0, 20).map((r, i) => {
          const price = (r.current ?? r.current_price) as number | undefined
          const ch3m = r.price_change_percentage_3min
          const ch1h = r.price_change_1h
          const change = (typeof ch3m === 'number' ? ch3m : ch1h) ?? 0
          const up = change >= 0
          return (
            <div key={r.symbol + i} style={{
              border: '1px solid rgba(0,0,0,0.08)',
              borderRadius: 8,
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              background: 'rgba(0,0,0,0.02)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <strong>{r.symbol}</strong>
                <span style={{ fontSize: 12, opacity: 0.8 }}>${fmt(price, 4)}</span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: up ? 'green' : 'crimson' }}>
                {up ? '+' : ''}{fmt(change, 2)}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
