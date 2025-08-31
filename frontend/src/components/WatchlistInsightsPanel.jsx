import React, { useEffect, useState, useCallback } from 'react';
import { API_ENDPOINTS, getWatchlist, fetchLatestAlerts } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';

export default function WatchlistInsightsPanel() {
  const [insights, setInsights] = useState([]);
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [auto, setAuto] = useState(true);
  const { latestData } = useWebSocket();
  const [showAlerts, setShowAlerts] = useState(() => {
    try { return localStorage.getItem('insights:showAlerts') === '1'; } catch { return false; }
  });
  const [maxAlerts, setMaxAlerts] = useState(() => {
    const v = Number(localStorage.getItem('insights:maxAlerts') || '3');
    return Number.isFinite(v) && v > 0 ? v : 3;
  });
  const [latest, setLatest] = useState({});

  // Local helper: derive insights from WS + local watchlist when server is unavailable
  const buildClientInsights = useCallback(async () => {
    try {
      const wl = await getWatchlist();
      const items = (Array.isArray(wl) ? wl : []).map((it) =>
        typeof it === 'string' ? { symbol: it, priceAtAdd: 0 } : { symbol: it.symbol, priceAtAdd: Number(it.priceAtAdd) || 0 }
      ).filter(x => x && x.symbol);
      if (items.length === 0) {
        return { insights: ['😐 No symbols in watchlist yet. Click ⭐ to add.'], raw: '' };
      }
      // Get current prices
      const priceMap = {};
      if (latestData?.prices) {
        Object.assign(priceMap, latestData.prices);
      }
      if (Array.isArray(latestData?.crypto)) {
        latestData.crypto.forEach(c => {
          const s = (c.symbol?.replace('-USD','') || c.symbol);
          if (s) priceMap[s] = { price: c.current_price ?? c.price, change: c.change ?? c.price_change_percentage_1min };
        });
      }
      // Compute since-added
      const computed = items.map(it => {
        const cur = priceMap[it.symbol]?.price;
        const pct = (it.priceAtAdd > 0 && typeof cur === 'number') ? ((cur - it.priceAtAdd) / it.priceAtAdd) * 100 : null;
        return { symbol: it.symbol, pctSince: pct };
      });
      const withPct = computed.filter(x => x.pctSince !== null);
      const up = [...withPct].sort((a,b) => (b.pctSince - a.pctSince))[0];
      const down = [...withPct].sort((a,b) => (a.pctSince - b.pctSince))[0];
      const breadth = withPct.length ? (withPct.filter(x => x.pctSince >= 0).length / withPct.length) : 0;
      const lines = [];
      if (up) lines.push(`📈 Top since‑added: ${up.symbol} +${up.pctSince.toFixed(2)}%`);
      if (down && down.symbol !== up?.symbol) lines.push(`⚠️ Weakest since‑added: ${down.symbol} ${down.pctSince.toFixed(2)}%`);
      lines.push(`🤖 Breadth (since‑added > 0): ${(breadth*100).toFixed(0)}%`);
      if (lines.length === 0) lines.push('😐 No price context yet. Waiting for live data...');
      return { insights: lines, raw: '' };
    } catch (e) {
      return { insights: ['😐 Insights unavailable (client)'], raw: '' };
    }
  }, [latestData]);

  const fetchInsights = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(API_ENDPOINTS.watchlistInsights);
      if (res.ok) {
        const data = await res.json();
        setInsights(Array.isArray(data.insights) ? data.insights : []);
        setRaw(typeof data.raw === 'string' ? data.raw : '');
      } else {
        // Fallback to client insights when server returns 4xx/5xx
        const local = await buildClientInsights();
        setInsights(local.insights);
        setRaw(local.raw);
      }
    } catch (e) {
      // Network error: fallback to client insights but also expose a small error string
      setError(null);
      const local = await buildClientInsights();
      setInsights(local.insights);
      setRaw(local.raw);
    } finally {
      setLoading(false);
    }
  }, [buildClientInsights]);

  // Optional: fetch minimal latest alerts on demand
  const fetchLatest = useCallback(async () => {
    try {
      const wl = await getWatchlist();
      const symbols = (Array.isArray(wl) ? wl : []).map((it) => typeof it === 'string' ? it : it.symbol).filter(Boolean);
      if (!symbols.length) { setLatest({}); return; }
      const data = await fetchLatestAlerts(symbols.slice(0, 30)); // cap payload
      setLatest(data || {});
    } catch {
      setLatest({});
    }
  }, []);

  useEffect(() => {
    try { localStorage.setItem('insights:showAlerts', showAlerts ? '1' : '0'); } catch {}
    if (showAlerts) fetchLatest();
  }, [showAlerts, fetchLatest]);

  useEffect(() => {
    try { localStorage.setItem('insights:maxAlerts', String(maxAlerts)); } catch {}
  }, [maxAlerts]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  useEffect(() => {
    if (!auto) return;
    const id = setInterval(fetchInsights, 15000);
    return () => clearInterval(id);
  }, [auto, fetchInsights]);

  return (
    <div className="bg-black/60 backdrop-blur-sm border border-purple-800 rounded-xl p-4 w-96 max-w-full text-xs font-mono shadow-lg">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-purple font-bold tracking-wide text-sm">WATCHLIST INSIGHTS</h3>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} />
            <span className="text-[10px] uppercase tracking-wider">Auto</span>
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showAlerts} onChange={e => setShowAlerts(e.target.checked)} />
            <span className="text-[10px] uppercase tracking-wider">Alerts</span>
          </label>
          <button
            onClick={fetchInsights}
            className="px-2 py-0.5 rounded bg-purple-700 hover:bg-purple-600 text-white text-[10px]"
          >Refresh</button>
        </div>
      </div>
      {loading && <div className="text-blue-300 animate-pulse">Loading...</div>}
      {error && <div className="text-pink-400">Error: {error}</div>}
      {!loading && !error && insights.length === 0 && (
        <div className="text-gray-400">No current alerts or suggestions.</div>
      )}
      <ul className="space-y-1 max-h-56 overflow-auto pr-1 custom-scrollbar">
        {insights.map((line, i) => (
          <li key={i} className="leading-snug">
            {line.startsWith('⚠️') && <span className="text-yellow-400">{line}</span>}
            {line.startsWith('📈') && <span className="text-green-400">{line}</span>}
            {line.startsWith('😐') && <span className="text-gray-300">{line}</span>}
            {line.startsWith('🤖') && <span className="text-blue-300">{line}</span>}
            {!['⚠️','📈','😐','🤖'].some(p => line.startsWith(p)) && <span>{line}</span>}
          </li>
        ))}
      </ul>

      {showAlerts && (
        <div className="mt-3 pt-2 border-t border-purple-900/40">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-purple-200">Latest Alerts</span>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-gray-400">max</span>
              <select
                className="bg-black/40 border border-purple-900 text-[10px] rounded px-1 py-0.5 text-gray-200"
                value={maxAlerts}
                onChange={e => setMaxAlerts(Number(e.target.value))}
              >
                {[3,5,10].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
              <button onClick={fetchLatest} className="px-1.5 py-0.5 rounded bg-purple-700 hover:bg-purple-600 text-white text-[10px]">Refresh</button>
            </div>
          </div>
          <ul className="space-y-1 max-h-32 overflow-auto pr-1">
            {Object.entries(latest).slice(0, maxAlerts).map(([sym, msg]) => (
              <li key={sym} className="leading-snug">
                <span className="text-gray-300">{sym}:</span> <span className="text-gray-200">{String(msg)}</span>
              </li>
            ))}
            {Object.keys(latest || {}).length === 0 && (
              <li className="text-gray-500">No recent alerts.</li>
            )}
          </ul>
        </div>
      )}
      {raw && (
        <details className="mt-3 opacity-60 hover:opacity-100 transition">
          <summary className="cursor-pointer select-none">Raw</summary>
          <pre className="mt-2 whitespace-pre-wrap text-[10px] leading-tight max-h-32 overflow-auto">{raw}</pre>
        </details>
      )}
    </div>
  );
}
