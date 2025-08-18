import { useEffect, useRef, useState } from 'react';
import { getJSON } from '../lib/api';

export default function AlertsIndicator() {
  const [count, setCount] = useState(0);
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState(null); // <-- define error state
  const timerRef = useRef(null);

  useEffect(() => {
    let aborted = false;
  const pollMs = Number(import.meta.env.VITE_ALERTS_POLL_MS ?? 10000);

  async function tick() {
      try {
        setError(null);
        const data = await getJSON('/api/alerts/recent?limit=25');
        if (aborted) return;
        const items = Array.isArray(data?.alerts)
          ? data.alerts
          : Array.isArray(data)
          ? data
          : [];
        setCount(items.length);
        setLatest(items[0] || null);
      } catch (err) {
        setError(err)
      } finally {
        if (!aborted) timerRef.current = window.setTimeout(tick, Math.max(5000, pollMs));
      }
    }

    tick();
    return () => {
      aborted = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div className="flex items-center gap-2 text-xs">
      <div
        className={[
          'w-2 h-2 rounded-full',
          error ? 'bg-red-500 animate-pulse' : count > 0 ? 'bg-purple-500' : 'bg-zinc-500',
        ].join(' ')}
      />
      <span className="font-medium">Alerts</span>
      <span className="tabular-nums">{count}</span>
      {latest && (
        <span className="text-zinc-400 truncate max-w-[18ch]">
          • {latest.symbol ?? latest.ticker ?? latest.name ?? '—'}
        </span>
      )}
      {error && <span className="text-red-400 truncate max-w-[40ch]">• {error.message}</span>}
    </div>
  );
}
