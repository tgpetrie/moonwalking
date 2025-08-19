// src/components/TopBannerScroll.jsx
import React, { useMemo } from 'react'
import { useEndpoint, API_ENDPOINTS } from '../lib/api'

function normalizeArray(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.items)) return payload.items
  return []
}

function normalizeItem(x) {
  const symbol = (x.symbol || x.ticker || x.asset || x.s || x.name || '').toString().toUpperCase()
  let change = x.change_24h ?? x.change_3m ?? x.pct ?? x.delta ?? x.change
  change = Number(change ?? 0)
  return { symbol, change, _raw: x }
}

function dedupeKeepLargestAbs(list) {
  const by = new Map()
  for (const r of list) {
    const prev = by.get(r.symbol)
    if (!prev || Math.abs(r.change) > Math.abs(prev.change)) by.set(r.symbol, r)
  }
  return [...by.values()]
}

function badgeClass(v) {
  if (!Number.isFinite(v)) return 'bg-white/20 text-white'
  return v >= 0 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'
}

export default function TopBannerScroll() {
  const ENDPOINT = (API_ENDPOINTS && (API_ENDPOINTS.topBanner || API_ENDPOINTS.top_banner))
    || '/api/component/top-banner-scroll'
  const [payload, loading] = useEndpoint(ENDPOINT)

  const items = useMemo(() => {
    const base = normalizeArray(payload).map(normalizeItem)
    const uniq = dedupeKeepLargestAbs(base)
    uniq.sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
    return uniq.slice(0, 20)
  }, [payload])

  return (
    <div className="w-full whitespace-nowrap overflow-x-auto py-1">
      <div className="inline-flex gap-3 items-center">
        {loading && <span className="text-xs text-white/50">loading…</span>}
        {items.map(it => (
          <span key={it.symbol} className={`px-2 py-0.5 rounded-full text-xs font-mono border border-white/10 ${badgeClass(it.change)}`}>
            {it.symbol} {Number.isFinite(it.change) ? `${it.change >= 0 ? '+' : ''}${it.change.toFixed(2)}%` : ''}
          </span>
        ))}
        {!loading && items.length === 0 && (
          <span className="text-white/50 text-sm">No movers yet</span>
        )}
      </div>
    </div>
  )
}

// src/components/AlertsIndicator.jsx
import React from 'react';
import { API_ENDPOINTS, useEndpoint } from '../lib/api';

export default function AlertsIndicator() {
  const [payload, loading, err] = useEndpoint(API_ENDPOINTS.alertsRecent);

  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.data)
      ? payload.data
      : Array.isArray(payload?.items)
        ? payload.items
        : [];

  const count = items.length;

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#C026D3]/10 border border-[#C026D3]/30">
      <span className="text-sm text-white/80">Alerts</span>
      <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#C026D3]/30 text-white">
        {loading ? '…' : count}
      </span>
      {err && (
        <span className="text-[10px] text-red-400/80 font-mono">
          offline
        </span>
      )}
    </div>
  );
}