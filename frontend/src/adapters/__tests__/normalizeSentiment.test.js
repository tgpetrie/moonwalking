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
