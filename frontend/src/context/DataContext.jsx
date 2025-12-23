import { createContext, useCallback, useEffect, useMemo, useRef, useState, useContext } from "react";
import { fetchAllData } from "../api";

const DataContext = createContext(null);
export const useData = () => useContext(DataContext);

// Environment-driven cadence knobs (defaults optimized for N100)
const FETCH_MS = Number(import.meta.env.VITE_FETCH_MS || 8000);
const PUBLISH_3M_MS = Number(import.meta.env.VITE_PUBLISH_3M_MS || 30000);
const PUBLISH_BANNER_MS = Number(import.meta.env.VITE_PUBLISH_BANNER_MS || 120000);
const STAGGER_MS = Number(import.meta.env.VITE_ROW_STAGGER_MS || 65);

// Normalize backend response to canonical shape
function normalizeApiData(payload) {
  const p = payload || {};

  // Support both top-level and nested .data structures
  const gainers_1m = p.gainers_1m ?? p.data?.gainers_1m ?? p.gainers1m ?? [];
  const gainers_3m = p.gainers_3m ?? p.data?.gainers_3m ?? p.gainers3m ?? [];
  const losers_3m  = p.losers_3m  ?? p.data?.losers_3m  ?? p.losers3m  ?? [];

  const banner_1h_price  = p.banner_1h_price  ?? p.data?.banner_1h_price  ?? p.banner_1h ?? p.top_banner_1h ?? [];
  const banner_1h_volume = p.banner_1h_volume ?? p.data?.banner_1h_volume ?? p.volume_banner_1h ?? [];

  const latest_by_symbol = p.latest_by_symbol ?? p.data?.latest_by_symbol ?? {};
  const updated_at       = p.updated_at       ?? p.data?.updated_at       ?? Date.now();

  return {
    gainers_1m,
    gainers_3m,
    losers_3m,
    banner_1h_price,
    banner_1h_volume,
    latest_by_symbol,
    updated_at,
    meta: p.meta ?? p.data?.meta ?? {},
    errors: p.errors ?? p.data?.errors ?? [],
    coverage: p.coverage ?? p.data?.coverage ?? null,
  };
}

export function DataProvider({ children }) {
  // "Published" slices that drive the UI at different cadences
  const [oneMinRows, setOneMinRows] = useState([]);
  const [threeMin, setThreeMin] = useState({ gainers: [], losers: [] });
  const [banners, setBanners] = useState({ price: [], volume: [] });
  const [latestBySymbol, setLatestBySymbol] = useState({});

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastFetchTs, setLastFetchTs] = useState(null);
  const [heartbeatPulse, setHeartbeatPulse] = useState(false);

  // Timing refs for gated publishing
  const last3mPublishRef = useRef(0);
  const lastBannerPublishRef = useRef(0);
  const latestNormalizedRef = useRef(null);
  const abortRef = useRef(null);
  const staggerTokenRef = useRef(null);
  const heartbeatTimerRef = useRef(null);

  // Staggered commit for 1m rows (creates "live feel")
  const staggerCommit1m = useCallback((nextRows) => {
    // Cancel any in-flight stagger cycle
    const token = Symbol("stagger");
    staggerTokenRef.current = token;

    if (!Array.isArray(nextRows) || nextRows.length === 0) {
      setOneMinRows([]);
      return;
    }

    // For drastic count changes, commit immediately
    if (nextRows.length <= 1) {
      setOneMinRows(nextRows);
      return;
    }

    // Start with current rows to avoid jarring "teleport"
    setOneMinRows(prev => {
      const base = Array.isArray(prev) && prev.length ? [...prev] : [...nextRows];
      return base;
    });

    // Stagger individual row updates for smooth animation
    nextRows.forEach((row, i) => {
      setTimeout(() => {
        if (staggerTokenRef.current !== token) return; // Stale stagger, abort
        setOneMinRows(prev => {
          const arr = Array.isArray(prev) ? [...prev] : [];
          arr[i] = row;
          return arr;
        });
      }, i * STAGGER_MS);
    });
  }, []);

  const fetchData = useCallback(async () => {
    try {
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = new AbortController();

      const json = await fetchAllData();
      const norm = normalizeApiData(json);
      const now = Date.now();

      latestNormalizedRef.current = norm;
      setLatestBySymbol(norm.latest_by_symbol || {});
      setError(null);
      setLoading(false);

      // 1m: every fetch, but stagger the row commits for "live feel"
      staggerCommit1m(norm.gainers_1m);

      setLastFetchTs(now);
      setHeartbeatPulse(true);
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
      }
      heartbeatTimerRef.current = setTimeout(() => {
        setHeartbeatPulse(false);
      }, 420);

      // 3m: publish every PUBLISH_3M_MS (default 30s)
      if (now - last3mPublishRef.current >= PUBLISH_3M_MS) {
        last3mPublishRef.current = now;
        setThreeMin({ gainers: norm.gainers_3m, losers: norm.losers_3m });
      }

      // banners: publish every PUBLISH_BANNER_MS (default 2 minutes)
      if (now - lastBannerPublishRef.current >= PUBLISH_BANNER_MS) {
        lastBannerPublishRef.current = now;
        setBanners({ price: norm.banner_1h_price, volume: norm.banner_1h_volume });
      }
    } catch (e) {
      if (e.name === 'AbortError') return;
      console.warn('[DataContext] Fetch failed:', e.message);
      setError(e);
      setLoading(false);
    }
  }, [staggerCommit1m]);

  useEffect(() => {
    let mounted = true;

    const doFetch = async () => {
      if (!mounted) return;
      await fetchData();
    };

    // Initial fetch
    doFetch();

    // One fast fetch interval, multiple publish cadences
    const id = setInterval(doFetch, FETCH_MS);

    return () => {
      mounted = false;
      clearInterval(id);
      if (abortRef.current) abortRef.current.abort();
      staggerTokenRef.current = null;
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    };
  }, [fetchData]);

  // Legacy compatibility: combine all published slices
  const combinedData = useMemo(() => ({
    gainers_1m: oneMinRows,
    gainers_3m: threeMin.gainers,
    losers_3m: threeMin.losers,
    banner_1h_price: banners.price,
    top_banner_1h: banners.price, // Legacy alias
    banner_1h_volume: banners.volume,
    volume_banner_1h: banners.volume, // Legacy alias
    latest_by_symbol: latestBySymbol,
    updated_at: latestNormalizedRef.current?.updated_at ?? Date.now(),
  }), [oneMinRows, threeMin, banners, latestBySymbol]);

  const value = useMemo(() => ({
    data: combinedData,
    oneMinRows,
    threeMin,
    banners,
    latestBySymbol,
    error,
    loading,
    refetch: fetchData,
    heartbeatPulse,
    lastFetchTs,
  }), [combinedData, oneMinRows, threeMin, banners, latestBySymbol, error, loading, fetchData, heartbeatPulse, lastFetchTs]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
