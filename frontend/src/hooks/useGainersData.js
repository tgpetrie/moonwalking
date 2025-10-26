import React from 'react';
import { endpoints } from '../lib/api.ts';
const pollMs = Number(import.meta.env.VITE_POLL_MS || 10000);

async function fetchJSON(url) {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function useGainersData() {
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let alive = true;
    async function tick() {
      try {
  // Backend defines /api/component/gainers-table (3-minute data)
  const j = await fetchJSON(endpoints.gainers);
        const raw = Array.isArray(j) ? j : (j?.data ?? []);
        // Normalize to { symbol, changePct } expected by the card
        const pickChangePct = (row) => {
          if (typeof row.price_change_percentage_3min === 'number') return row.price_change_percentage_3min;
          if (typeof row.gain === 'number') return row.gain;
          return row.changePct;
        };
        const data = raw.map((r) => ({
          symbol: r.symbol || r.ticker || r.sym || r.Symbol,
          changePct: pickChangePct(r),
        })).filter((r) => r.symbol);
        if (alive) {
          setRows(data);
          setLoading(false);
        }
      } catch (e) {
        if (alive) {
          setError(e);
          setLoading(false);
        }
      }
    }
    tick();
    const id = setInterval(tick, pollMs);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return { rows, loading, error };
}

export { useGainersData };
export default useGainersData;
