// src/components/Watchlist.jsx
import React, { useEffect, useMemo, useState } from 'react'
import { useWebSocket, WebSocketContext } from '../context/websocketcontext.jsx'

const DEFAULT_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOGE-USD']

function sanitizeSymbol(input) {
  if (!input) return null
  let sym = String(input).trim().toUpperCase()
  // Accept "BTC", "btc-usd", "BTC/USD", etc → normalize to "BTC-USD"
  sym = sym.replace(/\s+/g, '')
  sym = sym.replace('/', '-')
  if (!sym.includes('-')) sym = `${sym}-USD`
  return sym
}

function formatPrice(x) {
  if (x == null || Number.isNaN(+x)) return '—'
  const n = +x
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (n >= 1)   return n.toLocaleString(undefined, { maximumFractionDigits: 3 })
  if (n >= 0.1) return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

function pctClass(v) {
  // Project styling: purple for positive, pink for negative, gray neutral
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
      <div className="h-4 w-16 bg-gray-700/60 rounded" />
      <div className="h-6 w-12 bg-gray-700/60 rounded" />
    </div>
  )
}

export default function Watchlist({ initialSymbols }) {
  const ctx = (typeof useWebSocket === 'function' ? useWebSocket() : null)
            || React.useContext(WebSocketContext)
            || { state: { connected: false, prices: {}, alerts: [], server: null } }

  const { state } = ctx
  const pricesObj = (state && state.prices && typeof state.prices === 'object') ? state.prices : {}
  const connected = !!(state && state.connected)

  // Local symbols persisted across sessions
  const [symbols, setSymbols] = useState(() => {
    const fromProp  = Array.isArray(initialSymbols) && initialSymbols.length ? initialSymbols : null
    const fromStore = (() => {
      try { return JSON.parse(localStorage.getItem('watchlist_symbols') || '[]') } catch { return [] }
    })()
    return (fromProp || fromStore || DEFAULT_SYMBOLS).filter(Boolean)
  })

  useEffect(() => {
    try { localStorage.setItem('watchlist_symbols', JSON.stringify(symbols)) } catch {}
  }, [symbols])

  const [input, setInput] = useState('')

  const rows = useMemo(() => {
    return (symbols.length ? symbols : DEFAULT_SYMBOLS).map(sym => {
      const p = pricesObj[sym]
      // allow either {price, change24h} or a raw number
      const last = (p && typeof p === 'object') ? p.price : (typeof p === 'number' ? p : null)
      const change24h = (p && typeof p === 'object' && typeof p.change24h === 'number') ? p.change24h : null
      return { symbol: sym, last, change24h }
    })
  }, [symbols, pricesObj])

  const hasAnyPrice = rows.some(r => r.last != null)

  function addSymbol() {
    const sym = sanitizeSymbol(input)
    if (!sym) return
    if (!symbols.includes(sym)) setSymbols(prev => [...prev, sym])
    setInput('')
  }

  function removeSymbol(sym) {
    setSymbols(prev => prev.filter(s => s !== sym))
  }

  function onKeyDown(e) {
    if (e.key === 'Enter') addSymbol()
  }

  return (
    <div className="p-4 rounded-2xl bg-transparent shadow-inner border border-white/4 backdrop-blur-sm transition-all duration-200 ease-out hover:shadow-[inset_0_0_24px_rgba(128,0,255,0.12)] hover:scale-[1.002] w-full md:col-span-2">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-headline font-bold tracking-wide">Watchlist</h2>
        <div className={`text-xs px-2 py-1 rounded ${connected ? 'bg-green-600/20 text-green-300' : 'bg-gray-600/20 text-gray-300'}`}>
          {connected ? 'live' : 'offline'}
        </div>
      </div>

      {/* Add symbol */}
  <div className="flex items-center gap-2 mb-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Add symbol (e.g. BTC or BTC-USD)"
          className="flex-1 px-3 py-2 rounded bg-white/3 border border-white/6 text-sm outline-none focus:ring-2 ring-purple-400/30 placeholder:text-gray-400"
        />
        <button
          onClick={addSymbol}
          className="px-3 py-2 rounded bg-purple-600/80 hover:bg-purple-600 text-sm text-white"
        >
          Add
        </button>
      </div>

      {/* Header */}
  <div className="hidden sm:grid grid-cols-[minmax(0,1fr)_152px_108px_28px] items-center gap-x-4 px-1 text-xs text-gray-400 mb-1">
        <div>Symbol</div>
        <div className="text-right">Last</div>
        <div className="text-right">24h</div>
        <div className="text-right"> </div>
      </div>

      {/* Rows */}
      {!hasAnyPrice && !Object.keys(pricesObj).length ? (
        <>
          <RowSkeleton /><RowSkeleton /><RowSkeleton /><RowSkeleton /><RowSkeleton />
          <div className="mt-2 text-xs text-gray-400">Waiting for live prices…</div>
        </>
      ) : (
        <div>
          {rows.map(({ symbol, last, change24h }) => (
            <div key={symbol} className="px-2 py-1 mb-1">
              <div className="relative overflow-hidden rounded-xl p-4 box-border hover:scale-[1.01] transition-transform">
                <div className="relative z-10 w-full grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-center">
                  <div className="min-w-0">
                    <div className="font-headline font-bold text-white text-lg tracking-wide truncate">{symbol.replace('-USD','')}</div>
                  </div>

                  <div className="w-[152px] pr-6 text-right">
                    <div className="text-base sm:text-lg font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                      {formatPrice(last)}
                    </div>
                  </div>

                  <div className="w-[108px] pr-1.5 text-right">
                    <div className={`text-base sm:text-lg font-bold font-mono leading-none whitespace-nowrap ${pctClass(change24h)}`}>
                      {change24h == null || Number.isNaN(+change24h) ? '—' : `${(+change24h).toFixed(2)}%`}
                    </div>
                    <div className="text-xs text-gray-400">24h</div>
                  </div>

                  <div className="w-[28px] flex items-center justify-end">
                    <button
                      onClick={() => removeSymbol(symbol)}
                      className="bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-end text-gray-300 hover:text-white"
                      title="Remove from watchlist"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}