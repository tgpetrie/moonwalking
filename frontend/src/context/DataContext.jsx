import { createContext, useCallback, useEffect, useMemo, useRef, useState, useContext } from "react";

const DataContext = createContext(null);
export const useData = () => useContext(DataContext);

const LS_KEY = "bh_last_payload_v1";
const FAST_1M_MS = Number(import.meta.env.VITE_FAST_1M_MS || 3800);
const BACKOFF_1M_MS = Number(import.meta.env.VITE_BACKOFF_1M_MS || 9000);
const BACKOFF_WINDOW_MS = 30_000;
const POLL_JITTER_MS = Number(import.meta.env.VITE_POLL_JITTER_MS || 320);
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

const SEV_RANK = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
const MIN_ROWS_3M = 4;
const MIN_BANNER_ITEMS = 2;

const asArray = (value) => (Array.isArray(value) ? value : []);
const pickStableSlice = (next, prev, min = 1) => {
  const nextArr = asArray(next);
  const prevArr = asArray(prev);
  const usePrev = nextArr.length < min && prevArr.length > 0;
  return {
    value: usePrev ? prevArr : nextArr,
    sticky: usePrev,
    nextLength: nextArr.length,
    prevLength: prevArr.length,
  };
};

const normAlert = (a) => {
  const sev = String(a?.severity || "info").toLowerCase();
  const typ = String(a?.alert_type || a?.type || "info").toLowerCase();
  const tsRaw = a?.ts;
  const tsIso = tsRaw ? String(tsRaw) : null;
  let tsMs = null;
  if (typeof tsRaw === "number") {
    tsMs = tsRaw > 1e12 ? tsRaw : tsRaw * 1000;
  } else if (tsIso) {
    const parsed = Date.parse(tsIso);
    tsMs = Number.isFinite(parsed) ? parsed : null;
  }

  return {
    id: a?.id || `${a?.symbol || "UNK"}-${tsIso || Date.now()}`,
    symbol: String(a?.symbol || "").toUpperCase(),
    alert_type: typ.toUpperCase(),
    severity: sev.toUpperCase(),
    severity_lc: sev,
    title: String(a?.title || a?.message || "Alert"),
    message: String(a?.message || ""),
    score: Number.isFinite(a?.score) ? Number(a.score) : null,
    sources: Array.isArray(a?.sources) ? a.sources : [],
    trade_url: a?.trade_url ? String(a.trade_url) : null,
    ts_iso: tsIso,
    ts_ms: Number.isFinite(tsMs) ? tsMs : null,
    rank: SEV_RANK[sev] || 0,
    raw: a,
  };
};

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
  const rawAlerts = Array.isArray(alerts) ? alerts : [];
  const alerts_norm = rawAlerts
    .map(normAlert)
    .sort((x, y) => (y.ts_ms || 0) - (x.ts_ms || 0));

  const latest_by_symbol = root.latest_by_symbol ?? {};
  const updated_at       = root.updated_at ?? payload?.updated_at ?? Date.now();

  return {
    gainers_1m: Array.isArray(gainers_1m) ? gainers_1m : [],
    gainers_3m: Array.isArray(gainers_3m) ? gainers_3m : [],
    losers_3m: Array.isArray(losers_3m) ? losers_3m : [],
    banner_1h_price: Array.isArray(banner_1h_price) ? banner_1h_price : [],
    banner_1h_volume: Array.isArray(banner_1h_volume) ? banner_1h_volume : [],
    volume1h: Array.isArray(volume1h) ? volume1h : [],
    alerts: alerts_norm,
    alerts_norm,
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
  const [alerts, setAlerts] = useState(() => cachedNormalized?.alerts_norm ?? cachedNormalized?.alerts ?? []);
  const [alertsUnread, setAlertsUnread] = useState(0);

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => !cachedNormalized);
  const [lastFetchTs, setLastFetchTs] = useState(null);
  const [heartbeatPulse, setHeartbeatPulse] = useState(false);
  const [warming, setWarming] = useState(() => !cachedNormalized);
  const [warming3m, setWarming3m] = useState(false);
  const [staleSeconds, setStaleSeconds] = useState(null);
  const [lastGoodTs, setLastGoodTs] = useState(cachedLastGoodAt || null);
  const [backendBase, setBackendBase] = useState("/data"); // Always use proxy path
  const [connectionStatus, setConnectionStatus] = useState(() => (cachedNormalized ? "STALE" : "LIVE")); // LIVE | STALE | DOWN
  const lastGoodRef = useRef(cachedNormalized);
  const lastGoodAtRef = useRef(cachedLastGoodAt || (cachedNormalized ? Date.now() : null));

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
  const failCountRef = useRef(0);

  // Commit 1m rows as a whole snapshot.
  // Row liveliness is handled in the table layer (value-only pulses + staggering),
  // and avoiding index-based partial commits prevents "jerky" mismatched row updates.
  const commit1m = useCallback((nextRows) => {
    staggerTokenRef.current = null;
    setOneMinRows(Array.isArray(nextRows) ? nextRows : []);
  }, []);

  const persistLastGood = useCallback((norm) => {
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
      // No longer cache backend URL - always use proxy path
    } catch {}
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

    const prevGood = lastGoodRef.current || {};

    const nextG1 = pickStableSlice(norm.gainers_1m, prevGood.gainers_1m, 1);
    const nextG3 = pickStableSlice(norm.gainers_3m, prevGood.gainers_3m, MIN_ROWS_3M);
    const nextL3 = pickStableSlice(norm.losers_3m, prevGood.losers_3m, MIN_ROWS_3M);
    const nextBannerPrice = pickStableSlice(norm.banner_1h_price, prevGood.banner_1h_price, MIN_BANNER_ITEMS);
    const nextBannerVol = pickStableSlice(norm.banner_1h_volume, prevGood.banner_1h_volume, MIN_BANNER_ITEMS);
    const nextVolume1h = pickStableSlice(norm.volume1h, prevGood.volume1h, 1);
    const nextAlertsBase = pickStableSlice(
      Array.isArray(norm.alerts_norm) ? norm.alerts_norm : Array.isArray(norm.alerts) ? norm.alerts : [],
      prevGood.alerts_norm || prevGood.alerts,
      1
    );
    const nextLatestBySymbol =
      (norm.latest_by_symbol && typeof norm.latest_by_symbol === "object" && norm.latest_by_symbol) ||
      prevGood.latest_by_symbol ||
      {};

    const sticky3m = nextG3.sticky || nextL3.sticky;
    const stickyBanner = nextBannerPrice.sticky || nextBannerVol.sticky;
    const sticky1m = nextG1.sticky;

    setError(null);
    setLoading(false);
    setWarming(Boolean(backendWarming || sticky1m || stickyBanner));
    setWarming3m(Boolean(backendWarming3m || sticky3m));
    setStaleSeconds(backendStaleSeconds);

    const stableSnapshot = {
      ...norm,
      gainers_1m: nextG1.value,
      gainers_3m: nextG3.value,
      losers_3m: nextL3.value,
      banner_1h_price: nextBannerPrice.value,
      banner_1h_volume: nextBannerVol.value,
      volume1h: nextVolume1h.value,
      alerts: nextAlertsBase.value,
      alerts_norm: nextAlertsBase.value,
      latest_by_symbol: nextLatestBySymbol,
    };

    latestNormalizedRef.current = stableSnapshot;
    persistLastGood(stableSnapshot);
    setLastGoodTs(backendLastGoodTs ?? lastGoodAtRef.current ?? null);

    setLatestBySymbol(nextLatestBySymbol || {});

    const prevMap = new Map();
    (alerts || []).forEach((a) => {
      if (!a || !a.id) return;
      prevMap.set(a.id, Boolean(a.read));
    });
    setVolume1h(nextVolume1h.value);
    const normalizedAlerts = nextAlertsBase.value.map((a) => ({
      ...a,
      read: prevMap.has(a.id) ? prevMap.get(a.id) : false,
    }));
    const unreadCount = normalizedAlerts.reduce((n, a) => n + (a.read ? 0 : 1), 0);
    setAlerts(normalizedAlerts);
    setAlertsUnread(unreadCount);
    if (import.meta?.env?.DEV) {
      const sample = normalizedAlerts[0];
      console.log(
        "[mw] alerts_norm sample:",
        sample
          ? {
              id: sample.id,
              symbol: sample.symbol,
              alert_type: sample.alert_type,
              severity_lc: sample.severity_lc,
              score: sample.score,
            }
          : "EMPTY"
      );
    }

    // 1m: every fetch (table layer handles "live feel" without partial commits)
    commit1m(nextG1.value);
    if (import.meta?.env?.VITE_MW_DEBUG && Array.isArray(nextG1.value) && nextG1.value.length) {
      const sample = nextG1.value.slice(0, 3).map((row) => {
        const sym = row?.symbol || row?.product_id || row?.ticker || "UNK";
        const priceNow = Number(row?.current_price ?? row?.price ?? row?.current ?? row?.last ?? null);
        const baseline =
          row?.previous_price_1m ??
          row?.initial_price_1min ??
          row?.price_1m_ago ??
          row?.baseline_price ??
          null;
        const pct =
          row?.change_1m ??
          row?.price_change_percentage_1min ??
          row?.pct_change ??
          row?.pct ??
          row?.changePct ??
          null;
        const baselineAge = row?.baseline_age_s ?? null;
        return {
          symbol: sym,
          price_now: Number.isFinite(priceNow) ? priceNow : null,
          baseline_1m: baseline ?? null,
          baseline_age_s: baselineAge,
          pct_1m: Number.isFinite(Number(pct)) ? Number(pct) : null,
        };
      });
      console.info("[mw] g1 debug", sample);
    }

    // 3m: publish every PUBLISH_3M_MS (default 12s)
    if (now - last3mPublishRef.current >= PUBLISH_3M_MS) {
      last3mPublishRef.current = now;
      setThreeMin({ gainers: nextG3.value, losers: nextL3.value });
    }

    // banners: publish every PUBLISH_BANNER_MS (default 2 minutes)
    if (now - lastBannerPublishRef.current >= PUBLISH_BANNER_MS) {
      lastBannerPublishRef.current = now;
      setBanners({ price: nextBannerPrice.value, volume: nextBannerVol.value });
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

    // PROXY-FIRST ARCHITECTURE: Always use relative path
    // Vite dev proxy forwards /data → http://127.0.0.1:5003/data
    // Production nginx/reverse proxy handles the same way
    const url = "/data";

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
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
        cache: "no-store"
      });
      clearTimeout(timeoutId);

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const norm = normalizeApiData(json);
      if (import.meta?.env?.VITE_MW_DEBUG) {
        try {
          const lens = {
            g1: Array.isArray(norm.gainers_1m) ? norm.gainers_1m.length : 0,
            g3: Array.isArray(norm.gainers_3m) ? norm.gainers_3m.length : 0,
            l3: Array.isArray(norm.losers_3m) ? norm.losers_3m.length : 0,
            b1h: Array.isArray(norm.banner_1h_price) ? norm.banner_1h_price.length : 0,
            bv1h: Array.isArray(norm.banner_1h_volume) ? norm.banner_1h_volume.length : 0,
            v1h: Array.isArray(norm.volume1h) ? norm.volume1h.length : 0,
            alerts: Array.isArray(norm.alerts_norm || norm.alerts) ? (norm.alerts_norm || norm.alerts).length : 0,
          };
          console.info("[mw] fetch /data ok", { url, len: lens, meta: norm.meta });
        } catch (e) {
          console.warn("[mw] fetch /data debug log failed", e);
        }
      }

      setBackendBase(url); // Store relative path
      setConnectionStatus("LIVE");
      failCountRef.current = 0;
      applySnapshot(norm, Date.now());
      backoffUntilRef.current = 0;

    } catch (err) {
      clearTimeout(timeoutId);
      setLoading(false);
      setError(err);
      failCountRef.current += 1;

      if (lastGoodRef.current) {
        setConnectionStatus("STALE");
      } else {
        setConnectionStatus("DOWN");
      }

      const status = parseStatus(err);
      if (status === 429 || (status && status >= 500)) {
        backoffUntilRef.current = Date.now() + BACKOFF_WINDOW_MS;
      }
    } finally {
      inFlightRef.current = false;
    }
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
    alerts_norm: alerts,
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

  const toTsMs = useCallback((value) => {
    if (value == null) return 0;
    if (typeof value === "number") return value > 1e12 ? value : value * 1000;
    const parsed = Date.parse(String(value));
    return Number.isFinite(parsed) ? parsed : 0;
  }, []);

  const getActiveAlert = useCallback(
    (sym) => {
      if (!sym) return null;
      const key = sym.toString().toUpperCase();
      const list = alertsBySymbol[key];
      if (!list || !list.length) return null;
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
          const sa = SEV_RANK[String(a.severity_lc || a.severity || "info").toLowerCase()] || 0;
          const sb = SEV_RANK[String(b.severity_lc || b.severity || "info").toLowerCase()] || 0;
          if (sa !== sb) return sb - sa;
          const ta = toTsMs(a.ts_ms ?? a.ts_iso ?? a.ts);
          const tb = toTsMs(b.ts_ms ?? b.ts_iso ?? b.ts);
          return tb - ta;
        });
      return active[0] || null;
    },
    [alertsBySymbol, toTsMs]
  );

  const markAllRead = useCallback(() => {
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
    setAlertsUnread(0);
  }, []);

  const clearAllAlerts = useCallback(() => {
    setAlerts([]);
    setAlertsUnread(0);
  }, []);

  const value = useMemo(() => ({
    data: combinedData,
    oneMinRows,
    threeMin,
    banners,
    latestBySymbol,
    alerts,
    alertsUnread,
    alerts_norm: alerts,
    alertsBySymbol,
    getActiveAlert,
    markAllRead,
    clearAllAlerts,
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
  }), [combinedData, oneMinRows, threeMin, banners, latestBySymbol, alerts, alertsUnread, alertsBySymbol, getActiveAlert, markAllRead, clearAllAlerts, error, loading, fetchData, heartbeatPulse, lastFetchTs, warming, warming3m, staleSeconds, lastGoodTs, volume1h, connectionStatus, backendBase]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
