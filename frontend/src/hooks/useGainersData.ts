import React from 'react';

// @ts-ignore - Vite injects import.meta.env at build/runtime
const API_BASE = (import.meta as any).env?.VITE_API_BASE || '';
// @ts-ignore
const pollMs = Number((import.meta as any).env?.VITE_POLL_MS || 10000);

async function fetchJSON(url: string) {
  const r = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default function useGainersData() {
  const [data, setData] = React.useState<any[]>([]);
  const [isLoading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<any>(null);

  React.useEffect(() => {
    let alive = true;

    async function tick() {
      try {
        const j = await fetchJSON(`${API_BASE}/api/component/gainers-table-1min`);
        const rows = Array.isArray(j) ? j : (j?.data ?? []);
        if (alive) {
          setData(rows);
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
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return { data, isLoading, error };
}
