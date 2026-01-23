export const EMPTY_SENTIMENT = {
  overall_sentiment: null, // null = missing, not 0 = neutral
  fear_greed_index: null,
  social_metrics: { volume_change: null, engagement_rate: null, mentions_24h: null },
  social_breakdown: { reddit: null, twitter: null, telegram: null, chan: null },
  source_breakdown: { tier1: null, tier2: null, tier3: null, fringe: null },
  sentiment_history: [],
  social_history: [],
  trending_topics: [],
  divergence_alerts: [],
};

export function normalizeSentiment(raw) {
  const base = raw || {};
  const sentiment = {
    ...EMPTY_SENTIMENT,
    ...base,
    social_metrics: {
      ...EMPTY_SENTIMENT.social_metrics,
      ...(base.social_metrics || {}),
    },
    social_breakdown: {
      ...EMPTY_SENTIMENT.social_breakdown,
      ...(base.social_breakdown || {}),
    },
    source_breakdown: {
      ...EMPTY_SENTIMENT.source_breakdown,
      ...(base.source_breakdown || {}),
    },
    sentiment_history: Array.isArray(base.sentiment_history) ? base.sentiment_history : [],
    social_history: Array.isArray(base.social_history) ? base.social_history : [],
    trending_topics: Array.isArray(base.trending_topics) ? base.trending_topics : [],
    divergence_alerts: Array.isArray(base.divergence_alerts) ? base.divergence_alerts : [],
  };

  // Keep null as null - don't forge 0 when data is missing
  sentiment.overall_sentiment =
    base.overall_sentiment == null ? null : Number(base.overall_sentiment);
  sentiment.fear_greed_index =
    base.fear_greed_index == null ? null : Number(base.fear_greed_index);

  return sentiment;
}
