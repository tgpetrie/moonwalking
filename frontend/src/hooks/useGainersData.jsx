import { useEffect, useRef, useState } from "react";

/**
 * Hook for fetching gainers table data via HTTP polling
 * Uses AbortController to prevent overlapping requests
 * Supports both 1-min and 3-min windows
 */
export default function useGainersData({ window = "3min", pollInterval = 6000 }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  // Determine endpoint based on window
  const endpoint = window === "1min"
    ? "/api/component/gainers-table-1min"
    : "/api/component/gainers-table-3min";

  useEffect(() => {
    let mounted = true;
    let timer;

    const fetchData = async () => {
      try {
        // Abort any in-flight request
        abortRef.current?.abort();
        const ac = new AbortController();
        abortRef.current = ac;

        setLoading(true);

        const res = await fetch(endpoint, { signal: ac.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();
        if (!mounted) return;

        // Extract rows from response
        const data = Array.isArray(json?.rows) ? json.rows : (Array.isArray(json) ? json : []);
        setRows(data);
        setError(null);
      } catch (e) {
        if (!mounted) return;
        if (e.name !== "AbortError") {
          setError(e);
          console.error(`Failed to fetch ${window} gainers:`, e);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    // Initial fetch
    fetchData();

    // Poll on interval
    timer = setInterval(fetchData, pollInterval);

    return () => {
      mounted = false;
      clearInterval(timer);
      abortRef.current?.abort();
    };
  }, [endpoint, pollInterval, window]);

  return { rows, loading, error };
}
