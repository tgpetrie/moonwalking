import React, { useEffect, useMemo, useRef, useState } from 'react';
import { endpoints, httpGet as fetchData } from '../lib/api';

const AlertsIndicator = () => {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const seenCountRef = useRef(0);
  const pollMs = useMemo(() => {
    const v = Number(import.meta?.env?.VITE_ALERTS_POLL_MS);
    return Number.isFinite(v) && v >= 5000 ? v : 30000; // default 30s, min 5s
  }, []);
  const timerRef = useRef(null);

  const alertsEnabled = String(import.meta?.env?.VITE_ALERTS_ENABLED || '').toLowerCase() === 'true';

  useEffect(() => {
    if (!alertsEnabled) return; // gate off in dev unless explicitly enabled
    let mounted = true;
    const limit = 25;
    const poll = async () => {
      try {
  const url = endpoints.alertsRecent(limit);
  const res = await fetchData(url);
        if (!mounted) return;
        if (res && Array.isArray(res.alerts)) {
          setItems(res.alerts.slice(-limit));
          setCount(res.alerts.length);
          setError(null);
        }
      } catch (e) {
        if (!mounted) return;
        console.warn('alerts poll failed', e);
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
  }, [pollMs, alertsEnabled]);

  // When the panel opens, mark current count as seen so badge resets
  useEffect(() => {
    if (open) seenCountRef.current = count;
  }, [open, count]);

  // Badge-only UI; unseen count logic retained for future but not rendered

  if (!alertsEnabled) {
    // Render a tiny disabled indicator to preserve layout spacing
    return (
      <div className="relative">
        <button
          className="flex items-center justify-center w-7 h-7 rounded-full bg-gray-700 text-gray-300 text-[10px] font-extrabold opacity-60 cursor-not-allowed"
          title="Alerts disabled"
          aria-label="Alerts disabled"
        >
          —
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-center w-7 h-7 rounded-full bg-pink-500 text-white text-[10px] font-extrabold shadow-lg hover:brightness-110"
        title={error ? `Alerts: ${error}` : `Recent alerts (${count})`}
        aria-label="Open alerts"
      >
        {Math.max(0, count)}
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
                    href={`https://www.coinbase.com/trade/${(a.symbol||'').toLowerCase()}-USD`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-bold hover:text-amber-400"
                  >
                    {a.symbol}
                  </a>
                  {(() => {
                    const isUp = a.direction === 'up';
                    const isDown = a.direction === 'down';
                    let cls = 'text-gray-300';
                    if (isUp) cls = 'text-green-300';
                    else if (isDown) cls = 'text-red-300';
                    let glyph = '·';
                    if (isUp) glyph = '↑';
                    else if (isDown) glyph = '↓';
                    return <span className={cls}>{glyph}</span>;
                  })()}
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
