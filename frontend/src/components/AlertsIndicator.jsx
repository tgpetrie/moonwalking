import React, { useEffect, useMemo, useRef, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';

const AlertsIndicator = () => {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const [seenCount, setSeenCount] = useState(0);
  const pollMs = useMemo(() => {
    const v = Number(import.meta?.env?.VITE_ALERTS_POLL_MS);
    return Number.isFinite(v) && v >= 5000 ? v : 30000; // default 30s, min 5s
  }, []);
  const timerRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    const limit = 25;
    const poll = async () => {
      try {
        const url = (API_ENDPOINTS.alertsRecent || '/api/alerts/recent') + `?limit=${limit}`;
        const res = await fetchData(url);
        if (!mounted) return;
        if (res && Array.isArray(res.alerts)) {
          setItems(res.alerts.slice(-limit));
          setCount(res.alerts.length);
          setError(null);
        }
      } catch (e) {
        if (!mounted) return;
        setError('alerts offline');
      } finally {
        timerRef.current = setTimeout(poll, pollMs);
      }
    };
    poll();
    return () => {
      mounted = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [pollMs]);

  // When the panel opens, mark current count as seen so badge resets
  useEffect(() => {
    if (open) setSeenCount(count);
  }, [open, count]);

  const unseen = Math.max(0, count - seenCount);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-1 rounded bg-gray-800 text-white text-xs font-semibold hover:bg-gray-700"
        title={error ? `Alerts: ${error}` : `Recent alerts (${count})`}
      >
        <span>Alerts</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${count>0 ? 'bg-orange-500 text-white' : 'bg-gray-600 text-gray-200'}`}>{count}</span>
        {unseen > 0 && (
          <span className="px-1 py-0.5 rounded bg-red-600 text-white text-[10px] leading-none">NEW {unseen}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-72 overflow-auto rounded border border-gray-700 bg-black/90 shadow-lg z-50">
          <div className="p-2 text-xs text-gray-300 border-b border-gray-700">Recent alerts</div>
          <ul className="divide-y divide-gray-800">
            {items.length === 0 && (
              <li className="p-3 text-xs text-gray-500">No alerts yet.</li>
            )}
            {items.map((a, i) => (
              <li key={`${a.ts}-${a.symbol}-${i}`} className="p-2 text-xs text-gray-200">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-gray-400">{a.ts?.replace('T',' ')?.slice(0,19)}</span>
                  <span className="ml-2 px-1 py-0.5 rounded bg-gray-700 text-[10px]">{a.scope}</span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <a
                    href={`https://www.coinbase.com/advanced-trade/spot/${(a.symbol||'').toLowerCase()}-USD`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-bold hover:text-amber-400"
                  >
                    {a.symbol}
                  </a>
                  <span className={`${a.direction==='up'?'text-green-300':'text-red-300'}`}>{a.direction === 'up' ? '↑' : a.direction === 'down' ? '↓' : '·'}</span>
                  {typeof a.streak === 'number' && a.streak > 0 && (
                    <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none">x{a.streak}</span>
                  )}
                  <span className="text-[10px] text-gray-400">score {Number(a.score||0).toFixed(2)}</span>
                </div>
                {a.message && <div className="mt-1 text-[11px] text-gray-400">{a.message}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default AlertsIndicator;
