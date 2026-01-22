/*
 * Adapter contract: accepts snake_case or camelCase payloads and never throws.
 * Always return arrays instead of null, clamp 0-1 metrics, and keep a copy of
 * the original payload under `raw` for debugging. Any UI component that needs
 * sentiment data must go through this adapter.
 *
 * Also extracts sentiment_meta and computes pipelineStatus: "LIVE" | "STALE" | "OFFLINE"
 */

const STALE_THRESHOLD_SECONDS = 120; // Data older than 2min is considered stale

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

/**
 * Compute pipeline status from sentiment_meta
 * @param {object|null} meta - sentiment_meta from backend
 * @param {boolean} hasData - whether we have any sentiment data
 * @returns {"LIVE" | "STALE" | "OFFLINE"}
 */
const computePipelineStatus = (meta, hasData) => {
  if (!meta) return hasData ? "STALE" : "OFFLINE";
  if (meta.ok && meta.pipelineRunning) return "LIVE";
  if (meta.pipelineRunning || hasData) {
    const staleSeconds = meta.staleSeconds ?? Infinity;
    return staleSeconds < STALE_THRESHOLD_SECONDS ? "LIVE" : "STALE";
  }
  return "OFFLINE";
};

export function normalizeSentiment(raw = {}) {
  // accept both snake_case and camelCase
  const overallSentiment = clamp01(
    pick(raw, "overall_sentiment", "overallSentiment")
  );

  const fgBlock = pick(raw, "fear_greed", "fearGreed") || {};
  const fgValue = toNum(pick(fgBlock, "value", "index", "score", "fear_greed_index"), null);
  const fearGreedIndex = fgValue !== null
    ? fgValue
    : toNum(pick(raw, "fear_greed_index", "fearGreedIndex"), null);
  const fearGreedLabel =
    pick(fgBlock, "label", "classification", "status", "value_classification") ||
    pick(raw, "fear_greed_label", "fearGreedLabel") ||
    null;
  const fearGreedUpdatedAt =
    pick(fgBlock, "updated_at", "timestamp", "ts") ||
    pick(raw, "fear_greed_timestamp", "fearGreedTimestamp") ||
    pick(raw, "updated_at", "updatedAt") ||
    null;
  const fearGreedStatus =
    fearGreedIndex !== null
      ? (fgBlock?.stale ? "STALE" : "LIVE")
      : "UNAVAILABLE";

  const marketPulseRaw = pick(raw, "market_pulse", "marketPulse", "market") || {};
  const marketPulse = {
    totalMarketCap: toNum(pick(marketPulseRaw, "total_market_cap_usd", "market_cap_usd", "total_market_cap"), null),
    totalVolume: toNum(pick(marketPulseRaw, "total_volume_usd", "volume_usd", "total_volume"), null),
    btcDominance: toNum(pick(marketPulseRaw, "btc_dominance", "btc_dominance_pct", "btc_dominance_usd"), null),
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
  const marketPulseStatus =
    marketPulse.totalMarketCap !== null || marketPulse.totalVolume !== null
      ? marketPulse.stale
        ? "STALE"
        : "LIVE"
      : "UNAVAILABLE";

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
    stocktwits: clamp01(pick(socialBreakdownRaw, "stocktwits")),
    chan: clamp01(pick(socialBreakdownRaw, "chan")),
    custom: clamp01(pick(socialBreakdownRaw, "custom")),
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
    custom: clamp01(pick(p, "custom")),
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

  // Tiered sentiment data (optional, from sentiment pipeline)
  const tierScoresRaw = pick(raw, "tier_scores", "tierScores") || {};
  const tierScores = tierScoresRaw ? {
    tier1: clamp01(pick(tierScoresRaw, "tier1")),
    tier2: clamp01(pick(tierScoresRaw, "tier2")),
    tier3: clamp01(pick(tierScoresRaw, "tier3")),
    fringe: clamp01(pick(tierScoresRaw, "fringe")),
  } : null;

  const hasTieredData = pick(raw, "has_tiered_data", "hasTieredData") || false;
  const totalDataPoints = toNum(pick(raw, "total_data_points", "totalDataPoints"), 0);
  const confidence = clamp01(pick(raw, "confidence"));
  const pipelineTimestamp = pick(raw, "pipeline_timestamp", "pipelineTimestamp") || null;

  const updatedAt = pick(raw, "updated_at", "updatedAt", "ts", "timestamp") || null;

  // Extract sentiment_meta from backend response
  const sentimentMeta = pick(raw, "sentiment_meta", "sentimentMeta") || null;
  const hasData = overallSentiment > 0 || fearGreedIndex !== null;
  const pipelineStatus = computePipelineStatus(sentimentMeta, hasData);

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
    // Tiered data fields
    tierScores,
    hasTieredData,
    totalDataPoints,
    confidence,
    pipelineTimestamp,
    updatedAt,
    fearGreedLabel,
    fearGreedUpdatedAt,
    fearGreedStatus,
    marketPulse,
    marketPulseStatus,
    // Pipeline truth-state contract
    sentimentMeta,
    pipelineStatus, // "LIVE" | "STALE" | "OFFLINE"
    raw,
  };
}

export default normalizeSentiment;
