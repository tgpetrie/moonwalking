import React, { useState } from 'react';
import { API_ENDPOINTS } from '../api.js';
import usePollingFetch from '../hooks/usePollingFetch.js';

export default function WatchlistInsightsPanel() {
  const [auto, setAuto] = useState(true);

  const { data, loading, error, refresh } = usePollingFetch(
    API_ENDPOINTS.watchlistInsights,
    { interval: 15000, auto }
  );

  // Derived state from the hook's data
  const insights = data?.insights || [];
  const raw = data?.raw || '';

  return (
    <div className="bg-black/60 backdrop-blur-sm border border-purple-800 rounded-xl p-4 w-96 max-w-full text-xs font-mono shadow-lg">
      <div className="flex items-center justify-between mb-2">
  <h3 className="color-lock-purple font-bold tracking-wide text-sm">WATCHLIST INSIGHTS</h3>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} />
            <span className="text-[10px] uppercase tracking-wider">Auto</span>
          </label>
          <button
            onClick={refresh}
            disabled={loading}
            className="px-2 py-0.5 rounded bg-purple-700 hover:bg-purple-600 text-white text-[10px] disabled:opacity-50"
          >{loading ? '...' : 'Refresh'}</button>
        </div>
      </div>
      {loading && <div className="text-blue-300 animate-pulse">Loading...</div>}
      {error && <div className="text-pink-400">Error: {error}</div>}
      {!loading && !error && insights.length === 0 && (
        <div className="text-gray-400">No current alerts or suggestions.</div>
      )}
      <ul className="space-y-1 max-h-56 overflow-auto pr-1 custom-scrollbar">
        {insights.map((line, index) => {
          const key = `${line.slice(0, 20)}-${index}`;
          return (
            <li key={key} className="leading-snug">
              {line.startsWith('⚠️') && <span className="text-yellow-400">{line}</span>}
              {line.startsWith('📈') && <span className="text-green-400">{line}</span>}
              {line.startsWith('😐') && <span className="text-gray-300">{line}</span>}
              {line.startsWith('🤖') && <span className="text-blue-300">{line}</span>}
              {!['⚠️','📈','😐','🤖'].some(p => line.startsWith(p)) && <span>{line}</span>}
            </li>
          );
        })}
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
