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
const MW_DEBUG = import.meta.env.VITE_MW_DEBUG === "1";

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

// Prevent UI "dropouts" when a later poll briefly returns an empty slice.
// Keep the last non-empty slice for a short grace window.
const KEEP_NONEMPTY_1M_MS = Number(import.meta.env.VITE_KEEP_NONEMPTY_1M_MS || 60_000);
const KEEP_NONEMPTY_3M_MS = Number(import.meta.env.VITE_KEEP_NONEMPTY_3M_MS || 120_000);
const KEEP_NONEMPTY_BANNER_MS = Number(import.meta.env.VITE_KEEP_NONEMPTY_BANNER_MS || 180_000);

// Normalize backend response to canonical shape
function normalizeApiData(payload) {
  const root = payload?.data && typeof payload.data === "object" ? payload.data : payload || {};
  const gainers_1m = root.gainers_1m ?? root.gainers1m ?? [];
  const gainers_3m = root.gainers_3m ?? root.gainers3m ?? [];
  const losers_3m  = root.losers_3m  ?? root.losers3m  ?? [];

  const banner_1h_price  = root.banner_1h_price  ?? root.banner_1h ?? root.top_banner_1h ?? [];
  const banner_1h_volume = root.banner_1h_volume ?? root.volume_banner_1h ?? [];
  const volume1h = root.volume1h ?? [];
  const alertsRaw = root.alerts ?? [];

  const latest_by_symbol = root.latest_by_symbol ?? {};
  const updated_at       = root.updated_at ?? payload?.updated_at ?? Date.now();
  const sentiment = payload?.sentiment ?? root.sentiment ?? null;
  const sentimentMeta = payload?.sentiment_meta ?? payload?.sentimentMeta ?? root.sentiment_meta ?? root.sentimentMeta ?? null;

  const toMs = (v) => {
    if (v == null) return null;
    if (typeof v === "number") return Number.isFinite(v) ? v : null;
    const n = Number(v);
    if (Number.isFinite(n) && n > 0) return n;
    const t = Date.parse(String(v));
    return Number.isFinite(t) ? t : null;
  };

  const normalizeAlert = (a) => {
    if (!a || typeof a !== "object") return null;
    const symRaw = a.product_id ?? a.symbol ?? a.pair ?? a.ticker ?? "";
    const rawUpper = String(symRaw || "").trim().toUpperCase();
    const product_id = rawUpper;
    const symbol = rawUpper.replace(/-USD$|-USDT$|-PERP$/i, "");

    const emitted_ts = a.ts ?? a.emitted_ts ?? a.emittedTs ?? a.ts_iso ?? a.tsIso ?? null;
    const emitted_ts_ms = toMs(a.ts_ms ?? a.tsMs ?? a.emitted_ts_ms ?? a.emittedTsMs ?? emitted_ts);

    const event_ts =
      a.event_ts ??
      a.eventTs ??
      a.window_end_ts ??
      a.windowEndTs ??
      a.detected_ts ??
      a.detectedTs ??
      null;
    const event_ts_ms = toMs(a.event_ts_ms ?? a.eventTsMs ?? a.event_ms ?? a.eventMs ?? event_ts);
    return {
      ...a,
      symbol,
      product_id,
      ts: emitted_ts || a.ts || null,
      ts_ms: emitted_ts_ms,
      emitted_ts: emitted_ts || null,
      emitted_ts_ms,
      event_ts: event_ts || null,
      event_ts_ms,
    };
  };

  const isPingNoise = (a) => {
    if (!a) return true;
    const type = String(a.type || a.kind || a.class_key || a.category || a.alert_type || "").toUpperCase();
    const msg = String(a.message || a.title || a.text || a.raw || "");
    if (type === "PING" || type === "HEARTBEAT") return true;
    if (/PING\s*>>/i.test(msg)) return true;
    if (/HEARTBEAT/i.test(msg)) return true;
    return false;
  };

  const alerts = Array.isArray(alertsRaw)
    ? alertsRaw.map(normalizeAlert).filter((a) => a && !isPingNoise(a))
    : [];

  return {
    gainers_1m: Array.isArray(gainers_1m) ? gainers_1m : [],
    gainers_3m: Array.isArray(gainers_3m) ? gainers_3m : [],
    losers_3m: Array.isArray(losers_3m) ? losers_3m : [],
    banner_1h_price: Array.isArray(banner_1h_price) ? banner_1h_price : [],
    banner_1h_volume: Array.isArray(banner_1h_volume) ? banner_1h_volume : [],
    volume1h: Array.isArray(volume1h) ? volume1h : [],
    alerts,
    latest_by_symbol: typeof latest_by_symbol === "object" && latest_by_symbol ? latest_by_symbol : {},
    updated_at,
    sentiment,
    sentimentMeta,
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
  // Use relative paths - Vite proxy handles routing to backend
  // Empty string means requests go to /data, /api/... which Vite proxies
  const CANONICAL_LOCAL_BASE = "";
  const normalizeBase = (base) => String(base || "").trim().replace(/\/+$/, "");
  const isCanonicalLocalBase = (base) => normalizeBase(base) === CANONICAL_LOCAL_BASE;

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
  const [sentiment, setSentiment] = useState(() => cachedNormalized?.sentiment ?? null);
  const [sentimentMeta, setSentimentMeta] = useState(() => cachedNormalized?.sentimentMeta ?? null);

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => !cachedNormalized);
  const [lastFetchTs, setLastFetchTs] = useState(null);
  const [heartbeatPulse, setHeartbeatPulse] = useState(false);
  const [warming, setWarming] = useState(() => !cachedNormalized);
  const [warming3m, setWarming3m] = useState(false);
  const [staleSeconds, setStaleSeconds] = useState(null);
  const [partial, setPartial] = useState(false);
  const [lastGoodTs, setLastGoodTs] = useState(cachedLastGoodAt || null);
  const [backendBase, setBackendBase] = useState(() => {
    if (typeof window === "undefined") return null;
    try {
      const cached = window.localStorage.getItem(MW_BACKEND_KEY);
      return cached && isCanonicalLocalBase(cached) ? normalizeBase(cached) : null;
    } catch {
      return null;
    }
  });
  const [connectionStatus, setConnectionStatus] = useState(() => (cachedNormalized ? "STALE" : "LIVE")); // LIVE | STALE | DOWN
  const lastGoodRef = useRef(cachedNormalized);
  const lastGoodAtRef = useRef(cachedLastGoodAt || (cachedNormalized ? Date.now() : null));

  const lastNonEmpty1mAtRef = useRef(
    cachedNormalized && Array.isArray(cachedNormalized.gainers_1m) && cachedNormalized.gainers_1m.length
      ? Date.now()
      : 0
  );
  const lastNonEmpty3mAtRef = useRef(
    cachedNormalized &&
      ((Array.isArray(cachedNormalized.gainers_3m) && cachedNormalized.gainers_3m.length) ||
        (Array.isArray(cachedNormalized.losers_3m) && cachedNormalized.losers_3m.length))
      ? Date.now()
      : 0
  );
  const lastNonEmptyBannerAtRef = useRef(
    cachedNormalized &&
      ((Array.isArray(cachedNormalized.banner_1h_price) && cachedNormalized.banner_1h_price.length) ||
        (Array.isArray(cachedNormalized.banner_1h_volume) && cachedNormalized.banner_1h_volume.length))
      ? Date.now()
      : 0
  );

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
  const lastFetchOkRef = useRef(true);
  const pollStartedRef = useRef(false);

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
        sentiment: norm.sentiment ?? null,
        sentiment_meta: norm.sentimentMeta ?? null,
        updated_at: norm.updated_at,
        meta: norm.meta,
        coverage: norm.coverage,
      };
      localStorage.setItem(MW_LAST_GOOD_DATA, JSON.stringify(minimal));
      localStorage.setItem(MW_LAST_GOOD_AT, String(lastGoodAtRef.current));
      const normalizedBase = normalizeBase(baseUrl);
      if (isCanonicalLocalBase(normalizedBase)) {
        localStorage.setItem(MW_BACKEND_KEY, CANONICAL_LOCAL_BASE);
      } else {
        localStorage.removeItem(MW_BACKEND_KEY);
      }
    } catch {}
  }, []);

  const applySnapshot = useCallback((norm, now = Date.now(), baseUrl = null) => {
    // DEV-only one-time payload shape log for diagnostics
    if (
      import.meta?.env?.DEV &&
      MW_DEBUG &&
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
    const backendPartial = Boolean(meta.partial);

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

    const cached3mEmpty =
      !cached ||
      ((Array.isArray(cached.gainers_3m) ? cached.gainers_3m.length : 0) === 0 &&
        (Array.isArray(cached.losers_3m) ? cached.losers_3m.length : 0) === 0);
    const next3mHasAny =
      (Array.isArray(norm.gainers_3m) ? norm.gainers_3m.length : 0) > 0 ||
      (Array.isArray(norm.losers_3m) ? norm.losers_3m.length : 0) > 0;

    const cachedBannersEmpty =
      !cached ||
      ((Array.isArray(cached.banner_1h_price) ? cached.banner_1h_price.length : 0) === 0 &&
        (Array.isArray(cached.banner_1h_volume) ? cached.banner_1h_volume.length : 0) === 0);
    const nextBannersHasAny =
      (Array.isArray(norm.banner_1h_price) ? norm.banner_1h_price.length : 0) > 0 ||
      (Array.isArray(norm.banner_1h_volume) ? norm.banner_1h_volume.length : 0) > 0;

    setError(null);
    setLoading(false);

    // Warming and staleness:
    // If the backend temporarily returns an empty payload but we still have
    // cached rows, avoid showing "warming" overlays on top of cached tables.
    const cachedHas3m = !cached3mEmpty;
    const effectiveWarming3m = next3mHasAny ? Boolean(backendWarming3m) : cachedHas3m ? false : Boolean(backendWarming3m);
    const effectiveWarming = hasAny ? Boolean(backendWarming) : cacheHasAny ? warming : Boolean(backendWarming);

    setWarming(effectiveWarming);
    setWarming3m(effectiveWarming3m);
    setStaleSeconds(backendStaleSeconds);
    setPartial(backendPartial);
    setLastGoodTs(backendLastGoodTs ?? lastGoodAtRef.current ?? null);

    if (!hasAny && cacheHasAny) {
      // Keep cached rows; do not replace snapshots
    } else {
      const cached1mLen = Array.isArray(cached?.gainers_1m) ? cached.gainers_1m.length : 0;
      const next1mLen = Array.isArray(norm.gainers_1m) ? norm.gainers_1m.length : 0;
      if (next1mLen > 0) lastNonEmpty1mAtRef.current = now;
      const useCached1m =
        next1mLen === 0 &&
        cached1mLen > 0 &&
        now - (lastNonEmpty1mAtRef.current || 0) < KEEP_NONEMPTY_1M_MS;
      const merged1m = useCached1m ? cached.gainers_1m : norm.gainers_1m;

      const cached3mLen =
        (Array.isArray(cached?.gainers_3m) ? cached.gainers_3m.length : 0) +
        (Array.isArray(cached?.losers_3m) ? cached.losers_3m.length : 0);
      const next3mLen =
        (Array.isArray(norm.gainers_3m) ? norm.gainers_3m.length : 0) +
        (Array.isArray(norm.losers_3m) ? norm.losers_3m.length : 0);
      if (next3mLen > 0) lastNonEmpty3mAtRef.current = now;
      const useCached3m =
        next3mLen === 0 &&
        cached3mLen > 0 &&
        now - (lastNonEmpty3mAtRef.current || 0) < KEEP_NONEMPTY_3M_MS;
      const merged3mGainers = useCached3m ? cached.gainers_3m : norm.gainers_3m;
      const merged3mLosers = useCached3m ? cached.losers_3m : norm.losers_3m;

      const cachedBannerLen =
        (Array.isArray(cached?.banner_1h_price) ? cached.banner_1h_price.length : 0) +
        (Array.isArray(cached?.banner_1h_volume) ? cached.banner_1h_volume.length : 0);
      const nextBannerLen =
        (Array.isArray(norm.banner_1h_price) ? norm.banner_1h_price.length : 0) +
        (Array.isArray(norm.banner_1h_volume) ? norm.banner_1h_volume.length : 0);
      if (nextBannerLen > 0) lastNonEmptyBannerAtRef.current = now;
      const useCachedBanners =
        nextBannerLen === 0 &&
        cachedBannerLen > 0 &&
        now - (lastNonEmptyBannerAtRef.current || 0) < KEEP_NONEMPTY_BANNER_MS;
      const mergedBannerPrice = useCachedBanners ? cached.banner_1h_price : norm.banner_1h_price;
      const mergedBannerVolume = useCachedBanners ? cached.banner_1h_volume : norm.banner_1h_volume;

      const mergedNorm = {
        ...norm,
        gainers_1m: merged1m,
        gainers_3m: merged3mGainers,
        losers_3m: merged3mLosers,
        banner_1h_price: mergedBannerPrice,
        banner_1h_volume: mergedBannerVolume,
      };
      mergedNorm.sentiment = norm.sentiment ?? cached?.sentiment ?? null;
      mergedNorm.sentimentMeta = norm.sentimentMeta ?? cached?.sentimentMeta ?? null;

      latestNormalizedRef.current = mergedNorm;
      persistLastGood(mergedNorm, baseUrl);
      setLatestBySymbol(norm.latest_by_symbol || {});
      setVolume1h(norm.volume1h || []);
      setAlerts(Array.isArray(norm.alerts) ? norm.alerts : []);

      // 1m: every fetch (table layer handles "live feel" without partial commits)
      commit1m(mergedNorm.gainers_1m);

      // 3m: publish every PUBLISH_3M_MS (default 12s)
      if (cached3mEmpty && next3mHasAny) {
        last3mPublishRef.current = now;
        setThreeMin({ gainers: mergedNorm.gainers_3m, losers: mergedNorm.losers_3m });
      } else if (now - last3mPublishRef.current >= PUBLISH_3M_MS) {
        last3mPublishRef.current = now;
        setThreeMin({ gainers: mergedNorm.gainers_3m, losers: mergedNorm.losers_3m });
      }

      // banners: publish every PUBLISH_BANNER_MS (default 2 minutes)
      if (cachedBannersEmpty && nextBannersHasAny) {
        lastBannerPublishRef.current = now;
        setBanners({ price: mergedNorm.banner_1h_price, volume: mergedNorm.banner_1h_volume });
      } else if (now - lastBannerPublishRef.current >= PUBLISH_BANNER_MS) {
        lastBannerPublishRef.current = now;
        setBanners({ price: mergedNorm.banner_1h_price, volume: mergedNorm.banner_1h_volume });
      }
    }

    setSentiment(norm.sentiment ?? cached?.sentiment ?? null);
    setSentimentMeta(norm.sentimentMeta ?? cached?.sentimentMeta ?? null);

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

    // MW_SPEC: do not silently try random ports.
    // - If VITE_API_BASE_URL is set, use it.
    // - Otherwise, in local dev, use the canonical base only.
    const envCandidate = normalizeBase(import.meta?.env?.VITE_API_BASE_URL || "");
    const envBase = envCandidate.startsWith("http") ? envCandidate : "";
    if (envBase) {
      candidates.push(envBase);
    } else {
      candidates.push(CANONICAL_LOCAL_BASE);
    }

    // Only honor cached base if it is canonical local.
    try {
      const cachedBase = typeof window !== "undefined" ? window.localStorage.getItem(MW_BACKEND_KEY) : null;
      if (cachedBase && isCanonicalLocalBase(cachedBase) && !candidates.includes(CANONICAL_LOCAL_BASE)) {
        candidates.push(CANONICAL_LOCAL_BASE);
      }
      if (cachedBase && !isCanonicalLocalBase(cachedBase)) {
        window.localStorage.removeItem(MW_BACKEND_KEY);
      }
    } catch {}

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
        const url = `${base.replace(/\/$/, "")}/data`;
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
        setBackendBase(isCanonicalLocalBase(okBase) ? CANONICAL_LOCAL_BASE : null);
        setConnectionStatus("LIVE");
        failCountRef.current = 0;
        if (!lastFetchOkRef.current) {
          console.info("[mw] data poll recovered");
          lastFetchOkRef.current = true;
        }
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
      if (lastFetchOkRef.current) {
        console.warn("[mw] data poll failed:", lastError || "fetch failed");
        lastFetchOkRef.current = false;
      }
    }

    inFlightRef.current = false;
    return succeeded;
  }, [applySnapshot]);

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
    if (pollStartedRef.current) return undefined;
    pollStartedRef.current = true;
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
      const ok = await fetchData();
      if (cancelled) return;
      const now = Date.now();
      let delay = now < backoffUntilRef.current ? BACKOFF_1M_MS : FAST_1M_MS;
      if (!ok && failCountRef.current > 0) {
        const expo = Math.min(10_000, 2000 * Math.pow(2, failCountRef.current - 1));
        delay = Math.max(delay, expo);
      }
      scheduleNext(delay);
    };

    run();

    return () => {
      cancelled = true;
      pollStartedRef.current = false;
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
          const ta =
            (typeof a.event_ts_ms === "number" && Number.isFinite(a.event_ts_ms) ? a.event_ts_ms : null) ??
            (typeof a.ts_ms === "number" && Number.isFinite(a.ts_ms) ? a.ts_ms : null) ??
            (Date.parse(a.ts || "") || 0);
          const tb =
            (typeof b.event_ts_ms === "number" && Number.isFinite(b.event_ts_ms) ? b.event_ts_ms : null) ??
            (typeof b.ts_ms === "number" && Number.isFinite(b.ts_ms) ? b.ts_ms : null) ??
            (Date.parse(b.ts || "") || 0);
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
    sentiment,
    sentimentMeta,
    error,
    loading,
    refetch: fetchData,
    heartbeatPulse,
    lastFetchTs,
    warming,
    warming3m,
    staleSeconds,
    partial,
    lastGoodTs,
    volume1h,
    connectionStatus,
    backendBase,
    lastGood: lastGoodRef.current,
    lastGoodLatestBySymbol: lastGoodRef.current?.latest_by_symbol || {},
    backendFailCount: failCountRef.current,
  }), [combinedData, oneMinRows, threeMin, banners, latestBySymbol, alerts, alertsBySymbol, getActiveAlert, sentiment, sentimentMeta, error, loading, fetchData, heartbeatPulse, lastFetchTs, warming, warming3m, staleSeconds, partial, lastGoodTs, volume1h, connectionStatus, backendBase]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export default DataContext;
