/*
 * Adapter contract: accepts snake_case or camelCase payloads and never throws.
 * Always return arrays instead of null, clamp 0-1 metrics, and keep a copy of
 * the original payload under `raw` for debugging. Any UI component that needs
 * sentiment data must go through this adapter.
 */

const pick = (obj, ...keys) => {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
};

const toNum = (v, d = 0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
};

const clamp01 = (v) => Math.max(0, Math.min(1, toNum(v, 0)));

const arr = (v) => (Array.isArray(v) ? v : []);

export function normalizeSentiment(raw = {}) {
  // accept both snake_case and camelCase
  const overallSentiment = clamp01(
    pick(raw, "overall_sentiment", "overallSentiment")
  );

  const fearGreedIndex = toNum(
    pick(raw, "fear_greed_index", "fearGreedIndex"),
    null
  );

  const socialMetricsRaw = pick(raw, "social_metrics", "socialMetrics") || {};
  const socialMetrics = {
    volumeChange: toNum(pick(socialMetricsRaw, "volume_change", "volumeChange"), 0),
    engagementRate: clamp01(pick(socialMetricsRaw, "engagement_rate", "engagementRate")),
    mentions24h: toNum(pick(socialMetricsRaw, "mentions_24h", "mentions24h"), 0),
  };

  const socialBreakdownRaw =
    pick(raw, "social_breakdown", "socialBreakdown") || {};
  const socialBreakdown = {
    reddit: clamp01(pick(socialBreakdownRaw, "reddit")),
    twitter: clamp01(pick(socialBreakdownRaw, "twitter")),
    telegram: clamp01(pick(socialBreakdownRaw, "telegram")),
    chan: clamp01(pick(socialBreakdownRaw, "chan")),
  };

  const sourceBreakdownRaw =
    pick(raw, "source_breakdown", "sourceBreakdown") || {};
  const sourceBreakdown = {
    tier1: toNum(pick(sourceBreakdownRaw, "tier1"), 0),
    tier2: toNum(pick(sourceBreakdownRaw, "tier2"), 0),
    tier3: toNum(pick(sourceBreakdownRaw, "tier3"), 0),
    fringe: toNum(pick(sourceBreakdownRaw, "fringe"), 0),
  };

  const sentimentHistoryRaw = arr(
    pick(raw, "sentiment_history", "sentimentHistory")
  );
  const sentimentHistory = sentimentHistoryRaw.map((p) => ({
    timestamp: pick(p, "timestamp"),
    sentiment: clamp01(pick(p, "sentiment")),
    priceNormalized: toNum(pick(p, "price_normalized", "priceNormalized"), 0),
  }));

  const socialHistoryRaw = arr(pick(raw, "social_history", "socialHistory"));
  const socialHistory = socialHistoryRaw.map((p) => ({
    timestamp: pick(p, "timestamp"),
    reddit: clamp01(pick(p, "reddit")),
    twitter: clamp01(pick(p, "twitter")),
    telegram: clamp01(pick(p, "telegram")),
    chan: clamp01(pick(p, "chan")),
  }));

  const trendingTopicsRaw = arr(
    pick(raw, "trending_topics", "trendingTopics")
  );
  const trendingTopics = trendingTopicsRaw.map((t) => ({
    tag: pick(t, "tag") || "",
    sentiment: pick(t, "sentiment") || "neutral",
    volume: pick(t, "volume") || "",
  }));

  const divergenceAlertsRaw = arr(
    pick(raw, "divergence_alerts", "divergenceAlerts")
  );
  const divergenceAlerts = divergenceAlertsRaw.map((a) => ({
    type: pick(a, "type") || "info",
    message: pick(a, "message") || "",
  }));

  const updatedAt = pick(raw, "updated_at", "updatedAt", "ts", "timestamp") || null;

  return {
    overallSentiment,
    fearGreedIndex,
    socialMetrics,
    socialBreakdown,
    sourceBreakdown,
    sentimentHistory,
    socialHistory,
    trendingTopics,
    divergenceAlerts,
    updatedAt,
    raw,
  };
}

export default normalizeSentiment;
