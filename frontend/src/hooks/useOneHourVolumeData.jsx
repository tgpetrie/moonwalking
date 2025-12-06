import { useEffect, useRef, useState } from "react";
import { fetchJson } from "../api";

/**
 * Hook for fetching 1-hour volume data via HTTP polling
 * Uses AbortController to prevent overlapping requests
 * Staggered polling interval (default 7s to avoid sync with price hook)
 */
export default function useOneHourVolumeData(pollInterval = 7000) {
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

        const json = await fetchJson("/api/snapshots/one-hour-volume", { signal: ac.signal });
        if (!mounted) return;

        // Extract rows from response
        const data = Array.isArray(json?.data)
          ? json.data
          : Array.isArray(json?.rows)
          ? json.rows
          : Array.isArray(json)
          ? json
          : [];

        // Normalize to ensure volume percent change is available for the UI
        const normalized = data.map((item) => {
          const volNow =
            item.volume_now ?? item.volume ?? item.vol_now ?? item.now ?? item.current_volume ?? null;
          const volAgo =
            item.volume_1h_ago ?? item.prev_volume ?? item.volume_prev ?? item.ago ?? item.previous_volume ?? null;
          let pct = item.volume_change_pct ?? item.percent_change ?? null;

          if (
            (pct === null || Number.isNaN(pct)) &&
            typeof volNow === "number" &&
            typeof volAgo === "number" &&
            isFinite(volNow) &&
            isFinite(volAgo) &&
            volAgo > 0
          ) {
            pct = ((volNow - volAgo) / volAgo) * 100;
          }

          return {
            ...item,
            volume_now: volNow,
            volume_1h_ago: volAgo,
            volume_change_pct: pct,
            // Many UI components expect `percent_change`; mirror it if missing
            percent_change: pct,
          };
        });

        setRows(normalized);
        setError(null);
      } catch (e) {
        if (!mounted) return;
        if (e.name !== "AbortError") {
          setError(e);
          console.error("Failed to fetch volume data:", e);
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
