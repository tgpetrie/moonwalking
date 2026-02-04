import { useMemo } from "react";
import { useData } from "../context/DataContext";
import normalizeSentiment from "../adapters/normalizeSentiment";

export function useMarketHeat() {
  const ctx = useData();
  const sentiment = ctx?.sentiment ?? null;
  const sentimentMeta = ctx?.sentimentMeta ?? null;
  const loading = Boolean(ctx?.loading) && !sentiment;
  const error = ctx?.error ?? null;
  const refresh = ctx?.refetch ?? (() => {});

  const data = useMemo(() => {
    const base = sentiment && typeof sentiment === "object" ? sentiment : {};
    const merged = {
      ...base,
      sentiment_meta: sentimentMeta ?? base.sentiment_meta ?? base.sentimentMeta ?? null,
    };
    const norm = normalizeSentiment(merged);
    const rawOverall = base?.overall_sentiment ?? base?.overallSentiment ?? null;
    if (rawOverall == null) {
      norm.overallSentiment = null;
    }

    return {
      ...norm,
      regime: base?.regime ?? null,
      reasons: Array.isArray(base?.reasons) ? base.reasons : [],
      tapeHeat: base?.tape_heat ?? base?.tapeHeat ?? null,
      components: base?.components ?? null,
    };
  }, [sentiment, sentimentMeta]);

  const pipelineHealth = sentimentMeta ?? data?.sentimentMeta ?? null;

  return {
    data,
    loading,
    error,
    refresh,
    pipelineHealth,
  };
}

export default useMarketHeat;
