import React, { useEffect, useMemo, useState } from 'react';
import UniformCard from './UniformCard.jsx';
import { fetchWithSWR, API_ENDPOINTS } from '../lib/api.js';

function normalize(raw) {
  let rows = (Array.isArray(raw) && raw) || raw?.data || raw?.crypto || raw?.rows || [];
  if (!Array.isArray(rows)) { rows = []; }
  const map = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.s || r.base);
    if (!sym) { continue; }
    const S = String(sym).toUpperCase();
    const pct = Number(r.change_1m ?? r.change ?? r.pct ?? r.delta ?? 0) || 0;
    const px = Number(r.price ?? r.last ?? r.p ?? r.close ?? r.current ?? 0) || 0;
    const entry = { symbol: S, price: px, change: pct };
    const prev = map.get(S);
    if (!prev || entry.change > prev.change) { map.set(S, entry); }
  }
  return Array.from(map.values()).sort((a, b) => b.change - a.change);
}

export default function GainersTableHistoric({ view = 'tiles' }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    let dead = false;
    (async () => {
      try {
        const res = await fetchWithSWR(API_ENDPOINTS.gainersTable1m);
        if (!dead) { setRows(normalize(res?.data ?? res ?? [])); }
      } catch (e) {}
    })();
    return () => { dead = true; };
  }, []);

  const top = useMemo(() => rows.slice(0, 8), [rows]);

  if (!rows.length) {
    return <div className="panel">No data</div>;
  }

  if (view === 'tiles') {
    return (
      <div className="panel">
        <div className="gainers-tiles">
          {top.map((r, i) => (
            <UniformCard key={r.symbol} symbol={r.symbol} price={r.price} change={r.change} rank={i+1} windowLabel="1-min" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <table className="table compact">
      <thead><tr><th>Symbol</th><th>Price</th><th>Δ 1m</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.symbol}><td>{r.symbol}</td><td>{r.price}</td><td>{r.change}</td></tr>
        ))}
      </tbody>
    </table>
  );
}
