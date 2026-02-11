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
  expect(norm.socialBreakdown.twitter).toBe(0);
});

test("normalizeSentiment tolerates nullish input", () => {
  const norm = normalizeSentiment(null);
  expect(norm.sentimentHistory).toEqual([]);
  expect(norm.socialHistory).toEqual([]);
  expect(norm.trendingTopics).toEqual([]);
  expect(norm.overallSentiment).toBe(0);
});
