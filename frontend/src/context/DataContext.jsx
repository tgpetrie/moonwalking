import { createContext, useCallback, useEffect, useMemo, useRef, useState, useContext } from "react";
import { fetchAllData } from "../api";

const DataContext = createContext(null);
export const useData = () => useContext(DataContext);

const LS_KEY = "bh_last_payload_v1";
const FAST_1M_MS = Number(import.meta.env.VITE_FAST_1M_MS || 2400);
const BACKOFF_1M_MS = Number(import.meta.env.VITE_BACKOFF_1M_MS || 9000);
const BACKOFF_WINDOW_MS = 30_000;

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
const PUBLISH_3M_MS = Number(import.meta.env.VITE_PUBLISH_3M_MS || 12000);
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
  const volume1h = p.volume1h ?? p.data?.volume1h ?? [];

  const latest_by_symbol = p.latest_by_symbol ?? p.data?.latest_by_symbol ?? {};
  const updated_at       = p.updated_at       ?? p.data?.updated_at       ?? Date.now();

  return {
    gainers_1m,
    gainers_3m,
    losers_3m,
    banner_1h_price,
    banner_1h_volume,
    volume1h,
    latest_by_symbol,
    updated_at,
    meta: p.meta ?? p.data?.meta ?? {},
    errors: p.errors ?? p.data?.errors ?? [],
    coverage: p.coverage ?? p.data?.coverage ?? null,
  };
}

const parseStatus = (err) => {
  if (!err) return null;
  if (typeof err.status === "number") return err.status;
  const match = String(err.message || "").match(/(\d{3})/);
  if (match && match[1]) {
    const num = Number(match[1]);
    return Number.isFinite(num) ? num : null;
  }
  return null;
};

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
  const [volume1h, setVolume1h] = useState(() => cachedNormalized?.volume1h ?? []);

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
  const pollTimerRef = useRef(null);
  const backoffUntilRef = useRef(0);
  const inFlightRef = useRef(false);
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

  const applySnapshot = useCallback((norm, now = Date.now()) => {
    // DEV-only one-time payload shape log for diagnostics
    if (
      import.meta?.env?.DEV &&
      typeof window !== "undefined" &&
      !window.__MW_DEBUG_LOGGED__ &&
      ((Array.isArray(norm.gainers_1m) && norm.gainers_1m.length) ||
        (Array.isArray(norm.banner_1h_price) && norm.banner_1h_price.length) ||
        (Array.isArray(norm.banner_1h_volume) && norm.banner_1h_volume.length))
    ) {
      window.__MW_DEBUG_LOGGED__ = true;
      console.log("[mw] 1m shape sample:", norm.gainers_1m?.slice(0, 2));
      console.log("[mw] 1h price banner shape:", norm.banner_1h_price?.slice(0, 2));
      console.log("[mw] 1h volume banner shape:", norm.banner_1h_volume?.slice(0, 2));
    }

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
      setVolume1h(norm.volume1h || []);

      // 1m: every fetch, but stagger the row commits for "live feel"
      staggerCommit1m(norm.gainers_1m);

      // 3m: publish every PUBLISH_3M_MS (default 12s)
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
  }, [staggerCommit1m]);

  const fetchData = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;

    if (abortRef.current) {
      try { abortRef.current.abort(); } catch {}
    }
    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutMs = 6500;
    const timeoutId = setTimeout(() => {
      try {
        controller.abort("timeout");
      } catch {}
    }, timeoutMs);

    try {
      const json = await fetchAllData({ signal: controller.signal });
      const norm = normalizeApiData(json);
      applySnapshot(norm, Date.now());
      backoffUntilRef.current = 0;
    } catch (e) {
      if (e.name === 'AbortError') {
        const timedOut = controller?.signal?.reason === "timeout";
        if (timedOut) {
          console.warn("[DataContext] Fetch timed out after", timeoutMs, "ms");
          backoffUntilRef.current = Date.now() + BACKOFF_WINDOW_MS;
        }
        return;
      }
      console.warn('[DataContext] Fetch failed:', e.message);
      setError(e);
      setLoading(false);
      const status = parseStatus(e);
      if (status === 429 || (status >= 500 && status < 600) || status === null) {
        backoffUntilRef.current = Date.now() + BACKOFF_WINDOW_MS;
      }
      // On error, don't override warming state - keep backend's last state
    } finally {
      clearTimeout(timeoutId);
      inFlightRef.current = false;
    }
  }, [applySnapshot]);

  useEffect(() => {
    if (!FAST_1M_MS || FAST_1M_MS <= 0) return undefined;
    let cancelled = false;

    const scheduleNext = (delayMs) => {
      if (cancelled) return;
      pollTimerRef.current = setTimeout(run, delayMs);
    };

    const run = async () => {
      if (cancelled) return;
      await fetchData();
      if (cancelled) return;
      const now = Date.now();
      const delay = now < backoffUntilRef.current ? BACKOFF_1M_MS : FAST_1M_MS;
      scheduleNext(delay);
    };

    run();

    return () => {
      cancelled = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
      if (abortRef.current) abortRef.current.abort();
      inFlightRef.current = false;
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
    volume1h,
    updated_at: latestNormalizedRef.current?.updated_at ?? Date.now(),
  }), [oneMinRows, threeMin, banners, latestBySymbol, volume1h]);

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
    volume1h,
  }), [combinedData, oneMinRows, threeMin, banners, latestBySymbol, error, loading, fetchData, heartbeatPulse, lastFetchTs, warming, warming3m, staleSeconds, lastGoodTs, volume1h]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
