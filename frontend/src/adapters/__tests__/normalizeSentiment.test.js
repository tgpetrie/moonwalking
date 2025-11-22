import assert from "node:assert";
import test from "node:test";
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
  assert.strictEqual(norm.overallSentiment, 0.42);
  assert.strictEqual(norm.fearGreedIndex, 68);
  assert.strictEqual(norm.socialMetrics.volumeChange, 5.5);
  assert.ok(Array.isArray(norm.sentimentHistory));
  assert.ok(Array.isArray(norm.trendingTopics));
  assert.strictEqual(norm.socialBreakdown.reddit, 0.8);
  assert.strictEqual(norm.socialBreakdown.twitter, 0);
});

test("normalizeSentiment tolerates nullish input", () => {
  const norm = normalizeSentiment(null);
  assert.deepStrictEqual(norm.sentimentHistory, []);
  assert.deepStrictEqual(norm.socialHistory, []);
  assert.deepStrictEqual(norm.trendingTopics, []);
  assert.strictEqual(norm.overallSentiment, 0);
});
