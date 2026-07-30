import { describe, expect, it } from "vitest";

import {
  buildEventView,
  buildFeedView,
  describeReason,
  formatPct,
  formatUsd,
} from "../intelligenceFeedAdapter.js";

const backendEvent = {
  event_id: "event-1",
  event_type: "PORTFOLIO_CHANGE_INTELLIGENCE",
  status: "detected",
  observed_at: "2026-07-26T00:00:00Z",
  headline: "Portfolio up 19.05% over the 12 hours — driven by SOL",
  what_changed: {
    reasons: [
      {
        type: "portfolio_move",
        magnitude_pct: 19.0476,
        threshold_pct: 5,
        direction: "up",
      },
      {
        type: "asset_contribution",
        asset_symbol: "SOL",
        magnitude_pct: 19.0476,
        threshold_pct: 3,
        direction: "up",
      },
    ],
    total_change_pct: 19.0476,
    total_change_usd: 40.0,
  },
  affected_assets: ["SOL"],
  portfolio_impact: {
    previous_total_usd: 210.0,
    current_total_usd: 250.0,
    change_usd: 40.0,
    change_pct: 19.0476,
  },
  supporting_metrics: {
    biggest_movers: [
      { asset_symbol: "SOL", value_delta_usd: 40.0, contribution_pct: 19.0476 },
    ],
    allocation_changes: [
      { asset_symbol: "SOL", from_pct: 47.6, to_pct: 56.0, delta_pct: 8.4 },
    ],
  },
  confidence: { level: "deterministic", source: "portfolio_change_intelligence" },
  evidence: { packet_id: "portfolio-change-abc", available: true },
  explanation: null,
};

describe("formatters", () => {
  it("signs percentages and dollars", () => {
    expect(formatPct(19.0476)).toBe("+19.05%");
    expect(formatPct(-6.5)).toBe("-6.50%");
    expect(formatUsd(40)).toBe("+$40.00");
    expect(formatUsd(-40)).toBe("-$40.00");
  });

  it("returns null for unknown values rather than a confident zero", () => {
    expect(formatPct(null)).toBeNull();
    expect(formatPct(undefined)).toBeNull();
    expect(formatUsd(Number.NaN)).toBeNull();
  });
});

describe("describeReason", () => {
  it("describes both trigger types in the engine's own terms", () => {
    expect(describeReason(backendEvent.what_changed.reasons[0])).toContain(
      "Total portfolio moved 19.05% up"
    );
    expect(describeReason(backendEvent.what_changed.reasons[1])).toContain(
      "SOL moved 19.05% of your portfolio value up"
    );
  });

  it("ignores unknown reason shapes", () => {
    expect(describeReason({ type: "mystery" })).toBeNull();
    expect(describeReason(null)).toBeNull();
  });
});

describe("buildEventView", () => {
  it("maps the backend contract to the view model", () => {
    const view = buildEventView(backendEvent);
    expect(view.id).toBe("event-1");
    expect(view.affectedAssets).toEqual(["SOL"]);
    expect(view.impact.changePctLabel).toBe("+19.05%");
    expect(view.impact.changeUsdLabel).toBe("+$40.00");
    expect(view.impact.direction).toBe("up");
    expect(view.impact.previousTotalLabel).toBe("+$210.00");
    expect(view.movers[0]).toMatchObject({ symbol: "SOL", valueDeltaLabel: "+$40.00" });
    expect(view.allocationChanges[0].deltaLabel).toBe("+8.40%");
    expect(view.confidence.label).toBe("Measured");
    expect(view.evidenceAvailable).toBe(true);
    expect(view.explanation).toBeNull();
  });

  it("marks a downward move and flags missing evidence", () => {
    const view = buildEventView({
      ...backendEvent,
      portfolio_impact: { ...backendEvent.portfolio_impact, change_pct: -6.5 },
      confidence: { level: "unknown" },
      evidence: { available: false },
    });
    expect(view.impact.direction).toBe("down");
    expect(view.confidence.label).toBe("Unverified");
    expect(view.evidenceAvailable).toBe(false);
  });

  it("keeps unknown impact distinct from zero", () => {
    const view = buildEventView({
      ...backendEvent,
      what_changed: { reasons: [] },
      portfolio_impact: {},
    });
    expect(view.impact.changePctLabel).toBeNull();
    expect(view.impact.direction).toBe("unknown");
  });

  it("rejects non-objects", () => {
    expect(buildEventView(null)).toBeNull();
  });
});

describe("buildFeedView", () => {
  it("wraps events and reports emptiness", () => {
    expect(buildFeedView({ events: [backendEvent] })).toMatchObject({
      count: 1,
      isEmpty: false,
    });
    expect(buildFeedView({ events: [] }).isEmpty).toBe(true);
    expect(buildFeedView(null).isEmpty).toBe(true);
  });
});
