import React from 'react';
const API_BASE = import.meta.env.VITE_API_BASE || "";
const pollMs = Number(import.meta.env.VITE_POLL_MS || 10000);

async function fetchJSON(url) {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function useGainersLosersData() {
  const [data, setData] = React.useState([]);
  const [isLoading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const j = await fetchJSON(`${API_BASE}/api/component/gainers-table`);
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
    return () => { alive = false; clearInterval(id); };
  }, []);

  return { data, isLoading, error };
}

export { useGainersLosersData };
export default useGainersLosersData;
