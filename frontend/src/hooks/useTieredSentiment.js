import { useCallback, useEffect, useRef, useState } from "react";
import { getSentimentBaseUrl } from "../api";

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);
const FRESH_REQUEST_TIMEOUT_MS = Number(
  import.meta.env.VITE_SENTIMENT_FRESH_TIMEOUT_MS || 32000
);
const SLOW_AUX_MS = 60000;

function toNum(v, fallback = null) {
  if (v === null || v === undefined) return fallback;
  if (typeof v === "number") return Number.isFinite(v) ? v : fallback;
  if (typeof v === "string") {
    const s = v.trim();
    if (!s || s === "-" || s === "—" || s.toLowerCase() === "n/a") return fallback;
    const cleaned = s.replace(/,/g, "").replace(/%/g, "");
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : fallback;
  }
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

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

  // Clamp to [0,1] or return null if missing - NO MORE 0.5 FORGERY
  const clamp01 = (v) => {
    const n = toNum(v, null);
    if (n === null) return null;
    return Math.max(0, Math.min(1, n));
  };

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

  // Compute sentiment values - null when missing, not 0.5
  const overallSent = clamp01(
    overallMetrics.weighted_sentiment ?? base.overall_sentiment ?? base.sentiment_score
  );
  const t1 = clamp01(tierScores.tier1);
  const t2 = clamp01(tierScores.tier2);
  const t3 = clamp01(tierScores.tier3);
  const tf = clamp01(tierScores.fringe);
  const conf = clamp01(overallMetrics.confidence ?? base.confidence);

  return {
    normalized: true,
    schemaVersion: 1,
    hasTieredData,
    overallSentiment: overallSent,
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
    // null instead of 0.5 - UI decides how to render "UNAVAILABLE"
    tierScores: { tier1: t1, tier2: t2, tier3: t3, fringe: tf },
    confidence: conf,
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

      try {
        const now = Date.now();
        const auxTieredStale = now - lastTieredFetchRef.current > SLOW_AUX_MS;
        const auxSourcesStale = now - lastSourcesFetchRef.current > SLOW_AUX_MS;

        const shouldFetchTiered = forceAux || auxTieredStale;
        const shouldFetchSources = forceAux || auxSourcesStale;

        // 1) LATEST FIRST (await)
        const symbolJson = await fetchSymbolSentiment(freshLatest);
        const latestWithProxy = symbolJson;

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

        const fallback = lastGoodRef.current;
        const fallbackSymbol = lastGoodSymbolRef.current;
        if (fallback && fallbackSymbol === (symbol || "")) {
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
    [enabled, cooldownUntil, symbol, fetchSymbolSentiment, fetchTieredData, fetchSources]
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
