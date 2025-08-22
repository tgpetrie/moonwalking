// src/components/Watchlist.jsx
import React, { useContext, useEffect, useMemo, useState } from 'react'
import { useWebSocket, WebSocketContext } from '../context/websocketcontext.jsx'

const DEFAULT_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOGE-USD']

function sanitizeSymbol(input) {
  if (!input) return null
  let sym = String(input).trim().toUpperCase()
  sym = sym.replace(/\s+/g, '')
  sym = sym.replace('/', '-')
  if (!sym.includes('-')) sym = `${sym}-USD`
  return sym
}

function formatPrice(x) {
  if (x == null || Number.isNaN(+x)) return '—'
  const n = +x
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (n >= 1) return n.toLocaleString(undefined, { maximumFractionDigits: 3 })
  if (n >= 0.1) return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

function pctClass(v) {
  if (v == null || Number.isNaN(+v)) return 'text-gray-300'
  if (+v > 0) return 'text-[#C026D3]'
  if (+v < 0) return 'text-pink'
  return 'text-gray-300'
}

function RowSkeleton() {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-b border-gray-800/40 animate-pulse">
      <div className="h-4 w-24 bg-gray-700/60 rounded" />
      <div className="h-4 w-20 bg-gray-700/60 rounded" />
      <div className="h-4 w-20 bg-gray-700/60 rounded" />
      <div className="h-4 w-16 bg-gray-700/60 rounded" />
      <div className="h-6 w-12 bg-gray-700/60 rounded" />
    </div>
  )
}

export default function Watchlist({ initialSymbols }) {
  // Prefer hook if available, otherwise context
  const hookCtx = typeof useWebSocket === 'function' ? useWebSocket() : null
  const ctx = hookCtx || useContext(WebSocketContext) || { state: { connected: false, prices: {} } }
  const { state } = ctx
  const pricesObj = (state && state.prices && typeof state.prices === 'object') ? state.prices : {}

  const [symbols, setSymbols] = useState(() => {
    try {
      const store = JSON.parse(localStorage.getItem('watchlist_symbols') || 'null')
      const fromProp = Array.isArray(initialSymbols) && initialSymbols.length ? initialSymbols : null
      return (fromProp || store || DEFAULT_SYMBOLS).filter(Boolean)
    } catch {
      return initialSymbols && initialSymbols.length ? initialSymbols : DEFAULT_SYMBOLS
    }
  })

  useEffect(() => {
    try { localStorage.setItem('watchlist_symbols', JSON.stringify(symbols)) } catch {}
  }, [symbols])

  const [input, setInput] = useState('')

  // capture price at time of adding
  const [meta, setMeta] = useState(() => {
    try { return JSON.parse(localStorage.getItem('watchlist_meta') || '{}') } catch { return {} }
  })

  useEffect(() => {
    try { localStorage.setItem('watchlist_meta', JSON.stringify(meta)) } catch {}
  }, [meta])

  useEffect(() => {
    // console to prove visible symbols in the UI
    console.log('Watchlist visible symbols:', symbols)
  }, [symbols])

  const addSymbol = () => {
    const s = sanitizeSymbol(input)
    if (!s) return
    if (symbols.includes(s)) {
      setInput('')
      return
    }
    // capture current price if available
    const p = pricesObj[s]
    const priceAtAdd = (p && typeof p === 'object') ? p.price : (typeof p === 'number' ? p : null)
    setSymbols(prev => [s, ...prev].slice(0, 50))
    setMeta(prev => ({ ...prev, [s]: { priceAtAdd, addedAt: Date.now() } }))
    setInput('')
  }

  const removeSymbol = (s) => {
    setSymbols(prev => prev.filter(x => x !== s))
    setMeta(prev => {
      const copy = { ...prev }
      delete copy[s]
      return copy
    })
  }

  const rows = useMemo(() => {
    if (!symbols || !symbols.length) return []
    return symbols.map(sym => {
      const p = pricesObj[sym]
      const last = (p && typeof p === 'object') ? p.price : (typeof p === 'number' ? p : null)
      const addedPrice = meta[sym]?.priceAtAdd ?? null
      const pct = (last != null && addedPrice != null) ? ((last - addedPrice) / addedPrice) * 100 : null
      return { sym, last, addedPrice, pct }
    })
  }, [symbols, pricesObj, meta])

  return (
    <div className="p-3 bg-black/60 rounded-md border border-gray-800/40">
      <div className="flex items-center mb-2 gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') addSymbol() }}
          placeholder="Add symbol e.g. BTC or BTC-USD"
          className="bg-gray-900 text-white px-2 py-1 rounded flex-1"
        />
        <button onClick={addSymbol} className="px-3 py-1 bg-indigo-600 rounded">Add</button>
      </div>

      <div className="space-y-1">
        {(!rows || rows.length === 0) ? (
          Array.from({ length: 5 }).map((_, i) => <RowSkeleton key={i} />)
        ) : rows.map(r => (
          <div key={r.sym} className="flex items-center justify-between gap-3 py-2 border-b border-gray-800/40">
            <div className="w-28 font-mono text-sm">{r.sym}</div>
            <div className="w-28 text-right text-sm">{formatPrice(r.last)}</div>
            <div className={`w-24 text-right text-sm ${pctClass(r.pct)}`}>{r.pct == null ? '—' : `${r.pct.toFixed(2)}%`}</div>
            <div className="w-24 text-right text-sm text-gray-400">{r.addedPrice == null ? '—' : formatPrice(r.addedPrice)}</div>
            <div>
              <button onClick={() => removeSymbol(r.sym)} className="text-xs text-red-400">Remove</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
