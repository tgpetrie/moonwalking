// src/components/GainersTable.jsx
import React, { useMemo } from 'react'
import useEndpoint from '../hooks/useEndpoint'
import { API_ENDPOINTS } from '../lib/api'
import { useWebSocketData } from '../context/websocketcontext'

// local helpers (kept here to avoid extra imports)
function pct3m(item) {
  const keys = [
    'price_change_percentage_3min',
    'change_3m',
    'three_min_change',
    'pct_3m',
    'change',
  ]
  for (const k of keys) {
    const v = item?.[k]
    if (typeof v === 'number' && Number.isFinite(v)) return v
  }
  return 0
}

function currentPrice(item) {
  const keys = ['current_price', 'price', 'last', 'current']
  for (const k of keys) {
    const v = item?.[k]
    if (typeof v === 'number' && Number.isFinite(v)) return v
  }
  return null
}

function normSymbol(s) {
  if (!s) return 'N/A'
  return String(s).replace(/-USD$/i, '').toUpperCase()
}

function normalizeT3M(payload) {
  if (!payload) return []

  let arr = []
  if (Array.isArray(payload)) arr = payload
  else if (Array.isArray(payload?.data)) arr = payload.data
  else if (Array.isArray(payload?.crypto)) arr = payload.crypto
  else if (Array.isArray(payload?.crypto_meta?.gainers)) arr = payload.crypto_meta.gainers
  else if (Array.isArray(payload?.t3m)) arr = payload.t3m
  else return []

  // map → uniform shape and drop non‑positive changes
  const mapped = arr.map((it, idx) => ({
    rank: it.rank ?? idx + 1,
    symbol: normSymbol(it.symbol ?? it.ticker ?? it.asset),
    price: currentPrice(it),
    pct: pct3m(it),
  })).filter((r) => typeof r.pct === 'number' && Number.isFinite(r.pct) && r.pct > 0)

  // de‑dupe by symbol, keep the row with the largest 3‑min %
  const bySym = new Map()
  for (const row of mapped) {
    const prev = bySym.get(row.symbol)
    if (!prev || row.pct > prev.pct) bySym.set(row.symbol, row)
  }

  // sort desc by pct and re‑rank 1..N
  return Array.from(bySym.values())
    .sort((a, b) => b.pct - a.pct)
    .map((r, i) => ({ ...r, rank: i + 1 }))
}

function formatPct(v) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return 'N/A'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(v > 10 ? 1 : 2)}%`
}

export default function GainersTable() {
  // 1) socket snapshot (preferred)
  const { tables: tablesSnap } = useWebSocketData()
  const rowsFromSocket = useMemo(() => normalizeT3M(tablesSnap?.t3m), [tablesSnap])

  // 2) HTTP fallback (poll a bit, with SWR enabled in the data layer)
  const { data: httpPayload, loading, error } = useEndpoint(API_ENDPOINTS.t3m, {
    pollMs: 20000,
    swr: true,
  })
  const rowsFromHttp = useMemo(() => normalizeT3M(httpPayload), [httpPayload])

  const rows = rowsFromSocket.length ? rowsFromSocket : rowsFromHttp

  if (!rows.length) {
    return (
      <div className="w-full h-full min-h-[420px] flex items-center justify-center">
        <div className="text-white/40 text-sm">
          {error ? `Failed to load 3-min data: ${error.message ?? String(error)}` : (loading ? 'Loading 3-min gainers…' : 'No 3-min gainers data available')}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 transition-all duration-300">
      {rows.slice(0, 20).map((row) => (
        <div key={row.symbol} className="px-2 py-1 mb-1">
          <a
            className="block group"
            href={`https://www.coinbase.com/advanced-trade/spot/${row.symbol.toLowerCase()}-USD`}
            target="_blank" rel="noopener noreferrer"
          >
            <div className="relative overflow-hidden rounded-xl p-4 box-border hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform">
              {/* subtle inner glow */}
              <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                <span
                  className="block rounded-xl transition-transform duration-500 opacity-0 group-hover:opacity-90 transform-gpu scale-100 group-hover:scale-105 w-full h-full"
                  style={{
                    background: 'radial-gradient(circle at 50% 50%, rgba(192,38,211,0.20) 0%, rgba(192,38,211,0.12) 45%, rgba(192,38,211,0.06) 70%, transparent 100%)',
                    position: 'absolute', inset: 0,
                  }}
                />
              </span>

              <div className="relative z-10 w-full grid grid-cols-[minmax(0,1fr)_152px_108px] gap-x-4 items-start">
                {/* symbol */}
                <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0">{row.rank}</div>
                  <div className="min-w-0">
                    <div className="font-bold text-white text-lg tracking-wide truncate">{row.symbol}</div>
                  </div>
                </div>

                {/* price */}
                <div className="w-[152px] pr-6 text-right">
                  <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                    {row.price == null ? 'N/A' : `$${row.price < 1 && row.price > 0 ? row.price.toFixed(4) : row.price.toFixed(2)}`}
                  </div>
                </div>

                {/* % change (3‑min) */}
                <div className="w-[108px] pr-1.5 text-right align-top">
                  <div className="text-base sm:text-lg md:text-xl font-bold font-mono leading-none whitespace-nowrap text-[#C026D3]">
                    {formatPct(row.pct)}
                  </div>
                  <div className="text-xs text-gray-400 leading-tight">3‑min</div>
                </div>
              </div>
            </div>
          </a>
        </div>
      ))}
    </div>
  )
}