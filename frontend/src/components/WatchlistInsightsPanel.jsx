import React, { useEffect, useState, useCallback } from 'react';
import { API_ENDPOINTS } from '../api.js';

export default function WatchlistInsightsPanel() {
  const [insights, setInsights] = useState([]);
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [auto, setAuto] = useState(true);

  const fetchInsights = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(API_ENDPOINTS.watchlistInsights);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setInsights(data.insights || []);
      setRaw(data.raw || '');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

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
      {raw && (
        <details className="mt-3 opacity-60 hover:opacity-100 transition">
          <summary className="cursor-pointer select-none">Raw</summary>
          <pre className="mt-2 whitespace-pre-wrap text-[10px] leading-tight max-h-32 overflow-auto">{raw}</pre>
        </details>
      )}
    </div>
  );
}
