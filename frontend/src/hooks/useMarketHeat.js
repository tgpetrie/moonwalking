import { useMemo } from "react";
import { useData } from "../context/DataContext";
import { normalizeSentiment } from "../adapters/normalizeSentiment";
import { getMarketPressure } from "../utils/marketPressure";

const clamp01 = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
};

const labelToRegime = (label) => {
  const l = String(label || "").trim().toLowerCase();
  if (!l) return "neutral";
  if (l.includes("euphoria") || l.includes("risk-on")) return "risk_on";
  if (l.includes("fear") || l.includes("cautious")) return "risk_off";
  return "neutral";
};

/**
 * useMarketHeat — drop-in replacement for useSentimentLatest / useTieredSentiment.
 *
 * Canonical source is /data.market_pressure with a legacy fallback to older
 * sentiment payload fields so existing UI paths never go blank.
 */
export function useMarketHeat() {
  const ctx = useData();
  const rawSentiment = ctx?.sentiment ?? null;
  const rawMeta = ctx?.sentimentMeta ?? null;
  const loading = ctx?.loading ?? false;
  const connectionStatus = ctx?.connectionStatus ?? "DOWN";
  const marketPressureInput =
    ctx?.marketPressure ??
    ctx?.data?.market_pressure ??
    ctx?.alertsMeta?.market_pressure ??
    rawSentiment?.market_pressure ??
    null;
  const hasMarketPressureSource = Boolean(marketPressureInput && typeof marketPressureInput === "object");

  const marketPressure = useMemo(
    () =>
      getMarketPressure({
        market_pressure: marketPressureInput,
      }),
    [marketPressureInput],
  );

  // Derive stale / pipelineStatus from connection + meta
  const pipelineStatus = useMemo(() => {
    if (connectionStatus === "DOWN") return "OFFLINE";
    if (!rawMeta) return rawSentiment || hasMarketPressureSource ? "STALE" : "OFFLINE";
    if (rawMeta.ok && rawMeta.pipelineRunning) return "LIVE";
    if (rawSentiment || hasMarketPressureSource) return "STALE";
    return "OFFLINE";
  }, [connectionStatus, rawMeta, rawSentiment, hasMarketPressureSource]);

  const data = useMemo(() => {
    const base = rawSentiment
      ? normalizeSentiment({ ...rawSentiment, sentiment_meta: rawMeta })
      : normalizeSentiment(null);

    const tapeHeat = rawSentiment?.tape_heat ?? null;
    const pressureComponents = marketPressure?.components ?? {};
    const legacyComponents = rawSentiment?.components ?? {};

    const totalSymbols = Number.isFinite(marketPressure?.symbol_count)
      ? Number(marketPressure.symbol_count)
      : Number.isFinite(legacyComponents?.total_symbols)
        ? Number(legacyComponents.total_symbols)
        : 0;

    const breadth01 = clamp01(pressureComponents.breadth ?? legacyComponents.breadth);
    const green3m = totalSymbols > 0 ? Math.round(totalSymbols * breadth01) : (legacyComponents.green_3m ?? 0);
    const red3m = totalSymbols > 0 ? Math.max(0, totalSymbols - green3m) : (legacyComponents.red_3m ?? 0);

    const momentumAlignment =
      Number.isFinite(legacyComponents.momentum_alignment)
        ? Number(legacyComponents.momentum_alignment)
        : (breadth01 - 0.5) * 2;

    const volatility =
      Number.isFinite(legacyComponents.volatility)
        ? Number(legacyComponents.volatility)
        : clamp01(pressureComponents.vol_regime ?? 0);

    const mergedComponents = {
      ...legacyComponents,
      breadth: breadth01,
      impulse_density: clamp01(pressureComponents.impulse_density ?? legacyComponents.impulse_density ?? 0),
      volume_anomaly: clamp01(pressureComponents.volume_anomaly ?? legacyComponents.volume_anomaly ?? 0),
      vol_regime: clamp01(pressureComponents.vol_regime ?? legacyComponents.vol_regime ?? volatility),
      persistence: clamp01(pressureComponents.persistence ?? legacyComponents.persistence ?? 0),
      breadth_3m: Number.isFinite(legacyComponents.breadth_3m)
        ? Number(legacyComponents.breadth_3m)
        : breadth01 * 100,
      breadth_1m: Number.isFinite(legacyComponents.breadth_1m)
        ? Number(legacyComponents.breadth_1m)
        : breadth01 * 100,
      green_3m: green3m,
      red_3m: red3m,
      total_symbols: totalSymbols,
      momentum_alignment: momentumAlignment,
      volatility,
      avg_return_1m: Number.isFinite(legacyComponents.avg_return_1m)
        ? Number(legacyComponents.avg_return_1m)
        : clamp01(pressureComponents.impulse_density ?? 0),
      avg_return_3m: Number.isFinite(legacyComponents.avg_return_3m)
        ? Number(legacyComponents.avg_return_3m)
        : (breadth01 - 0.5),
    };

    const score01 = clamp01(
      (hasMarketPressureSource ? marketPressure?.score01 : null) ??
      tapeHeat?.score ??
      base.overallSentiment,
    );

    const regime = tapeHeat?.regime ?? rawSentiment?.regime ?? labelToRegime(marketPressure?.label);
    const heatLabel = marketPressure?.label ?? tapeHeat?.label ?? "Neutral";

    const reasons = Array.isArray(rawSentiment?.reasons) && rawSentiment.reasons.length
      ? rawSentiment.reasons
      : [
          `Breadth ${(breadth01 * 100).toFixed(0)}%`,
          `Impulse density ${(clamp01(pressureComponents.impulse_density) * 100).toFixed(0)}%`,
          `Volume anomaly ${(clamp01(pressureComponents.volume_anomaly) * 100).toFixed(0)}%`,
        ];

    const sentimentHistory = (rawSentiment?.sentiment_history ?? []).map((p) => ({
      timestamp: p?.timestamp,
      sentiment: typeof p?.sentiment === "number" ? p.sentiment : 0,
      priceNormalized: 0,
    }));

    return {
      ...base,
      overallSentiment: score01,
      regime,
      reasons,
      heatLabel,
      components: mergedComponents,
      pipelineStatus,
      sentimentHistory: base.sentimentHistory?.length ? base.sentimentHistory : sentimentHistory,
      marketPressure,
      normalized: true,
      schemaVersion: 2,
    };
  }, [rawSentiment, rawMeta, pipelineStatus, marketPressure, hasMarketPressureSource]);

  const tapeHeat = rawSentiment?.tape_heat ?? null;
  const reasons = data?.reasons ?? [];
  const fearGreed = rawSentiment?.fear_greed ?? null;
  const sentimentHistory = rawSentiment?.sentiment_history ?? data?.sentimentHistory ?? [];

  const heat = hasMarketPressureSource && Number.isFinite(marketPressure?.index)
    ? Number(marketPressure.index)
    : (data?.overallSentiment != null ? Math.round(data.overallSentiment * 100) : 50);

  const regime = tapeHeat?.regime ?? rawSentiment?.regime ?? labelToRegime(marketPressure?.label);
  const heatLabel = marketPressure?.label ?? tapeHeat?.label ?? data?.heatLabel ?? "Neutral";
  const confidence = tapeHeat?.confidence ?? data?.confidence ?? clamp01(marketPressure?.components?.persistence ?? 0);

  const stale = pipelineStatus === "STALE";

  return {
    data,
    raw: rawSentiment,
    loading,
    validating: false,
    stale,
    error: null,
    refresh: ctx?.refetch ?? (() => {}),
    sentimentMeta: rawMeta,
    pipelineStatus,
    pipelineHealth: { running: pipelineStatus === "LIVE" },
    tieredData: null,
    sources: [],

    heat,
    regime,
    heatLabel,
    confidence,
    components: data?.components ?? {},
    reasons,
    fearGreed,
    sentimentHistory,
    marketPressure,
  };
}

export default useMarketHeat;
