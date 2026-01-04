import { useCallback, useEffect, useRef, useState } from "react";
import normalizeSentiment from "../adapters/normalizeSentiment";

/**
 * Enhanced sentiment hook that fetches from BOTH:
 * 1. The original /api/sentiment/latest (for symbol-specific data)
 * 2. The new /api/sentiment/tiered (for tiered breakdown from the pipeline)
 *
 * Merges both data sources to provide comprehensive sentiment analysis
 */

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);
const FRESH_REQUEST_TIMEOUT_MS = Number(
  import.meta.env.VITE_SENTIMENT_FRESH_TIMEOUT_MS || 32000
);

export function useTieredSentiment(
  symbol,
  { enabled = true, refreshMs = 30000 } = {}
) {
  // Use relative paths so Vite proxy handles the request
  // This avoids CORS issues by keeping requests same-origin
  const base = "";

  const lastGoodRef = useRef(null);
  const lastGoodSymbolRef = useRef(null);
  const [raw, setRaw] = useState(null);
  const [data, setData] = useState(() => normalizeSentiment(null));
  const [tieredData, setTieredData] = useState(null);
  const [sources, setSources] = useState([]);
  const [pipelineHealth, setPipelineHealth] = useState({ running: false, checked: false });
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);

  // Check if sentiment pipeline is healthy
  const checkPipelineHealth = useCallback(async () => {
    try {
      const res = await fetch(`${base}/api/sentiment/pipeline-health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(2000),
      });

      if (res.ok) {
        const healthData = await res.json();
        setPipelineHealth({
          running: healthData.pipeline_running || false,
          checked: true,
          data: healthData,
        });
        return healthData.pipeline_running;
      } else {
        setPipelineHealth({ running: false, checked: true });
        return false;
      }
    } catch (err) {
      setPipelineHealth({ running: false, checked: true, error: err.message });
      return false;
    }
  }, [base]);

  // Fetch tiered sentiment from the pipeline
  const fetchTieredData = useCallback(async () => {
    try {
      const res = await fetch(`${base}/api/sentiment/tiered`, {
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      if (!res.ok) {
        throw new Error(`tiered sentiment ${res.status}`);
      }

      const json = await res.json();

      if (json.success && json.data) {
        setTieredData(json.data);
        return json.data;
      } else {
        throw new Error(json.message || 'Failed to fetch tiered data');
      }
    } catch (err) {
      console.warn('[useTieredSentiment] Failed to fetch tiered data:', err.message);
      return null;
    }
  }, [base]);

  const fetchSources = useCallback(async () => {
    try {
      const res = await fetch(`${base}/api/sentiment/sources`, {
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
      console.warn('[useTieredSentiment] Failed to fetch sources:', err?.message || err);
      return null;
    }
  }, [base]);

  const buildLatestUrl = useCallback(
    (freshLatest = false) => {
      const qs = new URLSearchParams();
      if (symbol) qs.set("symbol", symbol);
      if (freshLatest) qs.set("fresh", "1");
      const query = qs.toString();
      return `${base}/api/sentiment/latest${query ? `?${query}` : ""}`;
    },
    [base, symbol]
  );

  // Fetch symbol-specific sentiment (optionally with fresh=1)
  const fetchSymbolSentiment = useCallback(
    async (freshLatest = false) => {
      const url = buildLatestUrl(freshLatest);
      console.log('[useTieredSentiment] Fetching symbol sentiment for:', symbol, 'URL:', url);
      console.log('[useTieredSentiment] Timeout setting:', freshLatest ? FRESH_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS);

      try {
        const res = await fetch(url, {
          cache: "no-store",
          signal: AbortSignal.timeout(
            freshLatest ? FRESH_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS
          ),
        });

        console.log('[useTieredSentiment] Fetch response received:', res.status, res.ok);

        if (!res.ok) throw new Error(`sentiment ${res.status}`);

        const json = await res.json();
        console.log('[useTieredSentiment] Fetch JSON parsed:', json);
        return json;
      } catch (err) {
        console.error('[useTieredSentiment] fetchSymbolSentiment ERROR:', err.name, err.message);
        throw err;
      }
    },
    [buildLatestUrl, symbol]
  );

  // Merge tiered data into the normalized sentiment structure
  const mergeTieredData = useCallback((symbolData, tieredData) => {
    if (!tieredData) {
      return normalizeSentiment(symbolData);
    }

    const overallMetrics = tieredData.overall_metrics || {};
    const tierScores = tieredData.tier_scores || {};
    const divergences = tieredData.divergences || [];

    // Extract tier scores
    const tier1Score = tierScores.tier1 || 0.5;
    const tier2Score = tierScores.tier2 || 0.5;
    const tier3Score = tierScores.tier3 || 0.5;
    const fringeScore = tierScores.fringe || 0.5;

    // Calculate divergence alerts
    const divergenceAlerts = [];

    // Check for institutional vs retail divergence
    const institutionalRetailDivergence = Math.abs(tier1Score - tier3Score);
    if (institutionalRetailDivergence > 0.2) {
      const tier1Pct = (tier1Score * 100).toFixed(0);
      const tier3Pct = (tier3Score * 100).toFixed(0);

      divergenceAlerts.push({
        type: institutionalRetailDivergence > 0.3 ? 'warning' : 'info',
        message: tier1Score > tier3Score
          ? `🐋 Whales (${tier1Pct}%) more bullish than Degens (${tier3Pct}%) - Smart money accumulating while apes panic sell?`
          : `💎 Diamond Hands (${tier3Pct}%) more bullish than Whales (${tier1Pct}%) - Retail FOMO while smart money exits? Possible local top.`
      });
    }

    // Check for mainstream vs fringe divergence
    const mainstreamFringeDivergence = Math.abs(tier2Score - fringeScore);
    if (mainstreamFringeDivergence > 0.25) {
      const tier2Pct = (tier2Score * 100).toFixed(0);
      const fringePct = (fringeScore * 100).toFixed(0);

      divergenceAlerts.push({
        type: 'info',
        message: tier2Score > fringeScore
          ? `📰 Normies (${tier2Pct}%) more bullish than Anons (${fringePct}%) - Mainstream catching up or /biz/ already priced in?`
          : `🌚 Moonboys (${fringePct}%) more bullish than Normies (${tier2Pct}%) - Early signal or just schizo hopium?`
      });
    }

    // Add custom divergences from the pipeline
    if (divergences && Array.isArray(divergences)) {
      divergences.forEach(div => {
        divergenceAlerts.push({
          type: div.severity === 'high' ? 'warning' : 'info',
          message: div.message
        });
      });
    }

    // Build enhanced sentiment object
    const enhanced = {
      ...normalizeSentiment(symbolData),

      // Override with tiered data
      overallSentiment: overallMetrics.weighted_sentiment || symbolData?.overall_sentiment || 0.5,

      // Add tier scores (camelCase for consistency)
      tierScores: {
        tier1: tier1Score,
        tier2: tier2Score,
        tier3: tier3Score,
        fringe: fringeScore,
      },

      // Enhanced source breakdown
      sourceBreakdown: {
        tier1: tieredData.total_sources?.tier1 || 2,
        tier2: tieredData.total_sources?.tier2 || 3,
        tier3: tieredData.total_sources?.tier3 || 2,
        fringe: tieredData.total_sources?.fringe || 1,
      },

      // Social breakdown derived from tiers
      socialBreakdown: {
        reddit: tier2Score,      // Reddit is tier2
        twitter: tier3Score,     // Twitter is tier3
        telegram: tier3Score,    // Telegram is tier3
        chan: fringeScore,       // 4chan is fringe
        news: tier2Score,        // News feeds are tier2
      },

      // Divergence alerts (camelCase)
      divergenceAlerts: divergenceAlerts,

      // Metadata
      confidence: overallMetrics.confidence || 0.5,
      totalDataPoints: tieredData.total_data_points || 0,
      pipelineTimestamp: tieredData.timestamp,
      hasTieredData: true,
    };

    return enhanced;
  }, []);

  const fetchAll = useCallback(async (options = {}) => {
    const freshLatest = options?.freshLatest === true;

    console.log('[useTieredSentiment] fetchAll called for symbol:', symbol, 'enabled:', enabled);

    if (!enabled) return;

    // Cooldown: if we failed recently, don't spam
    if (Date.now() < cooldownUntil) {
      return;
    }

    setValidating(true);
    setError(null);
    setStale(false);

    try {
      // Fetch both in parallel
      console.log('[useTieredSentiment] Starting Promise.allSettled for 3 fetches...');
      const [symbolData, tieredDataResult, sourcesResult] = await Promise.allSettled([
        fetchSymbolSentiment(freshLatest),
        fetchTieredData(),
        fetchSources(),
      ]);

      console.log('[useTieredSentiment] Promise.allSettled completed');
      console.log('[useTieredSentiment] symbolData status:', symbolData.status);
      console.log('[useTieredSentiment] tieredDataResult status:', tieredDataResult.status);
      console.log('[useTieredSentiment] sourcesResult status:', sourcesResult.status);

      // Get symbol data (primary)
      let symbolJson = null;
      if (symbolData.status === 'fulfilled') {
        symbolJson = symbolData.value;
        console.log('[useTieredSentiment] symbolData value:', symbolJson);
      } else {
        console.error('[useTieredSentiment] symbolData REJECTED:', symbolData.reason);
        throw symbolData.reason;
      }

      // Get tiered data (secondary, optional)
      let tieredJson = null;
      if (tieredDataResult.status === 'fulfilled') {
        tieredJson = tieredDataResult.value;
      } else {
        console.warn('[useTieredSentiment] tieredData rejected:', tieredDataResult.reason?.message);
      }

      // Merge and normalize
      const merged = mergeTieredData(symbolJson, tieredJson);

      console.log('[useTieredSentiment] Merged data for', symbol, ':', merged);
      console.log('[useTieredSentiment] overallSentiment:', merged.overallSentiment);

      lastGoodRef.current = merged;
      lastGoodSymbolRef.current = symbol || "";
      setRaw(symbolJson);
      setData(merged);
      setLoading(false);
      setStale(false);

    } catch (err) {
      // Set cooldown on failure
      setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);

      const fallback = lastGoodRef.current;
      const fallbackSymbol = lastGoodSymbolRef.current;

      if (fallback && fallbackSymbol === (symbol || "")) {
        setData(fallback);
        setError(null);
        setStale(true);
      }

      if (!fallback) {
        setError(err);
        // Set minimal fallback data
        setData(normalizeSentiment(null));
      }

      setLoading(false);
    } finally {
      setValidating(false);
    }
  }, [enabled, cooldownUntil, symbol, fetchSymbolSentiment, fetchTieredData, fetchSources, mergeTieredData]);

  // Check pipeline health on mount
  useEffect(() => {
    checkPipelineHealth();
  }, [checkPipelineHealth]);

  // Fetch data periodically
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    fetchAll();
    const id = setInterval(fetchAll, refreshMs);
    return () => clearInterval(id);
  }, [fetchAll, enabled, refreshMs]);

  // Reset on symbol change
  useEffect(() => {
    lastGoodRef.current = null;
    lastGoodSymbolRef.current = symbol || "";
    setLoading(true);
    setError(null);
    setStale(false);
    setData(normalizeSentiment(null));
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
