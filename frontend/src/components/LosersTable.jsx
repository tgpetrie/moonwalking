import React, { useEffect, useMemo, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api';
import { useWebSocketData } from '../context/websocketcontext.jsx';

function normalize3m(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.crypto ||
    raw?.crypto_meta?.losers ||
    raw?.rows ||
    [];
  if (!Array.isArray(rows)) rows = [];

  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const c3 =
      Number(
        r.change_3m ??
          r.change_3min ??
          r.change3m ??
          r.pct_3m ??
          r['3m_change'] ??
          r.delta_3m ??
          0
      ) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? 0) || 0;
    const entry = { symbol: sym, price: px, change3m: c3 };
    const prev = map.get(sym);
    // For losers keep the *most negative* value
    if (!prev || c3 < prev.change3m) map.set(sym, entry);
  }

  // Sort ascending (most negative first)
  return Array.from(map.values()).sort((a, b) => a.change3m - b.change3m);
}

export default function LosersTable() {
  const { tables } = useWebSocketData();
  const [rows, setRows] = useState([]);
  const t3mSocket = tables?.t3m_losers || tables?.losers || null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let raw = t3mSocket;
      if (!raw || (Array.isArray(raw) && raw.length === 0)) {
        try {
          raw = await fetchWithSWR(API_ENDPOINTS.losers);
        } catch (e) {
          console.warn('[losers 3m] HTTP fallback failed', e);
        }
      }
      const norm = normalize3m(raw);
      if (!cancelled) setRows(norm);
    })();
    return () => {
      cancelled = true;
    };
  }, [t3mSocket]);

  const content = useMemo(() => {
    if (!rows.length) {
      return <div className="empty">No 3-min losers data available.</div>;
    }
    return (
      <table className="table compact">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Δ 3m</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td>{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
              <td>{Number.isFinite(r.change3m) ? `${r.change3m.toFixed(2)}%` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }, [rows]);

  return (
    <div className="panel">
      <div className="panel__header">
        <h3>3-minute Losers</h3>
        <div className="meta">{rows.length ? `assets ${rows.length}` : 'loading…'}</div>
      </div>
      {content}
    </div>
  );
}