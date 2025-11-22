export const EMPTY_SENTIMENT = {
  overall_sentiment: 0,
  fear_greed_index: null,
  social_metrics: { volume_change: 0, engagement_rate: 0, mentions_24h: 0 },
  social_breakdown: { reddit: 0, twitter: 0, telegram: 0, chan: 0 },
  source_breakdown: { tier1: 0, tier2: 0, tier3: 0, fringe: 0 },
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

  sentiment.overall_sentiment =
    base.overall_sentiment == null ? 0 : Number(base.overall_sentiment);
  sentiment.fear_greed_index =
    base.fear_greed_index == null ? null : Number(base.fear_greed_index);

  return sentiment;
}
