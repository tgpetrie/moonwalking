// src/components/TopBannerScroll.jsx
import { useEffect, useRef, useState } from 'react';
import { getJSON } from '../lib/api';

// Hoisted helpers (defined before first use)
function getBadgeStyle(pct) {
  if (pct == null || Number.isNaN(pct)) return 'bg-zinc-600';
  if (pct >= 5) return 'bg-green-600';
  if (pct > 0) return 'bg-green-500/70';
  if (pct <= -5) return 'bg-red-600';
  if (pct < 0) return 'bg-red-500/70';
  return 'bg-zinc-600';
}

function formatPct(pct) {
  if (pct == null || Number.isNaN(pct)) return '';
  const n = Number(pct);
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

export default function TopBannerScroll() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    let stop = false;

    async function poll() {
      try {
        setError(null);
        // Backend returns { component, data, last_updated } (or a bare array)
        const payload = await getJSON('/api/component/top-banner-scroll');

        const items = Array.isArray(payload?.data)
          ? payload.data
          : Array.isArray(payload?.items)
          ? payload.items
          : Array.isArray(payload)
          ? payload
          : [];

        if (!stop) setRows(items);
      } catch (e) {
        if (!stop) setError(e instanceof Error ? e : new Error(String(e)));
      } finally {
        if (!stop) timerRef.current = setTimeout(poll, 3000);
      }
    }

    poll();
    return () => {
      stop = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  if (error) {
    return <div className="text-xs text-red-400">Banner error: {error.message}</div>;
  }

  if (!rows.length) {
    return <div className="text-xs text-zinc-400">No movers</div>;
  }

  return (
    <div className="flex gap-3 overflow-x-auto whitespace-nowrap px-2 py-1">
      {rows.map((it, idx) => {
        const symbol = it.symbol ?? it.ticker ?? it.name ?? `#${idx}`;
        const changePct = Number(it.change_pct ?? it.changePct ?? it.pct ?? it.change);
        return (
          <span key={`${symbol}-${idx}`} className="inline-flex items-center gap-2">
            <span className="text-zinc-300">{symbol}</span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] text-white ${getBadgeStyle(changePct)}`}>
              {formatPct(changePct)}
            </span>
          </span>
        );
      })}
    </div>
  );
}
