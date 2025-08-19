// frontend/src/components/GainersTable.jsx
import React, { useEffect, useMemo, useState } from 'react'
import { useWebSocket } from '../context/websocketcontext.jsx'
import { getJSON } from '../lib/api'

const T3M_ENDPOINT = '/api/component/gainers-table'

// Normalize various backend shapes into [{ symbol, price, pct }]
function normalize(input) {
  if (!input) return []
  let items = []
  if (Array.isArray(input)) items = input
  else if (Array.isArray(input.data)) items = input.data
  else if (Array.isArray(input.crypto)) items = input.crypto
  else if (input.crypto_meta?.gainers) items = input.crypto_meta.gainers
  else if (input.component && Array.isArray(input.data)) items = input.data
  else if (input.t3m && Array.isArray(input.t3m)) items = input.t3m
  else items = []

  return items
    .map((r) => {
      const symbol = (r.symbol || r.ticker || r.asset || r.pair || r.name || '')
        .toString()
        .toUpperCase()
      const price =
        r.price ?? r.last ?? r.close ?? r.price_usd ?? r.current_price ?? null
      const pct =
        r.change_3m ?? r.pct_3m ?? r.pct ?? r.change ?? r.delta_3m ?? r.delta ?? 0
      return { symbol, price, pct: Number(pct) || 0 }
    })
    .filter((r) => r.symbol)
}

// Dedupe by symbol; keep row with largest absolute 3-min change, then sort
function dedupeAndSort(rows) {
  const map = new Map()
  for (const row of rows) {
    const existing = map.get(row.symbol)
    if (!existing || Math.abs(row.pct) > Math.abs(existing.pct)) map.set(row.symbol, row)
  }
  return [...map.values()].sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))
}

export default function GainersTable() {
  const { tables } = useWebSocket() || {}
  const [httpData, setHttpData] = useState(null)
  const [error, setError] = useState(null)

  const socketRows = useMemo(() => normalize(tables?.t3m), [tables])
  const haveSocket = socketRows.length > 0

  useEffect(() => {
    let cancelled = false
    if (haveSocket) return
    getJSON(T3M_ENDPOINT)
      .then((json) => {
        if (!cancelled) setHttpData(json)
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || String(e))
      })
    return () => {
      cancelled = true
    }
  }, [haveSocket])

  const rows = useMemo(() => {
    const base = haveSocket ? socketRows : normalize(httpData)
    return dedupeAndSort(base)
  }, [haveSocket, socketRows, httpData])

  if (error) {
    return <div className="p-3 text-red-500">Error loading 3-min gainers: {error}</div>
  }
  if (rows.length === 0) {
    return <div className="p-3 text-gray-400">No 3-min gainers data available.</div>
  }

  return (
    <div className="p-3">
      <div className="mb-2 text-sm text-gray-500">
        3-minute gainers · {rows.length} assets
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500">
            <th className="py-1 pr-2">Symbol</th>
            <th className="py-1 pr-2">Price</th>
            <th className="py-1">Δ 3m</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className="border-t border-gray-800">
              <td className="py-1 pr-2 font-medium">{r.symbol}</td>
              <td className="py-1 pr-2 tabular-nums">{r.price ?? '—'}</td>
              <td className={`py-1 tabular-nums ${r.pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {Number.isFinite(r.pct) ? r.pct.toFixed(2) : '0.00'}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}