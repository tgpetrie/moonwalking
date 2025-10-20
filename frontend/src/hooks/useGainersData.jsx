import { useEffect, useRef, useState } from "react";
import { fetchComponent } from "../api.js";

/**
 * Hook for fetching gainers table data via HTTP polling
 * Uses AbortController to prevent overlapping requests
 * Supports both 1-min and 3-min windows
 */
export default function useGainersData({ window = "3min", pollInterval = 6000 }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [raw, setRaw] = useState(null);
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

  const result = await fetchComponent(endpoint, { signal: ac.signal });
  const data = result.rows;
  // preserve the raw payload so callers can inspect meta (eg. seeded flag)
  setRaw(result.raw ?? null);
        if (!mounted) return;

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

    // Stagger initial fetch slightly to avoid synchronized requests across windows
    const jitter = Math.floor(Math.random() * Math.min(1500, Math.max(0, pollInterval)));
    timer = setTimeout(() => {
      fetchData();
      // After the initial jittered run, poll regularly
      timer = setInterval(fetchData, pollInterval);
    }, jitter);

    return () => {
      mounted = false;
      clearInterval(timer);
      abortRef.current?.abort();
    };
  }, [endpoint, pollInterval, window]);

  return { rows, loading, error, raw };
}
