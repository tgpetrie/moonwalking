import React, { useMemo } from 'react';
import { API_ENDPOINTS } from '../lib/api';
import useEndpoint from '../hooks/useEndpoint';
import { fmtUSD, fmtPct, clsDelta } from '../lib/format';

const normalize = (raw = []) => {
  const rows = Array.isArray(raw) ? raw : (raw?.data || raw?.items || raw?.losers || []);
  if (!Array.isArray(rows)) return [];
  return rows.map((r, i) => ({
    symbol: r.symbol || r.ticker || r.asset || '',
    price: r.price ?? r.last ?? r.close,
    d3m: r.delta_3m ?? r.t3m ?? r.change_3m ?? r.delta ?? null,
  }));
};

export default function LosersTable() {
  const { data, loading, error } = useEndpoint(API_ENDPOINTS.losersTable, { pollMs: 15000 });
  const items = useMemo(() => normalize(data), [data]);

  const asPct = (v) => {
    const n = Number(v);
    const pct = Math.abs(n) <= 1 ? n * 100 : n;
    return fmtPct(pct, 2);
  };

  if (loading) return <div className="app-panel p-4 text-zinc-400 text-sm">Loading 3-min losers…</div>;
  if (error)   return <div className="app-panel p-4 text-red-400 text-sm">Error loading 3-min losers.</div>;
  if (!items.length) {
    return <div className="app-panel p-4 text-sm text-zinc-400">No 3-min losers data.</div>;
  }

  return (
    <div className="app-panel overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800/60">
        <h3 className="text-sm font-semibold tracking-wide text-[color:var(--ink)]">3-MIN LOSERS</h3>
      </div>
      <table className="app-table">
        <thead>
          <tr>
            <th className="text-left pl-4">Asset</th>
            <th className="text-right pr-4">Price</th>
            <th className="w-28 text-right pr-4">3-m %</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r, idx) => (
            <tr key={`${r.symbol}-${idx}`} className={idx % 2 ? 'bg-zinc-900/20' : ''}>
              <td className="pl-4 font-medium">{(r.symbol || '').toUpperCase()}</td>
              <td className="text-right pr-4 tabular-nums">{fmtUSD(r.price, 2, 6)}</td>
              <td className={`text-right pr-4 tabular-nums ${clsDelta(r.d3m)}`}>{asPct(r.d3m)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
