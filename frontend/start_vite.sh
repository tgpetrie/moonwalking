// src/components/BottomBannerScroll.jsx
import React, { useMemo } from 'react'
import { API_ENDPOINTS } from '../lib/api'
import useEndpoint from '../hooks/useEndpoint'

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    []
  if (!Array.isArray(rows)) rows = []
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }))
}

export default function BottomBannerScroll() {
  // Use the shared HTTP+socket data hook; no direct fetcher here
  const { data } = useEndpoint(API_ENDPOINTS.bottomBanner)

  const items = useMemo(() => normalize(data || []), [data])

  if (!items.length) return null

  return (
    <div className="banner banner--bottom">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  )
}
