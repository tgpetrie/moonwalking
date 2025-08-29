import React, { useEffect, useMemo, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api.js';
import UniformCard from './UniformCard.jsx';

function normalize(raw, key) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
  if (!Array.isArray(rows)) rows = [];
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const px = Number(r.price ?? r.last ?? r.p ?? r.current ?? r.close ?? 0) || 0;
    const pct = Number(r[key] ?? r.change_3m ?? r.change3m ?? r.pct_3m ?? r.pct ?? r.change ?? r.pct_1m ?? 0) || 0;
    const entry = { symbol: sym, price: px, change: pct };
    const prev = map.get(sym);
    if (!prev || Math.abs(entry.change) > Math.abs(prev.change)) map.set(sym, entry);
  }
  return Array.from(map.values()).sort((a, b) => b.change - a.change);
}

export default function GainersTable({ windowMinutes = 3, view = 'table' }) {
  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const endpoint = windowMinutes === 1 ? API_ENDPOINTS.t1m : API_ENDPOINTS.t3m;
        const payload = await fetchWithSWR(endpoint);
        if (!cancelled) setRows(normalize(payload?.data ?? payload ?? [], windowMinutes === 1 ? 'change_1m' : 'change_3m'));
      } catch (e) {
        // ignore
      }
    })();
    return () => { cancelled = true; };
  }, [windowMinutes]);

  useEffect(() => {
    (async () => {
      try {
        const { loadWatchlist } = await import('../lib/watchlist.js');
        setWatchlist(new Set(loadWatchlist()));
      } catch (e) {}
    })();
  }, []);

  const topRows = useMemo(() => rows.slice(0, 8), [rows]);

  const onToggle = async (symbol, price) => {
    try {
      const { toggleWatchlist, loadWatchlist } = await import('../lib/watchlist.js');
      await toggleWatchlist(symbol, price);
      setWatchlist(new Set(loadWatchlist()));
    } catch (e) {}
  };

  if (!rows || rows.length === 0) {
    return (
      <div className="panel">
        <div className="panel__header"><h3>{windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers'}</h3><div className="meta">loading…</div></div>
        <div className="empty">No data available.</div>
      </div>
    );
  }

  if (view === 'tiles') {
    return (
      <div className="panel">
        <div className="panel__header"><h3>{windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers'}</h3><div className="meta">assets {rows.length}</div></div>
        <div className="gainers-tiles">
          {topRows.map((r, idx) => (
            <UniformCard
              key={r.symbol}
              symbol={String(r.symbol).replace('-USD','')}
              price={r.price}
              change={r.change}
              rank={idx + 1}
              showPeak={windowMinutes === 1}
              windowLabel={`${windowMinutes}-min`}
              filled={watchlist.has(r.symbol)}
              onToggle={onToggle}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__header"><h3>{windowMinutes === 1 ? '1-minute Gainers' : '3-minute Gainers'}</h3><div className="meta">assets {rows.length}</div></div>
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ {windowMinutes}m</th><th/></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.symbol}-${i}`}>
              <td className="mono">{String(r.symbol).replace('-USD','')}</td>
              <td className="num">{Number.isFinite(r.price) ? r.price.toFixed(4) : '-'}</td>
              <td className={`num ${r.change >= 0 ? 'positive' : 'negative'}`}>{Number.isFinite(r.change) ? `${r.change.toFixed(2)}%` : '-'}</td>
              <td style={{ textAlign: 'right' }}>
                <button className="badge" onClick={() => onToggle(r.symbol, r.price)} aria-pressed={watchlist.has(r.symbol)}>{watchlist.has(r.symbol) ? '★' : '☆'}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}