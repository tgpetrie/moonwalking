import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBaseUrl, getSentimentBaseUrl } from "../api";

// Coerce anything → number (or fallback)
function toNum(v, fallback = 0) {
  if (v === null || v === undefined) return fallback;
  if (typeof v === "number") return Number.isFinite(v) ? v : fallback;
  if (typeof v === "boolean") return v ? 1 : 0;

  const s = String(v).trim();
  if (!s) return fallback;

  // allow "12.3%", "$1,234.56", "1 234", etc.
  const cleaned = s
    .replace(/[%$,]/g, "")
    .replace(/\s+/g, "");

  const n = Number(cleaned);
  return Number.isFinite(n) ? n : fallback;
}

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);
const FRESH_REQUEST_TIMEOUT_MS = Number(
  import.meta.env.VITE_SENTIMENT_FRESH_TIMEOUT_MS || 32000
);
const SLOW_AUX_MS = 60000;

const parsePipelineResponse = async (response) => {
  let payload = null;
  try {
    payload = await response.json();
  } catch (err) {
    payload = null;
  }
  if (!response.ok) {
    const detail =
      payload?.detail ?? payload?.error ?? payload?.message ?? response.statusText ?? `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return payload;
};

const safePipelineFetch = async (url, options = {}) => {
  const response = await fetch(url, options);
  return await parsePipelineResponse(response);
};

const pick = (obj, ...keys) => {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
};

export const normalizeTieredSentiment = (rawLatest, rawTiered, rawSources) => {
  const base = rawLatest || {};
  const tiered = rawTiered || {};

  const fgBlock = pick(base, "fear_greed", "fearGreed") || {};
  const fgValueRaw = pick(fgBlock, "value", "index", "score", "fear_greed_index");
  const fgValue = toNum(fgValueRaw, null);
  const fgLabel =
    pick(fgBlock, "label", "classification", "status", "value_classification") ||
    pick(base, "fear_greed_label", "fearGreedLabel") ||
    null;
  const fgUpdated =
    pick(fgBlock, "updated_at", "timestamp", "ts") ||
    pick(base, "fear_greed_timestamp", "fearGreedTimestamp") ||
    pick(base, "updated_at", "updatedAt") ||
    null;
  const fgStale = Boolean(pick(fgBlock, "stale"));

  const sentimentHistoryRaw =
    pick(base, "sentiment_history", "sentimentHistory") || [];
  const sentimentHistory = Array.isArray(sentimentHistoryRaw)
    ? sentimentHistoryRaw.map((p) => ({
        timestamp: p.timestamp,
        sentiment: p.sentiment ?? p.sentiment_score ?? null,
        priceNormalized: p.price_normalized ?? p.priceNormalized ?? p.price ?? null,
        price: p.price ?? null,
      }))
    : [];

  const socialHistoryRaw =
    pick(base, "social_history", "socialHistory") || [];
  const socialHistory = Array.isArray(socialHistoryRaw)
    ? socialHistoryRaw.map((p) => ({
        timestamp: p.timestamp,
        reddit: p.reddit ?? null,
        twitter: p.twitter ?? null,
        telegram: p.telegram ?? null,
        chan: p.chan ?? null,
      }))
    : [];

  const socialBreakdown =
    pick(base, "social_breakdown", "socialBreakdown") ||
    pick(tiered, "social_breakdown", "socialBreakdown") ||
    {};

  const sourceBreakdown =
    pick(base, "source_breakdown", "sourceBreakdown") ||
    pick(tiered, "source_breakdown", "sourceBreakdown") ||
    (typeof tiered.total_sources === "number"
      ? { tier1: 0, tier2: 0, tier3: 0, fringe: 0, total: tiered.total_sources }
      : {}) ||
    {};

  const divergenceAlerts =
    pick(base, "divergence_alerts", "divergenceAlerts") ||
    pick(tiered, "divergences") ||
    [];

  const trendingTopics =
    pick(base, "trending_topics", "trendingTopics") ||
    pick(tiered, "trending_topics", "trendingTopics") ||
    [];

  const tierScores = pick(tiered, "tier_scores", "tierScores") || {};
  const overallMetrics = pick(tiered, "overall_metrics", "overallMetrics") || {};
  const hasTieredData =
    Boolean(rawTiered) ||
    Boolean(pick(tiered, "tier_scores", "tierScores")) ||
    Boolean(pick(tiered, "overall_metrics", "overallMetrics"));

  const marketPulseRaw = pick(base, "market_pulse", "marketPulse", "market") || {};
  const marketPulse = {
    totalMarketCap: toNum(
      pick(marketPulseRaw, "total_market_cap_usd", "market_cap_usd", "total_market_cap"),
      null
    ),
    totalVolume: toNum(
      pick(marketPulseRaw, "total_volume_usd", "volume_usd", "total_volume"),
      null
    ),
    btcDominance: toNum(
      pick(marketPulseRaw, "btc_dominance", "btc_dominance_pct", "btc_dominance_usd"),
      null
    ),
    mcapChange24hPct: toNum(
      pick(
        marketPulseRaw,
        "mcap_change_24h_pct",
        "market_cap_change_percentage_24h_usd",
        "mcap_change_pct"
      ),
      null
    ),
    updatedAt: pick(marketPulseRaw, "updated_at", "timestamp", "ts") || null,
    sourceUrl: pick(marketPulseRaw, "source_url", "sourceUrl") || null,
    stale: Boolean(pick(marketPulseRaw, "stale")),
  };

  return {
    normalized: true,
    schemaVersion: 1,
    hasTieredData,
    overallSentiment:
      overallMetrics.weighted_sentiment ??
      base.overall_sentiment ??
      base.sentiment_score ??
      0.5,
    fearGreedIndex:
      (fgValue !== null ? fgValue : undefined) ??
      base.fear_greed_index ??
      base.fearGreedIndex ??
      overallMetrics.fear_greed_index ??
      null,
    fearGreedLabel: fgLabel,
    fearGreedUpdatedAt: fgUpdated,
    fearGreedStatus:
      (fgValue !== null || base.fear_greed_index !== undefined || base.fearGreedIndex !== undefined)
        ? fgStale
          ? "STALE"
          : "LIVE"
        : "UNAVAILABLE",
    marketPulse,
    marketPulseStatus:
      marketPulse.totalMarketCap !== null || marketPulse.totalVolume !== null
        ? marketPulse.stale
          ? "STALE"
          : "LIVE"
        : "UNAVAILABLE",
    sentimentHistory,
    socialHistory,
    socialBreakdown,
    sourceBreakdown,
    divergenceAlerts,
    trendingTopics,
    tierScores: {
      tier1: tierScores.tier1 ?? 0.5,
      tier2: tierScores.tier2 ?? 0.5,
      tier3: tierScores.tier3 ?? 0.5,
      fringe: tierScores.fringe ?? 0.5,
    },
    confidence: overallMetrics.confidence ?? base.confidence ?? 0.5,
    totalDataPoints: tiered.total_data_points ?? base.total_data_points ?? 0,
    pipelineTimestamp: tiered.timestamp ?? base.timestamp,
    sources: rawSources || [],
  };
};

const emptyNormalized = normalizeTieredSentiment(null, null, null);

export function useTieredSentiment(
  symbol,
  { enabled = true, refreshMs = 15000 } = {}
) {
  const apiBase = (getApiBaseUrl() || "").replace(/\/$/, "");
  const sentimentBase = (getSentimentBaseUrl() || "").replace(/\/$/, "");

  const lastGoodRef = useRef(null);
  const lastGoodSymbolRef = useRef(null);
  const intervalRef = useRef(null);
  const latestRef = useRef(null);
  const fetchSeqRef = useRef(0);
  const tieredRef = useRef(null);
  const sourcesRef = useRef([]);
  const lastTieredFetchRef = useRef(0);
  const lastSourcesFetchRef = useRef(0);
  const proxyCacheRef = useRef({ ts: 0, data: null });
  const [raw, setRaw] = useState(null);
  const [data, setData] = useState(() => emptyNormalized);
  const [tieredData, setTieredData] = useState(null);
  const [sources, setSources] = useState([]);
  const [pipelineHealth, setPipelineHealth] = useState({ running: false, checked: false });
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);

  const checkPipelineHealth = useCallback(async () => {
    try {
      const res = await fetch(`${sentimentBase}/api/sentiment/health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(2000),
      });

      const healthData = await parsePipelineResponse(res);
      const running =
        Boolean(healthData?.pipeline_running) ||
        Boolean(healthData?.running) ||
        healthData?.status === "healthy" ||
        healthData?.status === "ok";
      setPipelineHealth({
        running,
        checked: true,
        data: healthData,
      });
      return running;
    } catch (err) {
      setPipelineHealth({ running: false, checked: true, error: err.message });
      return false;
    }
  }, [sentimentBase]);

  const fetchTieredData = useCallback(async () => {
    try {
      const qs = new URLSearchParams();
      if (symbol) qs.set("symbol", symbol);
      const url = `${sentimentBase}/api/sentiment/tiered${qs.toString() ? `?${qs}` : ""}`;

      const payload = await safePipelineFetch(url, {
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      setTieredData(payload);
      tieredRef.current = payload;
      return payload;
    } catch (err) {
      console.warn("[useTieredSentiment] Failed to fetch tiered data:", err.message);
      return null;
    }
  }, [sentimentBase, symbol]);

  const fetchSources = useCallback(async () => {
    try {
      const payload = await safePipelineFetch(`${sentimentBase}/api/sentiment/sources`, {
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      const list = Array.isArray(payload) ? payload : payload.sources ?? [];
      setSources(list);
      sourcesRef.current = list;
      return list;
    } catch (err) {
      console.warn("[useTieredSentiment] Failed to fetch sources:", err?.message || err);
      return null;
    }
  }, [sentimentBase]);

  const buildLatestUrl = useCallback(
    (freshLatest = false) => {
      const qs = new URLSearchParams();
      if (symbol) qs.set("symbol", symbol);
      if (freshLatest) qs.set("fresh", "1");
      const query = qs.toString();
      return `${sentimentBase}/api/sentiment/latest${query ? `?${query}` : ""}`;
    },
    [sentimentBase, symbol]
  );

  const fetchSymbolSentiment = useCallback(
    async (freshLatest = false) => {
      const url = buildLatestUrl(freshLatest);
      try {
        const payload = await safePipelineFetch(url, {
          cache: "no-store",
          signal: AbortSignal.timeout(
            freshLatest ? FRESH_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS
          ),
        });

        return payload;
      } catch (err) {
        console.error("[useTieredSentiment] fetchSymbolSentiment ERROR:", err.name, err.message);
        throw err;
      }
    },
    [buildLatestUrl, symbol]
  );

  const fetchProxySentiment = useCallback(async () => {
    const now = Date.now();
    if (proxyCacheRef.current.data && now - proxyCacheRef.current.ts < 120000) {
      return proxyCacheRef.current.data;
    }

    const base = (apiBase || "http://127.0.0.1:5003").replace(/\/$/, "");
    const fetchOne = async (path) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2500);
      try {
        const res = await fetch(`${base}${path}`, { cache: "no-store", signal: controller.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      } finally {
        clearTimeout(timeout);
      }
    };

    try {
      const [fngRes, marketRes] = await Promise.allSettled([
        fetchOne("/api/sentiment/fng"),
        fetchOne("/api/sentiment/market"),
      ]);
      const payload = {
        fng: fngRes.status === "fulfilled" ? fngRes.value : null,
        market: marketRes.status === "fulfilled" ? marketRes.value : null,
      };
      proxyCacheRef.current = { ts: now, data: payload };
      return payload;
    } catch (err) {
      console.warn("[useTieredSentiment] proxy sentiment fetch failed", err?.message || err);
      return proxyCacheRef.current.data;
    }
  }, [apiBase]);

  const fetchAll = useCallback(
    async (options = {}) => {
      const freshLatest = options?.freshLatest === true;
      const forceAux = options?.forceAux === true;

      if (!enabled) return;
      if (Date.now() < cooldownUntil) return;

      const seq = ++fetchSeqRef.current;
      const sym = symbol || "";

      setValidating(true);
      setError(null);
      setStale(false);

      const proxyPromise = fetchProxySentiment();

      try {
        const now = Date.now();
        const auxTieredStale = now - lastTieredFetchRef.current > SLOW_AUX_MS;
        const auxSourcesStale = now - lastSourcesFetchRef.current > SLOW_AUX_MS;

        const shouldFetchTiered = forceAux || auxTieredStale;
        const shouldFetchSources = forceAux || auxSourcesStale;

        // 1) LATEST FIRST (await)
        const symbolJson = await fetchSymbolSentiment(freshLatest);
        const proxies = await proxyPromise.catch(() => null);
        const latestWithProxy = {
          ...symbolJson,
          fear_greed: symbolJson?.fear_greed ?? symbolJson?.fearGreed ?? proxies?.fng,
          market_pulse: symbolJson?.market_pulse ?? symbolJson?.marketPulse ?? proxies?.market,
        };

        // If a newer fetch started, drop this result on the floor.
        if (fetchSeqRef.current !== seq || !enabled || (symbol || "") !== sym) return;

        latestRef.current = latestWithProxy;

        // Merge using whatever aux we already have (cached)
        const mergedImmediate = normalizeTieredSentiment(
          latestWithProxy,
          tieredRef.current,
          sourcesRef.current
        );

        lastGoodRef.current = mergedImmediate;
        lastGoodSymbolRef.current = sym;

        setRaw(symbolJson);
        setData(mergedImmediate);
        setLoading(false);
        setStale(false);

        // 2) AUX IN BACKGROUND (do not block latest paint)
        if (shouldFetchTiered) {
          fetchTieredData().then((tieredPayload) => {
            if (fetchSeqRef.current !== seq || !enabled || (symbol || "") !== sym) return;

            if (tieredPayload) {
              lastTieredFetchRef.current = Date.now();
              tieredRef.current = tieredPayload;
              setTieredData(tieredPayload);
            }

            const latest = latestRef.current;
            if (latest) {
              const merged = normalizeTieredSentiment(latest, tieredRef.current, sourcesRef.current);
              lastGoodRef.current = merged;
              lastGoodSymbolRef.current = sym;
              setData(merged);
            }
          });
        }

        if (shouldFetchSources) {
          fetchSources().then((sourcesPayload) => {
            if (fetchSeqRef.current !== seq || !enabled || (symbol || "") !== sym) return;

            if (Array.isArray(sourcesPayload)) {
              lastSourcesFetchRef.current = Date.now();
              sourcesRef.current = sourcesPayload;
              setSources(sourcesPayload);
            }

            const latest = latestRef.current;
            if (latest) {
              const merged = normalizeTieredSentiment(latest, tieredRef.current, sourcesRef.current);
              lastGoodRef.current = merged;
              lastGoodSymbolRef.current = sym;
              setData(merged);
            }
          });
        }
      } catch (err) {
        setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);
        setPipelineHealth((prev) => ({
          ...prev,
          running: false,
          checked: true,
          error: err?.message,
        }));

        const proxies = await proxyPromise.catch(() => null);
        const fallback = lastGoodRef.current;
        const fallbackSymbol = lastGoodSymbolRef.current;

        if (proxies && (proxies.fng || proxies.market)) {
          const merged = normalizeTieredSentiment(
            { fear_greed: proxies.fng, market_pulse: proxies.market },
            tieredRef.current,
            sourcesRef.current
          );
          lastGoodRef.current = merged;
          lastGoodSymbolRef.current = sym;
          setData(merged);
          setError(null);
          setStale(Boolean(proxies.fng?.stale || proxies.market?.stale));
        } else if (fallback && fallbackSymbol === (symbol || "")) {
          setData(fallback);
          setError(null);
          setStale(true);
        } else {
          setError(err);
          setData(emptyNormalized);
        }

        setLoading(false);
      } finally {
        setValidating(false);
      }
    },
    [enabled, cooldownUntil, symbol, fetchSymbolSentiment, fetchTieredData, fetchSources, fetchProxySentiment]
  );

  useEffect(() => {
    if (!enabled) return undefined;
    checkPipelineHealth();
  }, [checkPipelineHealth, enabled]);

  useEffect(() => {
    const clearIntervalRef = (reason) => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        if (import.meta.env.DEV) {
          console.debug("[useTieredSentiment] polling stopped", reason || "cleanup");
        }
      }
    };

    if (!enabled) {
      clearIntervalRef("disabled");
      return () => clearIntervalRef("cleanup");
    }

    fetchAll();

    clearIntervalRef("restart");
    intervalRef.current = setInterval(fetchAll, refreshMs);
    if (import.meta.env.DEV) {
      console.debug("[useTieredSentiment] polling started", { refreshMs, symbol });
    }

    return () => clearIntervalRef("cleanup");
  }, [fetchAll, enabled, refreshMs, symbol]);

  useEffect(() => {
    lastGoodRef.current = null;
    lastGoodSymbolRef.current = symbol || "";
    setLoading(true);
    setError(null);
    setStale(false);
    setData(emptyNormalized);
  }, [symbol]);

  return {
    data,
    raw,
    tieredData,
    sources,
    pipelineHealth,
    loading,
    validating,
    stale,
    error,
    refresh: fetchAll,
    checkHealth: checkPipelineHealth,
  };
}

export default useTieredSentiment;
