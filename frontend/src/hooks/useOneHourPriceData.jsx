import { useEffect, useRef, useState } from "react";

/**
 * Hook for fetching 1-hour price data via HTTP polling
 * Uses AbortController to prevent overlapping requests
 * Staggered polling interval (default 5s)
 */
export default function useOneHourPriceData(pollInterval = 5000) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

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

        const res = await fetch("/api/snapshots/one-hour-price", { signal: ac.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();
        if (!mounted) return;

        // Extract rows from response (handles both {rows: [...]} and direct array)
        const data = Array.isArray(json?.rows) ? json.rows : (Array.isArray(json) ? json : []);
        setRows(data);
        setError(null);
      } catch (e) {
        if (!mounted) return;
        if (e.name !== "AbortError") {
          setError(e);
          console.error("Failed to fetch price data:", e);
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
  }, [pollInterval]);

  return { rows, loading, error };
}
