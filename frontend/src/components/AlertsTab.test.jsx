import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SignalRow } from "./AlertsTab";

// AlertsTab imports contexts that SignalRow doesn't use — mock so the module loads cleanly
vi.mock("../context/DataContext", () => ({ useData: () => ({}) }));
vi.mock("../context/WatchlistContext.jsx", () => ({ useWatchlist: () => ({ watchlist: [] }) }));

const NOW_MS = 1_800_000_000_000;

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
// 4. Confidence fallback — root score used when engine has no coverage
// ---------------------------------------------------------------------------

describe("SignalRow – confidence fallback to root", () => {
  it("falls back to root confidence when support_level is none", () => {
    const a = {
      ...base,
      confidence: 80,
      interpretation: { summary: "x", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("falls back to root confidence when interpretation is absent", () => {
    const a = { ...base, confidence: 50 };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Developing")).toBeInTheDocument();
  });

  it("shows no confidence chip when both scores are absent", () => {
    render(<SignalRow a={{ ...base }} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.queryByText("Developing")).not.toBeInTheDocument();
    expect(screen.queryByText("Limited")).not.toBeInTheDocument();
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

  it("shows root confidence chip for legacy alert", () => {
    const legacy = { ...base, confidence: 72, message: "BTC breakout" };
    render(<SignalRow a={legacy} nowMs={NOW_MS} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("shows no Why this read? for legacy alert", () => {
    render(<SignalRow a={{ ...base, message: "BTC moved" }} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });
});
