import { describe, expect, it } from "vitest";
import {
  buildAnalysisView,
  normalizeBackendSnapshot,
  validatePositionDraft,
  fmtPct,
  relativeTime,
} from "../askBhabitAdapter.js";
import {
  RICH_ANALYSIS,
  SPARSE_ANALYSIS,
  NO_PRIOR_ANALYSIS,
  PROVIDER_ERROR_ENVELOPE,
  MODEL_FAILURE_ENVELOPE,
} from "../fixtures/analyses.js";
import { ANALYSIS_STATE, MISSING_STATUS } from "../askBhabitContract.js";

describe("buildAnalysisView — classification", () => {
  it("marks provider and model failures without rendering an answer", () => {
    expect(buildAnalysisView(PROVIDER_ERROR_ENVELOPE).state).toBe(ANALYSIS_STATE.PROVIDER_ERROR);
    expect(buildAnalysisView(MODEL_FAILURE_ENVELOPE).state).toBe(ANALYSIS_STATE.MODEL_FAILURE);
    expect(buildAnalysisView(null).state).toBe(ANALYSIS_STATE.MODEL_FAILURE);
    expect(buildAnalysisView({ error: "weird" }).state).toBe(ANALYSIS_STATE.MODEL_FAILURE);
  });

  it("normalizes a rich payload into a ready view", () => {
    const { state, view } = buildAnalysisView(RICH_ANALYSIS);
    expect(state).toBe(ANALYSIS_STATE.READY);
    expect(view.directRead.headline).toMatch(/thesis intact/i);
    expect(view.confidence.label).toBe("High");
    expect(view.confidence.reasons.length).toBeGreaterThan(0);
    expect(view.thesisCheck.label).toBe("Strengthened");
    expect(view.position.display.unrealizedPnlPct).toBe("+19.26%");
    expect(view.position.pnlTone).toBe("positive");
  });
});

describe("What Changed distinctions", () => {
  it("labels a market-structure change and lists items with a prior snapshot", () => {
    const { view } = buildAnalysisView(RICH_ANALYSIS);
    expect(view.whatChanged.label).toBe("Market structure changed");
    expect(view.whatChanged.hasPrior).toBe(true);
    expect(view.whatChanged.items.length).toBe(2);
  });

  it("labels price-only changes distinctly from structure", () => {
    const { view } = buildAnalysisView(SPARSE_ANALYSIS);
    expect(view.whatChanged.label).toBe("Only price moved");
  });

  it("handles no prior snapshot (insufficient history)", () => {
    const { view } = buildAnalysisView(NO_PRIOR_ANALYSIS);
    expect(view.whatChanged.hasPrior).toBe(false);
    expect(view.whatChanged.label).toBe("Not enough history");
    expect(view.thesisCheck).toBeNull();
  });
});

describe("Missing data — never neutral", () => {
  it("preserves each distinct missing status with a non-muted tone where appropriate", () => {
    const { view } = buildAnalysisView(SPARSE_ANALYSIS);
    const byStatus = Object.fromEntries(view.missing.map((m) => [m.status, m]));
    expect(byStatus[MISSING_STATUS.UNSUPPORTED].label).toBe("Unsupported");
    expect(byStatus[MISSING_STATUS.NOT_CONFIGURED].label).toBe("Not configured");
    expect(byStatus[MISSING_STATUS.PROVIDER_ERROR].tone).toBe("danger");
    expect(byStatus[MISSING_STATUS.STALE].tone).toBe("warning");
    expect(byStatus[MISSING_STATUS.CONFLICTING].tone).toBe("danger");
  });

  it("degrades an unknown missing status to a safe default rather than blank", () => {
    const { view } = buildAnalysisView({ ...RICH_ANALYSIS, missing: [{ metric: "X", status: "bogus" }] });
    expect(view.missing[0].label).toBe("Unavailable");
  });
});

describe("Confidence", () => {
  it("shows insufficient evidence as its own state with reasons, not a score", () => {
    const { view } = buildAnalysisView(SPARSE_ANALYSIS);
    expect(view.confidence.label).toBe("Insufficient evidence");
    expect(view.confidence.reasons.length).toBeGreaterThan(0);
    expect(view.confidence).not.toHaveProperty("score");
  });
});

describe("validatePositionDraft", () => {
  it("requires asset, quantity and a basis", () => {
    const r = validatePositionDraft({});
    expect(r.valid).toBe(false);
    expect(r.errors.asset).toBeTruthy();
    expect(r.errors.quantity).toBeTruthy();
    expect(r.errors.basis).toBeTruthy();
  });

  it("derives cost basis from entry price and quantity", () => {
    const r = validatePositionDraft({ asset: "sol", quantity: "10", entryPrice: "100" });
    expect(r.valid).toBe(true);
    expect(r.normalized.asset).toBe("SOL");
    expect(r.normalized.costBasis).toBe(1000);
  });

  it("derives entry price from cost basis and quantity", () => {
    const r = validatePositionDraft({ asset: "BTC", quantity: "2", costBasis: "120000" });
    expect(r.valid).toBe(true);
    expect(r.normalized.entryPrice).toBe(60000);
  });

  it("rejects a non-positive quantity", () => {
    expect(validatePositionDraft({ asset: "SOL", quantity: "0", entryPrice: "1" }).valid).toBe(false);
  });
});

describe("formatting helpers", () => {
  it("formats percentages with sign", () => {
    expect(fmtPct(19.26)).toBe("+19.26%");
    expect(fmtPct(-3)).toBe("-3.00%");
    expect(fmtPct(null)).toBe("—");
  });

  it("formats relative time", () => {
    const now = Date.parse("2026-07-24T14:05:00Z");
    expect(relativeTime("2026-07-24T14:00:00Z", now)).toBe("5m ago");
    expect(relativeTime(null, now)).toBe("unknown time");
  });
});

describe("backend snapshot normalization", () => {
  const backendSnapshot = {
    snapshot_id: "snapshot-1",
    created_at: "2026-07-24T14:05:00Z",
    evidence_packet: {
      retrieved_at: "2026-07-24T14:04:00Z",
      asset_symbol: "SOL",
      public_market_evidence: {
        asset_identity: {
          status: "available",
          value: { symbol: "SOL", name: "Solana", provider_ids: { hyperliquid: "SOL" } },
          source: "ask_bhabit_asset_registry",
          retrieved_at: "2026-07-24T14:04:00Z",
          freshness: "fresh",
        },
        price: {
          status: "available",
          value: 141.2,
          source: "fixture_price",
          retrieved_at: "2026-07-24T14:04:00Z",
          freshness: "fresh",
        },
        movement: {
          short_window: {
            status: "stale",
            value: null,
            source: "fixture_1h",
            retrieved_at: "2026-07-24T13:04:00Z",
            freshness: "stale",
            missing_data_reason: "old candle",
          },
        },
        derivatives: {
          funding: {
            status: "not_configured",
            value: null,
            source: "derivatives_provider",
            retrieved_at: null,
            missing_data_reason: "provider not configured",
          },
          open_interest: {
            status: "provider_error",
            value: null,
            source: "hyperliquid",
            retrieved_at: "2026-07-24T14:03:00Z",
            provider_error: "timeout",
          },
          liquidations: {
            status: "unsupported",
            value: null,
            source: "hyperliquid",
            retrieved_at: "2026-07-24T14:03:00Z",
            missing_data_reason: "no liquidation feed",
          },
          trader_positioning: {
            status: "conflicting",
            value: null,
            source: "coinalyze",
            retrieved_at: "2026-07-24T14:03:00Z",
            conflicts: ["venues disagree"],
          },
        },
        sentiment: {
          status: "not_configured",
          value: null,
          source: "social_provider",
          retrieved_at: null,
          missing_data_reason: "No paid social provider configured",
        },
      },
      private_context: {
        position: {
          status: "available",
          value: {
            quantity: 42,
            entry_price: 118.4,
            total_cost_basis: 4972.8,
            current_value: 5930.4,
            unrealized_pnl: 957.6,
            unrealized_pnl_pct: 19.26,
          },
        },
        thesis: { status: "unavailable", value: null },
      },
      confidence: { level: "insufficient_evidence", reasons: ["thin data"] },
    },
    comparison: {
      status: "compared",
      categories: ["only_price_changed"],
      changes: [{ field: "price", type: "numeric_change", from: 140, to: 141.2 }],
      thesis_support: { direction: "unknown", reasons: ["No thesis supplied."] },
    },
    analysis: {
      status: "not_configured",
      created_at: "2026-07-24T14:05:00Z",
      sections: {
        direct_assessment: "Analysis generation unavailable: founder/server key or LLM provider is not configured.",
      },
    },
  };

  it("preserves backend nulls, statuses, source, retrieved_at, and freshness", () => {
    const normalized = normalizeBackendSnapshot(backendSnapshot);
    expect(normalized.position.market_price).toBe(141.2);
    expect(normalized.position.allocation_pct).toBeNull();
    expect(normalized.confidence.level).toBe("insufficient_evidence");
    expect(normalized.what_changed.kind).toBe("only_price_changed");
    const byStatus = Object.fromEntries(normalized.missing.map((item) => [item.status, item]));
    expect(byStatus.not_configured.detail).toMatch(/configured/i);
    expect(byStatus.provider_error.provider_error).toBe("timeout");
    expect(byStatus.stale.retrieved_at).toBe("2026-07-24T13:04:00Z");
    expect(byStatus.conflicting.conflicts).toEqual(["venues disagree"]);
    expect(normalized.sources.some((source) => source.provider === "fixture_price")).toBe(true);
  });

  it("renders backend not_configured model truthfully without turning missing metrics into zero", () => {
    const { state, view } = buildAnalysisView(backendSnapshot);
    expect(state).toBe(ANALYSIS_STATE.READY);
    expect(view.directRead.headline).toBe("Model analysis is not configured");
    expect(view.position.display.allocationPct).toBe("—");
    expect(view.confidence.label).toBe("Insufficient evidence");
    expect(view.whatChanged.label).toBe("Only price moved");
  });
});
