import { useMemo } from "react";
import { useData } from "../context/DataContext";
import { normalizeSentiment } from "../adapters/normalizeSentiment";

/**
 * useMarketHeat — drop-in replacement for useSentimentLatest / useTieredSentiment.
 *
 * Reads sentiment data from the main DataContext (which already polls /data every ~8s)
 * instead of making separate /api/sentiment/* requests. The backend now computes
 * Market Heat from the Coinbase tape and injects it into the /data payload.
 *
 * Returns a superset shape compatible with both useSentimentLatest and useTieredSentiment:
 *   { data, raw, loading, validating, stale, error, refresh, sentimentMeta, pipelineStatus,
 *     tieredData, sources, pipelineHealth,
 *     heat, regime, heatLabel, confidence, components, reasons, fearGreed, sentimentHistory }
 */
export function useMarketHeat() {
  const ctx = useData();
  const rawSentiment = ctx?.sentiment ?? null;
  const rawMeta = ctx?.sentimentMeta ?? null;
  const loading = ctx?.loading ?? false;
  const connectionStatus = ctx?.connectionStatus ?? "DOWN";

  // Derive stale / pipelineStatus from connection + meta
  const pipelineStatus = useMemo(() => {
    if (connectionStatus === "DOWN") return "OFFLINE";
    if (!rawMeta) return rawSentiment ? "STALE" : "OFFLINE";
    if (rawMeta.ok && rawMeta.pipelineRunning) return "LIVE";
    if (rawSentiment) return "STALE";
    return "OFFLINE";
  }, [connectionStatus, rawMeta, rawSentiment]);

  // Build the `data` object that consumers (SentimentPopupAdvanced, SentimentCard, etc.) read
  const data = useMemo(() => {
    const base = rawSentiment
      ? normalizeSentiment({ ...rawSentiment, sentiment_meta: rawMeta })
      : normalizeSentiment(null);

    // Tape heat fields (not in normalizeSentiment but consumed by popup)
    const tapeHeat = rawSentiment?.tape_heat ?? null;
    const components = rawSentiment?.components ?? {};
    const reasons = rawSentiment?.reasons ?? [];
    const regime = tapeHeat?.regime ?? rawSentiment?.regime ?? "calm";
    const heatLabel = tapeHeat?.label ?? "NEUTRAL";

    // History from tape (backend sends as sentiment_history)
    const sentimentHistory = (rawSentiment?.sentiment_history ?? []).map((p) => ({
      timestamp: p?.timestamp,
      sentiment: typeof p?.sentiment === "number" ? p.sentiment : 0,
      priceNormalized: 0,
    }));

    return {
      ...base,
      // Overlay fields that normalizeSentiment doesn't produce
      regime,
      reasons,
      heatLabel,
      components,
      pipelineStatus,
      // Ensure sentimentHistory is the tape history if normalizeSentiment had none
      sentimentHistory: base.sentimentHistory?.length ? base.sentimentHistory : sentimentHistory,
      // Keep normalized true to match useTieredSentiment
      normalized: true,
      schemaVersion: 1,
    };
  }, [rawSentiment, rawMeta, pipelineStatus]);

  // Extract tape-specific heat fields for direct consumption
  const tapeHeat = rawSentiment?.tape_heat ?? null;
  const components = rawSentiment?.components ?? {};
  const reasons = rawSentiment?.reasons ?? [];
  const fearGreed = rawSentiment?.fear_greed ?? null;
  const sentimentHistory = rawSentiment?.sentiment_history ?? [];

  const heat = tapeHeat?.score ?? (data?.overallSentiment != null ? Math.round(data.overallSentiment * 100) : 50);
  const regime = tapeHeat?.regime ?? rawSentiment?.regime ?? "calm";
  const heatLabel = tapeHeat?.label ?? "NEUTRAL";
  const confidence = tapeHeat?.confidence ?? data?.confidence ?? 0;

  const stale = pipelineStatus === "STALE";

  return {
    // Compatible with useTieredSentiment destructuring:
    //   { data: sentimentData, loading, error, refresh, pipelineHealth, tieredData, sources }
    data,
    raw: rawSentiment,
    loading,
    validating: false,
    stale,
    error: null,
    refresh: ctx?.refetch ?? (() => {}),
    sentimentMeta: rawMeta,
    pipelineStatus,
    // useTieredSentiment compatibility
    pipelineHealth: { running: pipelineStatus === "LIVE" },
    tieredData: null,
    sources: [],

    // New market-heat fields
    heat,
    regime,
    heatLabel,
    confidence,
    components,
    reasons,
    fearGreed,
    sentimentHistory,
  };
}

export default useMarketHeat;
