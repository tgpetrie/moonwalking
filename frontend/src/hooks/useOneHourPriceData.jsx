import { useEffect, useRef, useState } from "react";
import { endpoints } from "../lib/api";

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

  // Use centralized endpoint for one-hour banner data.
  const res = await fetch(endpoints.banner1h, { signal: ac.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();
        if (!mounted) return;

        // Extract rows from response (handles {data: [...]}, legacy {rows: [...]}, or direct array)
        let data = [];
        if (Array.isArray(json?.data)) data = json.data;
        else if (Array.isArray(json?.rows)) data = json.rows;
        else if (Array.isArray(json)) data = json;
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
