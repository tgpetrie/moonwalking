// src/components/LosersTable.jsx
import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../lib/api';
import { fmtUSD, fmtPct, clsDelta } from '../lib/format';

function normalizeLosers(payload) {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (payload?.data && Array.isArray(payload.data)) return payload.data;
  if (payload?.crypto && Array.isArray(payload.crypto)) return payload.crypto;
  if (payload?.crypto_meta?.losers && Array.isArray(payload.crypto_meta.losers)) return payload.crypto_meta.losers;
  if (payload?.component && payload?.items && Array.isArray(payload.items)) return payload.items;
  if (payload?.losers && Array.isArray(payload.losers)) return payload.losers;
  return [];
}

function dedupeByWorstChange(rows) {
  const bySym = new Map();
  for (const r of rows) {
    const sym = (r.symbol || r.ticker || r.asset || r.name || '').toUpperCase();
    if (!sym) continue;
    const pct = Number(r.pct || r.percent || r.change || r.change_pct || r.pct_3m || r['3m'] || 0);
    const prev = bySym.get(sym);
    if (!prev || Math.abs(pct) > Math.abs(prev._pct)) {
      bySym.set(sym, { ...r, _pct: pct, _sym: sym });
    }
  }
  return Array.from(bySym.values());
}

export default function LosersTable() {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const payload = await fetchWithSWR(API_ENDPOINTS.losersTable);
        if (!alive) return;
        const norm = dedupeByWorstChange(normalizeLosers(payload));
        // keep only negative changes
        const onlyNeg = norm.filter(r => Number(r._pct) < 0);
        setRows(onlyNeg);
      } catch (e) {
        if (!alive) return;
        setErr(e?.message || String(e));
      }
    })();
    return () => { alive = false; };
  }, []);

  if (err) {
    return <div className="p-2 text-sm text-red-500">3‑min losers error: {err}</div>;
  }
  if (!rows?.length) {
    return <div className="p-2 text-sm text-slate-400">No 3‑min losers data available.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm app-table">
        <thead>
          <tr className="text-left text-slate-400">
            <th className="py-2 pr-4 pl-4">Asset</th>
            <th className="py-2 pr-4 text-right">Price</th>
            <th className="py-2 pr-4 w-28 text-right">3m %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const sym = r._sym || (r.symbol || r.ticker || '').toUpperCase();
            const price = r.price ?? r.last ?? r.close ?? r.p ?? null;
            const pct = r._pct ?? r.pct ?? r.change ?? r.change_pct ?? 0;
            return (
              <tr key={`${sym}-${i}`} className={i%2 ? 'bg-zinc-900/20' : ''}>
                <td className="py-2 pl-4 font-medium">{sym}</td>
                <td className="py-2 tabular-nums text-right pr-4">{fmtUSD(price,2,6)}</td>
                <td className={`py-2 tabular-nums text-right pr-4 ${clsDelta(pct)}`}>{fmtPct(Number(pct),2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}