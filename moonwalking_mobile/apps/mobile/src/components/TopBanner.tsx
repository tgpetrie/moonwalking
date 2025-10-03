import React, { useMemo } from 'react'

// TopBannerScroll (web) — standalone component, no self-imports
export default function TopBannerScroll({ items, className }) {
  const list = useMemo(() => (Array.isArray(items) ? items : []), [items])

  const content = useMemo(() => {
    if (!list.length) {
      return (
        <div style={{ padding: '8px 12px', color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>
          No 1h data yet <span style={{ opacity: 0.7 }}>(warming up)</span>.
        </div>
      )
    }
    return (
      <div style={{ display: 'flex', gap: 8 }}>
        {list.map((r) => (
          <div
            key={r.symbol}
            style={{
              padding: '8px 12px',
              borderRadius: 999,
              background: 'rgba(255,255,255,0.06)',
              display: 'flex',
              flexDirection: 'column',
              minWidth: 120,
            }}
          >
            <div style={{ color: '#fff', fontWeight: 700, lineHeight: 1 }}>{r.symbol}</div>
            <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, marginTop: 2 }}>
              {fmtPrice(r.price)} • {fmtPct(r.changePct1h)}
            </div>
          </div>
        ))}
      </div>
    )
  }, [list])

  return (
    <div
      className={className}
      style={{
        padding: '8px 0',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        overflowX: 'auto',
        whiteSpace: 'nowrap',
      }}
    >
      <div style={{ padding: '0 8px' }}>{content}</div>
    </div>
  )
}

function fmtPrice(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  const digits = Math.abs(n) < 1 ? 6 : 2
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits }).format(n)
  } catch {
    return `$${n.toFixed(digits)}`
  }
}

function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  const sign = n > 0 ? '+' : ''
  const digits = Math.abs(n) < 1 ? 3 : 2
  return `${sign}${n.toFixed(digits)}%`
}
