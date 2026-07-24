import { describe, expect, it } from "vitest";
import { buildAnalysisView, validatePositionDraft, fmtPct, relativeTime } from "../askBhabitAdapter.js";
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
