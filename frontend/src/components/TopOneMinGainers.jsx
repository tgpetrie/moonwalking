import { useMemo, useState } from 'react';
import { API_ENDPOINTS } from '../api';
import useEndpoint from '../hooks/useEndpoint';
import { fmtUSD, clsDelta, asPctAuto } from '../lib/format';

const normalize = (raw = []) => {
  const rows = Array.isArray(raw) ? raw : (raw?.data || raw?.items || raw?.gainers || []);
  if (!Array.isArray(rows)) return [];
  return rows.map((r, i) => ({
    rank: r.rank ?? i + 1,
    symbol: r.symbol || r.ticker || r.asset || '',
    price: r.price ?? r.last ?? r.close,
    d1m: r.delta_1m ?? r.t1m ?? r.change_1m ?? r.delta ?? null,
  }));
};

export default function TopOneMinGainers() {
  const [limit, setLimit] = useState(8);
  const { data, loading, error } = useEndpoint(API_ENDPOINTS.gainersTable1Min, { pollMs: 15000 });
  const items = useMemo(() => normalize(data).slice(0, limit), [data, limit]);

  const mid = Math.ceil(items.length / 2);
  const left = items.slice(0, mid);
  const right = items.slice(mid);

  return (
    <div className="app-panel">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/60">
        <h3 className="text-sm font-semibold tracking-wide text-[color:var(--ink)]">TOP 1-MIN GAINERS</h3>
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400">Show</label>
          <select className="bg-[#0e0e16] border border-white/10 rounded px-2 py-1 text-xs" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            <option value={8}>Top 8 (4 + 4)</option>
            <option value={16}>Top 16 (8 + 8)</option>
          </select>
        </div>
      </div>

      {loading && <div className="p-3 text-sm text-zinc-400 text-center">Loading…</div>}
      {error && <div className="p-3 text-sm text-red-400 text-center">Error loading data.</div>}
      {!loading && !error && items.length === 0 && <div className="p-3 text-sm text-zinc-400 text-center">No 1-min data.</div>}

      {!loading && !error && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-3">
          <div className="rounded-lg border border-white/10 bg-[#10101a] overflow-hidden">
            <div className="px-3 py-2 border-b border-white/10 text-[11px] tracking-wide text-zinc-400">RANKED 1-MIN (A)</div>
            <table className="app-table">
              <thead>
                <tr>
                  <th className="w-10 pl-3 text-left">#</th>
                  <th className="text-left">Symbol</th>
                  <th className="text-right pr-3">Price</th>
                  <th className="w-20 text-right pr-3">1-m</th>
                </tr>
              </thead>
              <tbody>
                {left.map((r, idx) => (
                  <tr key={`${r.symbol}-L-${idx}`} className={idx % 2 ? 'bg-zinc-900/20' : ''}>
                    <td className="pl-3 text-zinc-400">{r.rank}</td>
                    <td className="font-semibold">{(r.symbol || '').toUpperCase()}</td>
                    <td className="text-right pr-3 tabular-nums">{fmtUSD(r.price, 2, 6)}</td>
                    <td className={`text-right pr-3 tabular-nums ${clsDelta(r.d1m)}`}>{asPctAuto(r.d1m)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="rounded-lg border border-white/10 bg-[#10101a] overflow-hidden">
            <div className="px-3 py-2 border-b border-white/10 text-[11px] tracking-wide text-zinc-400">RANKED 1-MIN (B)</div>
            <table className="app-table">
              <thead>
                <tr>
                  <th className="w-10 pl-3 text-left">#</th>
                  <th className="text-left">Symbol</th>
                  <th className="text-right pr-3">Price</th>
                  <th className="w-20 text-right pr-3">1-m</th>
                </tr>
              </thead>
              <tbody>
                {right.map((r, idx) => (
                  <tr key={`${r.symbol}-R-${idx}`} className={idx % 2 ? 'bg-zinc-900/20' : ''}>
                    <td className="pl-3 text-zinc-400">{r.rank}</td>
                    <td className="font-semibold">{(r.symbol || '').toUpperCase()}</td>
                    <td className="text-right pr-3 tabular-nums">{fmtUSD(r.price, 2, 6)}</td>
                    <td className={`text-right pr-3 tabular-nums ${clsDelta(r.d1m)}`}>{asPctAuto(r.d1m)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
