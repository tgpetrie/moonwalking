import { describe, expect, it } from "vitest";

import {
  PRIORITY_HALF_LIFE_MS,
  buildPriorityEvidence,
  buildPriorityItems,
  priorityContributionScore,
} from "./priorityEngine.js";

const NOW = 1_800_000_000_000;

const alert = (overrides = {}) => ({
  id: "alert-1",
  symbol: "BTC-USD",
  type_key: "moonshot",
  severity: "high",
  ts_ms: NOW - 30_000,
  evidence: {
    pct_1m: 2,
    volume_change_1h_pct: 50,
    streak: 3,
  },
  ...overrides,
});

const boards = {
  gainers1m: [{ symbol: "BTC-USD", rank: 2 }],
  gainers3m: [{ symbol: "BTC-USD", rank: 3 }],
  losers3m: [],
};

const deterministicInput = {
  alerts: [
    alert(),
    alert({
      id: "alert-2",
      type_key: "breakout",
      severity: "medium",
      ts_ms: NOW - 60_000,
      evidence: {
        pct_1m: 1,
        volume_change_1h_pct: 20,
        streak: 2,
      },
    }),
  ],
  ...boards,
  marketPressure: { breadth_up: 0.7, components: { breadth: 0.7 } },
  nowMs: NOW,
};

describe("shared priority engine", () => {
  it("preserves the existing deterministic contribution formula", () => {
    const contribution = priorityContributionScore(alert(), NOW);

    expect(contribution.baseScore).toBe(58);
    expect(contribution.decay).toBeCloseTo(Math.exp(-30_000 / PRIORITY_HALF_LIFE_MS));
    expect(contribution.weighted).toBeCloseTo(
      58 * Math.exp(-30_000 / PRIORITY_HALF_LIFE_MS)
    );
    expect(contribution.isFresh).toBe(true);
  });

  it("gives both consumers one state, score, rank trend, and semantic summary", () => {
    const alertsSurface = buildPriorityItems(deterministicInput)[0];
    const popupSurface = buildPriorityItems(deterministicInput)[0];

    expect(alertsSurface).toMatchObject({
      symbol: "BTC",
      bucket: "bullish",
      score: 99,
      stateLabel: "Dominant",
      rankTrend: "flat-strong",
      rankSummary: "rank held 2-3",
      confirms: 2,
      freshConfirms: 2,
    });
    expect(popupSurface).toMatchObject({
      score: alertsSurface.score,
      stateLabel: alertsSurface.stateLabel,
      rankTrend: alertsSurface.rankTrend,
      rankSummary: alertsSurface.rankSummary,
      scoreRaw: alertsSurface.scoreRaw,
    });
  });

  it("allows a surface to limit rendering without changing the computed item", () => {
    const items = buildPriorityItems({
      ...deterministicInput,
      limit: 1,
    });

    expect(items).toHaveLength(1);
    expect(items[0].score).toBe(99);
  });

  it("keeps current Reversal Risk canonical when stronger bullish evidence competes", () => {
    const items = buildPriorityItems({
      ...deterministicInput,
      alerts: [
        ...deterministicInput.alerts,
        alert({
          id: "current-risk",
          type_key: "social_divergence",
          ts_ms: NOW - 20_000,
          evidence: {
            pct_3m: 2,
            volume_change_1h_pct: -20,
          },
        }),
      ],
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      symbol: "BTC",
      bucket: "divergence",
      stateLabel: "Reversal Risk",
    });
  });

  it("lets current bullish evidence supersede stale Reversal Risk", () => {
    const items = buildPriorityItems({
      ...deterministicInput,
      alerts: [
        ...deterministicInput.alerts,
        alert({
          id: "stale-risk",
          type_key: "social_divergence",
          ts_ms: NOW - 4 * 60_000,
          evidence: {
            pct_3m: 2,
            volume_change_1h_pct: -20,
          },
        }),
      ],
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      symbol: "BTC",
      bucket: "bullish",
      stateLabel: "Dominant",
    });
  });

  it("returns Fragile entries instead of dropping the coin", () => {
    const items = buildPriorityItems({
      alerts: [
        alert({
          id: "fragile",
          type_key: "breakout",
          evidence: { pct_1m: 4 },
        }),
      ],
      nowMs: NOW,
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      symbol: "BTC",
      stateLabel: "Fragile",
    });
    expect(items[0].score).toBeGreaterThanOrEqual(40);
    expect(items[0].score).toBeLessThan(55);
  });

  it("deduplicates active and recent alerts and excludes expired evidence", () => {
    const live = alert({ expires_at: new Date(NOW + 60_000).toISOString() });
    const expired = alert({
      id: "expired",
      symbol: "ETH-USD",
      expires_at: new Date(NOW - 1).toISOString(),
    });

    const evidence = buildPriorityEvidence({
      activeAlerts: [live, expired],
      recentAlerts: [live],
      nowMs: NOW,
    });

    expect(evidence).toEqual([live]);
    expect(buildPriorityItems({ alerts: evidence, nowMs: NOW })).toHaveLength(1);
  });

  it("keeps semantic output invariant when display-only subsets change", () => {
    const evidence = buildPriorityEvidence({
      activeAlerts: deterministicInput.alerts.map((item) => ({
        ...item,
        expires_at: new Date(NOW + 60_000).toISOString(),
      })),
      recentAlerts: [],
      nowMs: NOW,
    });
    const semanticInput = { ...deterministicInput, alerts: evidence };
    const baseline = buildPriorityItems(semanticInput)[0];

    const severityVisible = evidence.filter((item) => item.severity === "high");
    const typeVisible = evidence.filter((item) => item.type_key === "breakout");
    const coinVisible = evidence.filter((item) => item.symbol === "ETH-USD");

    expect(severityVisible).toHaveLength(1);
    expect(typeVisible).toHaveLength(1);
    expect(coinVisible).toHaveLength(0);
    expect(buildPriorityItems(semanticInput)[0]).toMatchObject({
      score: baseline.score,
      stateLabel: baseline.stateLabel,
      rankTrend: baseline.rankTrend,
      rankSummary: baseline.rankSummary,
    });
  });
});
