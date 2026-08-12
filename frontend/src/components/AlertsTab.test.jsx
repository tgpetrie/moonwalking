import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SignalRow, freshnessFromStale } from "./AlertsTab";

// AlertsTab imports contexts that SignalRow doesn't use — mock so the module loads cleanly
vi.mock("../context/DataContext", () => ({ useData: () => ({}) }));
vi.mock("../context/WatchlistContext.jsx", () => ({ useWatchlist: () => ({ watchlist: [] }) }));

const NOW_MS = 1_800_000_000_000;

describe("market mood feed freshness", () => {
  it("describes literal feed age instead of calling it confidence", () => {
    expect(freshnessFromStale(1.2, 0.7)).toMatchObject({
      label: "Feed freshness: 1.2s",
      hint: "Oldest market input is 1.2s old.",
    });
  });

  it("shows unavailable when no freshness measurement exists", () => {
    expect(freshnessFromStale(null, null).label).toBe("Feed freshness unavailable");
  });
});

const base = {
  id: "test-1",
  symbol: "BTC-USD",
  type_key: "breakout",
  severity: "high",
  event_ts_ms: NOW_MS - 60_000,
};

const productionInterp = {
  summary: "Price broke out +4.8% in 3m with confirmed multi-window momentum.",
  supportingFactors: ["Large move: +4.8% in 3m", "Momentum confirmed across 1m, 1h windows"],
  cautionFactors: [],
  invalidationCondition: "Move reverses below the 3m open",
  confidence: 63,
  confidenceFactors: ["Large move: +4.8% in 3m"],
  interpretation_support_level: "production",
};

// ---------------------------------------------------------------------------
// 1. Primary text — interpretation summary replaces fallback message
// ---------------------------------------------------------------------------

describe("SignalRow – primary text", () => {
  it("shows interpretation summary when support_level is production", () => {
    render(<SignalRow a={{ ...base, interpretation: productionInterp }} nowMs={NOW_MS} />);
    expect(screen.getByText(/Price broke out.*confirmed multi-window momentum/)).toBeInTheDocument();
  });

  it("shows interpretation summary when support_level is experimental", () => {
    const a = {
      ...base,
      message: "Old message that should not appear",
      interpretation: { ...productionInterp, interpretation_support_level: "experimental" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText(/Price broke out.*confirmed multi-window momentum/)).toBeInTheDocument();
  });

  it("falls back to message when support_level is none", () => {
    const a = {
      ...base,
      message: "BTC moved upward sharply",
      interpretation: { summary: "should not show", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("should not show")).not.toBeInTheDocument();
    expect(screen.getByText(/moved upward sharply/)).toBeInTheDocument();
  });

  it("falls back to message when interpretation is absent", () => {
    const a = { ...base, message: "BTC breakout signal" };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText(/breakout signal/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Supporting factors disclosure
// ---------------------------------------------------------------------------

describe("SignalRow – Why this read? disclosure", () => {
  it("shows disclosure trigger when supporting factors exist", () => {
    render(<SignalRow a={{ ...base, interpretation: productionInterp }} nowMs={NOW_MS} />);
    expect(screen.getByText("Why this read?")).toBeInTheDocument();
  });

  it("shows disclosure trigger when only caution factors exist", () => {
    const a = {
      ...base,
      interpretation: {
        ...productionInterp,
        supportingFactors: [],
        cautionFactors: ["Thin liquidity in window"],
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Why this read?")).toBeInTheDocument();
  });

  it("does not render disclosure when no factors exist", () => {
    const a = {
      ...base,
      interpretation: {
        ...productionInterp,
        supportingFactors: [],
        cautionFactors: [],
        invalidationCondition: "",
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });

  it("does not render disclosure when support_level is none", () => {
    const a = {
      ...base,
      interpretation: {
        ...productionInterp,
        interpretation_support_level: "none",
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. Confidence label source — interpretation engine score takes precedence
// ---------------------------------------------------------------------------

describe("SignalRow – confidence label source", () => {
  it("uses interpretation.confidence when support_level is production", () => {
    const a = {
      ...base,
      confidence: 30,                       // root: would map to Limited
      interpretation: { ...productionInterp, confidence: 75 }, // engine: High
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("uses interpretation.confidence when support_level is experimental", () => {
    const a = {
      ...base,
      confidence: 80,                       // root: High
      interpretation: {
        ...productionInterp,
        confidence: 40,                     // engine: Limited
        interpretation_support_level: "experimental",
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Limited")).toBeInTheDocument();
  });

  it("maps interpretation.confidence 70+ to High", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 70 } };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("maps interpretation.confidence 45–69 to Developing", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 50 } };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Developing")).toBeInTheDocument();
  });

  it("maps interpretation.confidence <45 to Limited", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 30 } };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Limited")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 4. Signals/event confidence is semantically distinct from interpretation
// ---------------------------------------------------------------------------

describe("SignalRow – event rows do not reuse interpretation confidence labels", () => {
  it("does not show root event confidence when support_level is none", () => {
    const a = {
      ...base,
      confidence: 80,
      interpretation: { summary: "x", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
  });

  it("does not show High solely from a Moonwalking event-state score", () => {
    const a = { ...base, primary_state: "Moonwalking", confidence: 82 };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText("MOONWALKING")).toBeInTheDocument();
  });

  it("suppresses the chip on Signals rows even if interpretation is present", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 80 } };
    render(<SignalRow a={a} nowMs={NOW_MS} confidenceSemantics="none" />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText(/Price broke out/)).toBeInTheDocument();
    expect(screen.getByText("Why this read?")).toBeInTheDocument();
  });

  it("does not mutate the stored event confidence value", () => {
    const a = { ...base, primary_state: "Reversal Risk", confidence: 72 };
    render(<SignalRow a={a} nowMs={NOW_MS} confidenceSemantics="none" />);
    expect(a.confidence).toBe(72);
  });
});

// ---------------------------------------------------------------------------
// 5. the_read demotion — hidden behind disclosure when interpretation exists
// ---------------------------------------------------------------------------

describe("SignalRow – the_read demotion", () => {
  const theRead = {
    label: "Breakout Active",
    condition: "Resistance cleared",
    summary: "Price pushed above recent resistance on volume",
    tone: "favorable",
  };

  it("demotes the_read when interpretation is present (Event analysis trigger visible)", () => {
    const a = { ...base, interpretation: productionInterp, the_read: theRead };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Event analysis")).toBeInTheDocument();
    // THE READ eyebrow is not immediately visible at top level
    expect(screen.queryByLabelText("The Read")).not.toBeInTheDocument();
  });

  it("the_read renders at top level when no interpretation", () => {
    const a = { ...base, the_read: theRead };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("THE READ")).toBeInTheDocument();
  });

  it("the_read renders at top level when support_level is none", () => {
    const a = {
      ...base,
      the_read: theRead,
      interpretation: { summary: "x", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("THE READ")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. Graceful degradation — missing / partial interpretation
// ---------------------------------------------------------------------------

describe("SignalRow – graceful degradation", () => {
  it("renders without crash when interpretation key is missing entirely", () => {
    render(<SignalRow a={base} nowMs={NOW_MS} />);
    expect(screen.getByText("BREAKOUT")).toBeInTheDocument();
  });

  it("renders without crash when interpretation.confidence is null", () => {
    const a = {
      ...base,
      interpretation: { summary: "Signal detected.", confidence: null, interpretation_support_level: "production" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText(/Signal detected/)).toBeInTheDocument();
  });

  it("renders without crash when supportingFactors is absent from interpretation", () => {
    const a = {
      ...base,
      interpretation: { summary: "Breakout.", confidence: 60, interpretation_support_level: "production" },
    };
    expect(() => render(<SignalRow a={a} nowMs={NOW_MS} />)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 7. Legacy alerts — alerts without interpretation key still render correctly
// ---------------------------------------------------------------------------

describe("SignalRow – legacy alerts (pre-engine)", () => {
  it("shows message text for legacy alert with no interpretation", () => {
    const legacy = { ...base, message: "BTC surged above resistance" };
    render(<SignalRow a={legacy} nowMs={NOW_MS} />);
    expect(screen.getByText(/surged above resistance/)).toBeInTheDocument();
  });

  it("does not present root event confidence as interpretation confidence", () => {
    const legacy = { ...base, confidence: 72, message: "BTC breakout" };
    render(<SignalRow a={legacy} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText("breakout")).toBeInTheDocument();
  });

  it("shows no Why this read? for legacy alert", () => {
    render(<SignalRow a={{ ...base, message: "BTC moved" }} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });
});
