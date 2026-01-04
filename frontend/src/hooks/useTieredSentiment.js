import { useCallback, useEffect, useRef, useState } from "react";

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);
const FRESH_REQUEST_TIMEOUT_MS = Number(
  import.meta.env.VITE_SENTIMENT_FRESH_TIMEOUT_MS || 32000
);

const pick = (obj, ...keys) => {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
};

export const normalizeTieredSentiment = (rawLatest, rawTiered, rawSources) => {
  const base = rawLatest || {};
  const tiered = rawTiered || {};

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
      base.fear_greed_index ??
      base.fearGreedIndex ??
      overallMetrics.fear_greed_index ??
      50,
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
  const API_BASE =
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_BASE ||
    import.meta.env.VITE_API_URL ||
    import.meta.env.VITE_PROXY_TARGET ||
    "http://127.0.0.1:5003";

  const SENTIMENT_BASE =
    import.meta.env.VITE_SENTIMENT_BASE_URL ||
    import.meta.env.VITE_SENTIMENT_URL ||
    API_BASE;

  const apiBase = API_BASE.replace(/\/$/, "");
  const sentimentBase = SENTIMENT_BASE.replace(/\/$/, "");

  const lastGoodRef = useRef(null);
  const lastGoodSymbolRef = useRef(null);
  const intervalRef = useRef(null);
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
      const res = await fetch(`${sentimentBase}/api/sentiment/pipeline-health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(2000),
      });

      if (res.ok) {
        const healthData = await res.json();
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
      } else {
        setPipelineHealth({ running: false, checked: true });
        return false;
      }
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

      const res = await fetch(url, {
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      if (!res.ok) {
        throw new Error(`tiered sentiment ${res.status}`);
      }

      const json = await res.json();

      const payload = json?.data ?? json;
      setTieredData(payload);
      return payload;
    } catch (err) {
      console.warn("[useTieredSentiment] Failed to fetch tiered data:", err.message);
      return null;
    }
  }, [sentimentBase]);

  const fetchSources = useCallback(async () => {
    try {
      const res = await fetch(`${sentimentBase}/api/sentiment/sources`, {
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      if (!res.ok) {
        throw new Error(`sentiment sources ${res.status}`);
      }

      const json = await res.json();
      const payload = Array.isArray(json) ? json : json.sources ?? [];
      setSources(payload);
      return payload;
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
        const res = await fetch(url, {
          cache: "no-store",
          signal: AbortSignal.timeout(
            freshLatest ? FRESH_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS
          ),
        });

        if (!res.ok) throw new Error(`sentiment ${res.status}`);

        const json = await res.json();
        return json;
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

      if (!enabled) return;

      if (Date.now() < cooldownUntil) {
        return;
      }

      setValidating(true);
      setError(null);
      setStale(false);

      try {
        const [symbolData, tieredDataResult, sourcesResult] = await Promise.allSettled([
          fetchSymbolSentiment(freshLatest),
          fetchTieredData(),
          fetchSources(),
        ]);

        let symbolJson = null;
        if (symbolData.status === "fulfilled") {
          symbolJson = symbolData.value;
        } else {
          throw symbolData.reason;
        }

        const tieredJson = tieredDataResult.status === "fulfilled" ? tieredDataResult.value : null;
        const sourcesJson = sourcesResult.status === "fulfilled" ? sourcesResult.value : null;

        const merged = normalizeTieredSentiment(symbolJson, tieredJson, sourcesJson);

        lastGoodRef.current = merged;
        lastGoodSymbolRef.current = symbol || "";
        setRaw(symbolJson);
        setData(merged);
        setLoading(false);
        setStale(false);
      } catch (err) {
        setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);

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
