import { createContext, useCallback, useEffect, useMemo, useRef, useState, useContext } from "react";

const DataContext = createContext(null);
export const useData = () => useContext(DataContext);

const LS_KEY = "bh_last_payload_v1";
const FAST_1M_MS = Number(import.meta.env.VITE_FAST_1M_MS || 3800);
const BACKOFF_1M_MS = Number(import.meta.env.VITE_BACKOFF_1M_MS || 9000);
const BACKOFF_WINDOW_MS = 30_000;
const POLL_JITTER_MS = Number(import.meta.env.VITE_POLL_JITTER_MS || 320);
const PUBLISH_UI_MS = Number(import.meta.env.VITE_PUBLISH_UI_MS || 4000);
const MW_BACKEND_KEY = "mw_backend_base";
const MW_LAST_GOOD_DATA = "mw_last_good_data";
const MW_LAST_GOOD_AT = "mw_last_good_at";

const readCachedPayload = () => {
  if (typeof window === "undefined") return null;
  // Prefer new last-good cache; fall back to legacy key
  try {
    const raw = window.localStorage.getItem(MW_LAST_GOOD_DATA) || window.localStorage.getItem(LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

const readCachedTimestamp = () => {
  if (typeof window === "undefined") return null;
  try {
    const t = window.localStorage.getItem(MW_LAST_GOOD_AT);
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
};

// Environment-driven cadence knobs (defaults optimized for N100)
const PUBLISH_3M_MS = Number(import.meta.env.VITE_PUBLISH_3M_MS || 12000);
const PUBLISH_BANNER_MS = Number(import.meta.env.VITE_PUBLISH_BANNER_MS || 120000);
// NOTE: row-level staggering moved into the 1m table layer; keep env var reserved for future use.
const STAGGER_MS = Number(import.meta.env.VITE_ROW_STAGGER_MS || 65);

// Normalize backend response to canonical shape
function normalizeApiData(payload) {
  const root = payload?.data && typeof payload.data === "object" ? payload.data : payload || {};
  const gainers_1m = root.gainers_1m ?? root.gainers1m ?? [];
  const gainers_3m = root.gainers_3m ?? root.gainers3m ?? [];
  const losers_3m  = root.losers_3m  ?? root.losers3m  ?? [];

  const banner_1h_price  = root.banner_1h_price  ?? root.banner_1h ?? root.top_banner_1h ?? [];
  const banner_1h_volume = root.banner_1h_volume ?? root.volume_banner_1h ?? [];
  const volume1h = root.volume1h ?? [];
  const alerts = root.alerts ?? [];

  const latest_by_symbol = root.latest_by_symbol ?? {};
  const updated_at       = root.updated_at ?? payload?.updated_at ?? Date.now();

  return {
    gainers_1m: Array.isArray(gainers_1m) ? gainers_1m : [],
    gainers_3m: Array.isArray(gainers_3m) ? gainers_3m : [],
    losers_3m: Array.isArray(losers_3m) ? losers_3m : [],
    banner_1h_price: Array.isArray(banner_1h_price) ? banner_1h_price : [],
    banner_1h_volume: Array.isArray(banner_1h_volume) ? banner_1h_volume : [],
    volume1h: Array.isArray(volume1h) ? volume1h : [],
    alerts: Array.isArray(alerts) ? alerts : [],
    latest_by_symbol: typeof latest_by_symbol === "object" && latest_by_symbol ? latest_by_symbol : {},
    updated_at,
    meta: root.meta ?? payload?.meta ?? {},
    errors: root.errors ?? payload?.errors ?? [],
    coverage: root.coverage ?? payload?.coverage ?? null,
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
  const cachedLastGoodAt = useMemo(() => readCachedTimestamp(), []);

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
  const [alerts, setAlerts] = useState(() => cachedNormalized?.alerts ?? []);

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => !cachedNormalized);
  const [lastFetchTs, setLastFetchTs] = useState(null);
  const [heartbeatPulse, setHeartbeatPulse] = useState(false);
  const [warming, setWarming] = useState(() => !cachedNormalized);
  const [warming3m, setWarming3m] = useState(false);
  const [staleSeconds, setStaleSeconds] = useState(null);
  const [lastGoodTs, setLastGoodTs] = useState(cachedLastGoodAt || null);
  const [backendBase, setBackendBase] = useState(() => {
    if (typeof window === "undefined") return null;
    try {
      return (
        window.localStorage.getItem(MW_BACKEND_KEY) ||
        null
      );
    } catch {
      return null;
    }
  });
  const [connectionStatus, setConnectionStatus] = useState(() => (cachedNormalized ? "STALE" : "LIVE")); // LIVE | STALE | DOWN
  const lastGoodRef = useRef(cachedNormalized);
  const lastGoodAtRef = useRef(cachedLastGoodAt || (cachedNormalized ? Date.now() : null));

  // Timing refs for gated publishing
  const last3mPublishRef = useRef(0);
  const lastBannerPublishRef = useRef(0);
  const latestNormalizedRef = useRef(cachedNormalized);
  const pendingNormalizedRef = useRef(null);
  const pendingBaseRef = useRef(null);
  const abortRef = useRef(null);
  const pollTimerRef = useRef(null);
  const backoffUntilRef = useRef(0);
  const inFlightRef = useRef(false);
  const staggerTokenRef = useRef(null);
  const heartbeatTimerRef = useRef(null);
  const failCountRef = useRef(0);

  // Commit 1m rows as a whole snapshot.
  // Row liveliness is handled in the table layer (value-only pulses + staggering),
  // and avoiding index-based partial commits prevents "jerky" mismatched row updates.
  const commit1m = useCallback((nextRows) => {
    staggerTokenRef.current = null;
    setOneMinRows(Array.isArray(nextRows) ? nextRows : []);
  }, []);

  const persistLastGood = useCallback((norm, baseUrl) => {
    lastGoodRef.current = norm;
    lastGoodAtRef.current = Date.now();
    setLastGoodTs(lastGoodAtRef.current);
    try {
      const minimal = {
        gainers_1m: norm.gainers_1m,
        gainers_3m: norm.gainers_3m,
        losers_3m: norm.losers_3m,
        banner_1h_price: norm.banner_1h_price,
        banner_1h_volume: norm.banner_1h_volume,
        latest_by_symbol: norm.latest_by_symbol,
        volume1h: norm.volume1h,
        alerts: norm.alerts,
        updated_at: norm.updated_at,
        meta: norm.meta,
        coverage: norm.coverage,
      };
      localStorage.setItem(MW_LAST_GOOD_DATA, JSON.stringify(minimal));
      localStorage.setItem(MW_LAST_GOOD_AT, String(lastGoodAtRef.current));
      if (baseUrl) localStorage.setItem(MW_BACKEND_KEY, baseUrl);
    } catch {}
  }, []);

  const applySnapshot = useCallback((norm, now = Date.now(), baseUrl = null) => {
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
    setLastGoodTs(backendLastGoodTs ?? lastGoodAtRef.current ?? null);

    if (!hasAny && cacheHasAny) {
      // Keep warming state from backend
    } else {
      latestNormalizedRef.current = norm;
      persistLastGood(norm, baseUrl);
      setLatestBySymbol(norm.latest_by_symbol || {});
      setVolume1h(norm.volume1h || []);
      setAlerts(Array.isArray(norm.alerts) ? norm.alerts : []);

      // 1m: every fetch (table layer handles "live feel" without partial commits)
      commit1m(norm.gainers_1m);

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
  }, [commit1m, persistLastGood]);

  const fetchData = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;

    const candidates = [];
    if (backendBase) candidates.push(backendBase);
    try {
      const cachedBase = typeof window !== "undefined" ? window.localStorage.getItem(MW_BACKEND_KEY) : null;
      if (cachedBase && !candidates.includes(cachedBase)) candidates.push(cachedBase);
    } catch {}
    ["http://127.0.0.1:5003"].forEach((b) => {
      if (!candidates.includes(b)) candidates.push(b);
    });

    const tryOnce = async (base) => {
      if (abortRef.current) {
        try { abortRef.current.abort(); } catch {}
      }
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutMs = 4000;
      const timeoutId = setTimeout(() => {
        try { controller.abort("timeout"); } catch {}
      }, timeoutMs);
      try {
        const url = `${base.replace(/\\/$/, "")}/data`;
        const res = await fetch(url, { signal: controller.signal, headers: { Accept: "application/json" }, cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        clearTimeout(timeoutId);
        return { json, base };
      } catch (err) {
        clearTimeout(timeoutId);
        throw err;
      }
    };

    let succeeded = false;
    let lastError = null;
    for (const base of candidates) {
      try {
        const { json, base: okBase } = await tryOnce(base);
        const norm = normalizeApiData(json);
        setBackendBase(okBase);
        setConnectionStatus("LIVE");
        failCountRef.current = 0;
        // Fetch fast: store latest payload in a ref; publish on a steady cadence.
        pendingNormalizedRef.current = norm;
        pendingBaseRef.current = okBase;
        backoffUntilRef.current = 0;
        succeeded = true;
        break;
      } catch (err) {
        lastError = err;
        failCountRef.current += 1;
        continue;
      }
    }

    if (!succeeded) {
      setLoading(false);
      setError(lastError || new Error("fetch failed"));
      if (lastGoodRef.current) {
        setConnectionStatus("STALE");
      } else {
        setConnectionStatus("DOWN");
      }
      const status = parseStatus(new Error("fetch failed"));
      if (status === 429 || (status && status >= 500)) {
        backoffUntilRef.current = Date.now() + BACKOFF_WINDOW_MS;
      }
    }

    inFlightRef.current = false;
  }, [applySnapshot, backendBase]);

  // Publish pending snapshots on a steady cadence to avoid spamming React state.
  useEffect(() => {
    if (!PUBLISH_UI_MS || PUBLISH_UI_MS <= 0) return undefined;
    const id = setInterval(() => {
      const pending = pendingNormalizedRef.current;
      if (!pending) return;
      pendingNormalizedRef.current = null;
      const baseUrl = pendingBaseRef.current;
      applySnapshot(pending, Date.now(), baseUrl);
    }, PUBLISH_UI_MS);
    return () => clearInterval(id);
  }, [applySnapshot]);

  useEffect(() => {
    if (!FAST_1M_MS || FAST_1M_MS <= 0) return undefined;
    let cancelled = false;

    const scheduleNext = (delayMs) => {
      if (cancelled) return;
      const jitter =
        POLL_JITTER_MS > 0
          ? Math.max(-POLL_JITTER_MS, Math.min(POLL_JITTER_MS, (Math.random() * 2 - 1) * POLL_JITTER_MS))
          : 0;
      const ms = Math.max(1200, delayMs + jitter);
      pollTimerRef.current = setTimeout(run, ms);
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
    alerts,
    updated_at: latestNormalizedRef.current?.updated_at ?? lastGoodAtRef.current ?? Date.now(),
  }), [oneMinRows, threeMin, banners, latestBySymbol, volume1h, alerts]);

  const alertsBySymbol = useMemo(() => {
    const map = {};
    (alerts || []).forEach((a) => {
      if (!a) return;
      const sym = (a.symbol || "").toString().toUpperCase();
      if (!sym) return;
      map[sym] = map[sym] || [];
      map[sym].push(a);
    });
    return map;
  }, [alerts]);

  const getActiveAlert = useCallback(
    (sym) => {
      if (!sym) return null;
      const key = sym.toString().toUpperCase();
      const list = alertsBySymbol[key];
      if (!list || !list.length) return null;
      const severityRank = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
      const now = Date.now();
      const active = list
        .filter((a) => {
          if (!a) return false;
          if (a.expires_at) {
            const exp = Date.parse(a.expires_at);
            if (Number.isFinite(exp) && exp < now) return false;
          }
          return true;
        })
        .sort((a, b) => {
          const sa = severityRank[(a.severity || "").toLowerCase()] || 0;
          const sb = severityRank[(b.severity || "").toLowerCase()] || 0;
          if (sa !== sb) return sb - sa;
          const ta = Date.parse(a.ts || "") || 0;
          const tb = Date.parse(b.ts || "") || 0;
          return tb - ta;
        });
      return active[0] || null;
    },
    [alertsBySymbol]
  );

  const value = useMemo(() => ({
    data: combinedData,
    oneMinRows,
    threeMin,
    banners,
    latestBySymbol,
    alerts,
    alertsBySymbol,
    getActiveAlert,
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
    connectionStatus,
    backendBase,
    lastGood: lastGoodRef.current,
    lastGoodLatestBySymbol: lastGoodRef.current?.latest_by_symbol || {},
    backendFailCount: failCountRef.current,
  }), [combinedData, oneMinRows, threeMin, banners, latestBySymbol, alerts, alertsBySymbol, getActiveAlert, error, loading, fetchData, heartbeatPulse, lastFetchTs, warming, warming3m, staleSeconds, lastGoodTs, volume1h, connectionStatus, backendBase]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
