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

export function useTieredSentiment(
  symbol,
  { enabled = true, refreshMs = 30000 } = {}
) {
  const API_BASE =
    import.meta.env.VITE_API_BASE ||
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    "http://127.0.0.1:5001";

  const base = API_BASE.replace(/\/$/, "");

  const lastGoodRef = useRef(null);
  const lastGoodSymbolRef = useRef(null);
  const [raw, setRaw] = useState(null);
  const [data, setData] = useState(() => normalizeSentiment(null));
  const [tieredData, setTieredData] = useState(null);
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

  // Fetch symbol-specific sentiment
  const fetchSymbolSentiment = useCallback(async () => {
    const url = symbol
      ? `${base}/api/sentiment/latest?symbol=${encodeURIComponent(symbol)}`
      : `${base}/api/sentiment/latest`;

    const res = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });

    if (!res.ok) throw new Error(`sentiment ${res.status}`);

    return await res.json();
  }, [base, symbol]);

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

  const fetchAll = useCallback(async () => {
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
      const [symbolData, tieredDataResult] = await Promise.allSettled([
        fetchSymbolSentiment(),
        fetchTieredData(),
      ]);

      // Get symbol data (primary)
      let symbolJson = null;
      if (symbolData.status === 'fulfilled') {
        symbolJson = symbolData.value;
      } else {
        throw symbolData.reason;
      }

      // Get tiered data (secondary, optional)
      let tieredJson = null;
      if (tieredDataResult.status === 'fulfilled') {
        tieredJson = tieredDataResult.value;
      }

      // Merge and normalize
      const merged = mergeTieredData(symbolJson, tieredJson);

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
  }, [enabled, cooldownUntil, symbol, fetchSymbolSentiment, fetchTieredData, mergeTieredData]);

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
