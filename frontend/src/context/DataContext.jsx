import { createContext, useCallback, useEffect, useMemo, useRef, useState, useContext } from "react";
import { fetchAllData } from "../api";

const DataContext = createContext(null);
export const useData = () => useContext(DataContext);

const LS_KEY = "bh_last_payload_v1";
const FAST_1M_MS = Number(import.meta.env.VITE_FAST_1M_MS || 3000);

const readCachedPayload = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

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
  const cachedNormalized = useMemo(() => {
    const cached = readCachedPayload();
    return cached ? normalizeApiData(cached) : null;
  }, []);

  // "Published" slices that drive the UI at different cadences
  const [oneMinRows, setOneMinRows] = useState(() => cachedNormalized?.gainers_1m ?? []);
  const [threeMin, setThreeMin] = useState(() => ({
    gainers: cachedNormalized?.gainers_3m ?? [],
    losers: cachedNormalized?.losers_3m ?? [],
  }));
  const [banners, setBanners] = useState(() => ({
    price: cachedNormalized?.banner_1h_price ?? [],
    volume: cachedNormalized?.banner_1h_volume ?? [],
  }));
  const [latestBySymbol, setLatestBySymbol] = useState(() => cachedNormalized?.latest_by_symbol ?? {});

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => !cachedNormalized);
  const [lastFetchTs, setLastFetchTs] = useState(null);
  const [heartbeatPulse, setHeartbeatPulse] = useState(false);
  const [warming, setWarming] = useState(() => !cachedNormalized);
  const [warming3m, setWarming3m] = useState(false);
  const [staleSeconds, setStaleSeconds] = useState(null);
  const [lastGoodTs, setLastGoodTs] = useState(null);

  // Timing refs for gated publishing
  const last3mPublishRef = useRef(0);
  const lastBannerPublishRef = useRef(0);
  const latestNormalizedRef = useRef(cachedNormalized);
  const abortRef = useRef(null);
  const fastAbortRef = useRef(null);
  const fastInFlightRef = useRef(false);
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

      // Extract meta fields from backend
      const meta = norm.meta || {};
      const backendWarming = meta.warming ?? false;
       const backendWarming3m = meta.warming_3m ?? meta.warming3m ?? false;
      const backendStaleSeconds = meta.staleSeconds ?? null;
      const backendLastGoodTs = meta.lastGoodTs ?? null;

      const hasAny =
        (Array.isArray(norm.gainers_1m) && norm.gainers_1m.length) ||
        (Array.isArray(norm.gainers_3m) && norm.gainers_3m.length) ||
        (Array.isArray(norm.losers_3m) && norm.losers_3m.length) ||
        (Array.isArray(norm.banner_1h_price) && norm.banner_1h_price.length) ||
        (Array.isArray(norm.banner_1h_volume) && norm.banner_1h_volume.length);

      const cached = latestNormalizedRef.current;
      const cacheHasAny =
        cached &&
        ((Array.isArray(cached.gainers_1m) && cached.gainers_1m.length) ||
          (Array.isArray(cached.gainers_3m) && cached.gainers_3m.length) ||
          (Array.isArray(cached.losers_3m) && cached.losers_3m.length) ||
          (Array.isArray(cached.banner_1h_price) && cached.banner_1h_price.length) ||
          (Array.isArray(cached.banner_1h_volume) && cached.banner_1h_volume.length));

      setError(null);
      setLoading(false);

      // Use backend meta.warming as source of truth
      setWarming(backendWarming);
      setWarming3m(Boolean(backendWarming3m));
      setStaleSeconds(backendStaleSeconds);
      setLastGoodTs(backendLastGoodTs);

      if (!hasAny && cacheHasAny) {
        // Keep warming state from backend
      } else {
        latestNormalizedRef.current = norm;
        setLatestBySymbol(norm.latest_by_symbol || {});

        // 1m: every fetch, but stagger the row commits for "live feel"
        staggerCommit1m(norm.gainers_1m);

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
      }

      setLastFetchTs(now);
      setHeartbeatPulse(true);
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
      }
      heartbeatTimerRef.current = setTimeout(() => {
        setHeartbeatPulse(false);
      }, 420);
    } catch (e) {
      if (e.name === 'AbortError') return;
      console.warn('[DataContext] Fetch failed:', e.message);
      setError(e);
      setLoading(false);
      // On error, don't override warming state - keep backend's last state
    }
  }, [staggerCommit1m]);

  const applyFast1m = useCallback((norm, now) => {
    const has1m = Array.isArray(norm?.gainers_1m) && norm.gainers_1m.length > 0;
    if (!has1m) {
      return;
    }

    // Extract meta fields from backend
    const meta = norm.meta || {};
    const backendWarming = meta.warming ?? false;
    const backendWarming3m = meta.warming_3m ?? meta.warming3m ?? false;
    const backendStaleSeconds = meta.staleSeconds ?? null;
    const backendLastGoodTs = meta.lastGoodTs ?? null;

    latestNormalizedRef.current = norm;
    setLatestBySymbol(norm.latest_by_symbol || {});
    setWarming(backendWarming);
    setWarming3m(Boolean(backendWarming3m));
    setStaleSeconds(backendStaleSeconds);
    setLastGoodTs(backendLastGoodTs);
    staggerCommit1m(norm.gainers_1m);

    setLastFetchTs(now);
    setHeartbeatPulse(true);
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = setTimeout(() => {
      setHeartbeatPulse(false);
    }, 420);
  }, [staggerCommit1m]);

  const fetchFast1m = useCallback(async () => {
    if (!FAST_1M_MS || FAST_1M_MS <= 0) return;
    if (fastInFlightRef.current) return;
    fastInFlightRef.current = true;
    try {
      const json = await fetchAllData();
      const norm = normalizeApiData(json);
      applyFast1m(norm, Date.now());
    } catch {
      // fast loop is best-effort; do not surface errors
    } finally {
      fastInFlightRef.current = false;
    }
  }, [applyFast1m]);

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

  useEffect(() => {
    if (!FAST_1M_MS || FAST_1M_MS <= 0) return undefined;
    fetchFast1m();
    const id = setInterval(fetchFast1m, FAST_1M_MS);
    return () => {
      clearInterval(id);
      if (fastAbortRef.current) fastAbortRef.current.abort();
      fastInFlightRef.current = false;
    };
  }, [fetchFast1m]);

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
    warming,
    warming3m,
    staleSeconds,
    lastGoodTs,
  }), [combinedData, oneMinRows, threeMin, banners, latestBySymbol, error, loading, fetchData, heartbeatPulse, lastFetchTs, warming, warming3m, staleSeconds, lastGoodTs]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
