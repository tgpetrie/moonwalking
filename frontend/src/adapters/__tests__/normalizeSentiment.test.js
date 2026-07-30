import { expect, test } from "vitest";
import normalizeSentiment from "../../adapters/normalizeSentiment.js";

test("normalizeSentiment fills defaults and coerces numbers", () => {
  const raw = {
    overall_sentiment: "0.42",
    fear_greed_index: "68",
    social_metrics: { volume_change: "5.5" },
    social_breakdown: { reddit: 0.8 },
    sentiment_history: [{ score: "0.5", ts: 1 }],
    trending_topics: ["btc"],
  };
  const norm = normalizeSentiment(raw);
  expect(norm.overallSentiment).toBe(0.42);
  expect(norm.fearGreedIndex).toBe(68);
  expect(norm.socialMetrics.volumeChange).toBe(5.5);
  expect(Array.isArray(norm.sentimentHistory)).toBe(true);
  expect(Array.isArray(norm.trendingTopics)).toBe(true);
  expect(norm.socialBreakdown.reddit).toBe(0.8);
  expect(norm.socialBreakdown.twitter).toBeNull();
});

test("normalizeSentiment tolerates nullish input", () => {
  const norm = normalizeSentiment(null);
  expect(norm.sentimentHistory).toEqual([]);
  expect(norm.socialHistory).toEqual([]);
  expect(norm.trendingTopics).toEqual([]);
  expect(norm.overallSentiment).toBeNull();
  expect(norm.socialMetrics.volumeChange).toBeNull();
  expect(norm.socialBreakdown.reddit).toBeNull();
  expect(norm.pipelineStatus).toBe("OFFLINE");
});

test("normalizeSentiment surfaces market positioning from social_metrics", () => {
  const norm = normalizeSentiment({
    social_metrics: {
      derivatives_positioning: {
        live_exchanges: ["okx"],
        blocked_exchanges: ["binance", "bybit"],
        failed_exchanges: [],
        configured_exchanges: ["binance", "bybit", "okx"],
        stale: false,
        updated_at: "2026-07-22T00:00:00Z",
        summary: {
          funding_bias: "neutral",
          live_exchange_count: 1,
          configured_exchange_count: 3,
          coverage_ratio: 0.333,
          confidence_penalty: 0.667,
          average_funding_rate: 0.00001,
        },
      },
    },
  });
  const mp = norm.marketPositioning;
  expect(mp.available).toBe(true);
  expect(mp.status).toBe("LIVE");
  expect(mp.liveExchanges).toEqual(["okx"]);
  expect(mp.blockedExchanges).toEqual(["binance", "bybit"]);
  expect(mp.fundingBias).toBe("neutral");
  expect(mp.coverageLive).toBe(1);
  expect(mp.coverageTotal).toBe(3);
});

test("normalizeSentiment marks positioning stale when the payload is stale", () => {
  const norm = normalizeSentiment({
    social_metrics: {
      derivatives_positioning: {
        live_exchanges: ["okx"],
        configured_exchanges: ["binance", "bybit", "okx"],
        stale: true,
        summary: { funding_bias: "longs_pay" },
      },
    },
  });
  expect(norm.marketPositioning.status).toBe("STALE");
  expect(norm.marketPositioning.available).toBe(true);
});

test("normalizeSentiment never reports positioning as live without live exchanges", () => {
  // No live exchanges at all -> must be UNAVAILABLE, never LIVE.
  const norm = normalizeSentiment({
    social_metrics: {
      derivatives_positioning: {
        live_exchanges: [],
        blocked_exchanges: ["binance", "bybit", "okx"],
        configured_exchanges: ["binance", "bybit", "okx"],
        summary: { funding_bias: "unknown" },
      },
    },
  });
  expect(norm.marketPositioning.available).toBe(false);
  expect(norm.marketPositioning.status).toBe("UNAVAILABLE");

  // Missing block entirely -> also UNAVAILABLE.
  const empty = normalizeSentiment(null);
  expect(empty.marketPositioning.available).toBe(false);
  expect(empty.marketPositioning.status).toBe("UNAVAILABLE");
});

test("normalizeSentiment reports stale and offline truthfully", () => {
  const stale = normalizeSentiment({
    overall_sentiment: 0.28,
    sentiment_meta: {
      ok: true,
      pipelineRunning: true,
      staleSeconds: 301,
      dataStatus: "stale",
    },
  });
  expect(stale.pipelineStatus).toBe("STALE");

  const offline = normalizeSentiment({
    sentiment_meta: {
      ok: false,
      pipelineRunning: true,
      staleSeconds: 0,
      dataStatus: "offline",
    },
  });
  expect(offline.pipelineStatus).toBe("OFFLINE");
});
