import React, { useEffect, useState, useMemo } from 'react';
import UniformCard from './UniformCard.jsx';
import { fetchWithSWR, API_ENDPOINTS } from '../lib/api.js';

function normalize(raw) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
  if (!Array.isArray(rows)) rows = [];
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base)?.toUpperCase();
    if (!sym) continue;
    const pct = Number(r.change_3m ?? r.change ?? r.pct ?? r.delta ?? r.price_change_percentage_3m ?? 0) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? r.current ?? 0) || 0;
    const entry = { symbol: sym, price: px, change: pct };
    const prev = map.get(sym);
    if (!prev || entry.change < prev.change) map.set(sym, entry);
  }
  return Array.from(map.values()).sort((a, b) => a.change - b.change);
}

export default function LosersTable({ view = 'table' }) {
  const [rows, setRows] = useState([]);
  const [watchlist, setWatchlist] = useState(() => new Set());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchWithSWR(API_ENDPOINTS.losersTable);
        if (!cancelled) setRows(normalize(res?.data ?? res ?? []));
      } catch (e) {}
    })();
    return () => { cancelled = true; };
  }, []);

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

  if (!rows.length) {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">loading…</div></div>
        <div className="empty">No data available.</div>
      </div>
    );
  }

  if (view === 'tiles') {
    return (
      <div className="panel">
        <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
        <div className="gainers-tiles">
          {topRows.map((r, idx) => (
            <UniformCard key={r.symbol} symbol={String(r.symbol).replace('-USD','')} price={r.price} change={r.change} rank={idx+1} showPeak={false} windowLabel="3-min" filled={watchlist.has(r.symbol)} onToggle={onToggle} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__header"><h3>3-minute Losers</h3><div className="meta">assets {rows.length}</div></div>
      <table className="table compact">
        <thead>
          <tr><th>Symbol</th><th>Price</th><th>Δ 3m</th><th/></tr>
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
