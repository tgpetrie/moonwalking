import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CoinOutcomeHistory } from "./SentimentPopupAdvanced";

// SentimentPopupAdvanced imports many context hooks — none are exercised here
// because we only render the exported pure CoinOutcomeHistory component.
vi.mock("../context/DataContext", () => ({ useData: () => ({}) }));
vi.mock("../hooks/useMarketHeat", () => ({ useMarketHeat: () => ({}) }));
vi.mock("../api", () => ({ API_ENDPOINTS: {}, fetchData: vi.fn() }));
vi.mock("../utils/coinHistoryCache", () => ({ getCoinEvents: vi.fn() }));
vi.mock("../utils/marketPressure", () => ({ getMarketPressure: vi.fn() }));
vi.mock("../utils/coinbaseUrl", () => ({ coinbaseSpotUrl: vi.fn() }));
vi.mock("./CoinPositioning.jsx", () => ({ default: () => null }));
vi.mock("./AlertsTab", () => ({ default: () => null }));
vi.mock("./ChartReadPanel.jsx", () => ({ default: () => null }));
vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CARD_STRONG = {
  state: "Reversal Risk",
  direction: "up",
  label: "REVERSAL RISK RISING",
  sample_size: 150,
  win_rate: 0.21,
  recent_win_rate: 0.24,
  recent_sample: 50,
  median_favorable_pct: 1.3,
  median_adverse_pct: -0.8,
  median_return: { "5m": 0.2, "15m": 0.4, "30m": -0.1, "60m": -0.5 },
  oldest_ts: 1700000000,
  newest_ts: 1700086400,
};

const CARD_SPARSE = {
  ...CARD_STRONG,
  label: "SPARSE SIGNAL",
  sample_size: 8,   // below MEASURED_THRESHOLD (20)
  win_rate: 0.75,   // high but should be suppressed
};

const CARD_BOUNDARY = {
  ...CARD_STRONG,
  label: "BOUNDARY SIGNAL",
  sample_size: 20,  // exactly at the threshold — should show rate
  win_rate: 0.35,
};

function makeData(overrides = {}) {
  return {
    status: "live",
    product_id: "BTC-USD",
    total_outcomes: 150,
    target_pct: 2.0,
    adverse_pct: 1.0,
    horizon_minutes: 60,
    signal_types: [CARD_STRONG],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – loading state", () => {
  it("shows loading message when loading and no data yet", () => {
    render(<CoinOutcomeHistory data={null} loading={true} error={null} symbol="BTC" />);
    expect(screen.getByText(/Loading track record/i)).toBeInTheDocument();
  });

  it("does not show loading message when data is already present", () => {
    render(<CoinOutcomeHistory data={makeData()} loading={true} error={null} symbol="BTC" />);
    expect(screen.queryByText(/Loading track record/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – error state", () => {
  it("shows degraded message when error is set", () => {
    render(<CoinOutcomeHistory data={null} loading={false} error="degraded" symbol="BTC" />);
    expect(screen.getByText(/Track record temporarily unavailable/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// No data / null
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – null data", () => {
  it("renders nothing when data is null and not loading", () => {
    const { container } = render(
      <CoinOutcomeHistory data={null} loading={false} error={null} symbol="BTC" />
    );
    expect(container.firstChild).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// No-history state (data present, empty signal_types)
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – no history", () => {
  it("shows empty message when signal_types is empty", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [], total_outcomes: 0 })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText(/No measured history for BTC yet/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Track record header
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – header", () => {
  it("renders Track Record heading", () => {
    render(<CoinOutcomeHistory data={makeData()} loading={false} error={null} symbol="BTC" />);
    expect(screen.getByText("Track Record")).toBeInTheDocument();
  });

  it("shows total outcome count in header", () => {
    render(<CoinOutcomeHistory data={makeData({ total_outcomes: 150 })} loading={false} error={null} symbol="BTC" />);
    expect(screen.getByText(/150 comparable outcomes/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// n >= 20 — measured follow-through rate is shown
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – measured rate (n >= 20)", () => {
  it("shows follow-through percentage for 100+ samples", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_STRONG] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("21%")).toBeInTheDocument();
  });

  it("shows follow-through percentage at exactly n=20", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_BOUNDARY] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("35%")).toBeInTheDocument();
  });

  it("does not show suppression message when sample is sufficient", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_STRONG] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText(/Not enough history/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// n < 20 — rate is suppressed
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – suppressed rate (n < 20)", () => {
  it("shows 'Not enough history' instead of percentage for sparse samples", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_SPARSE] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText(/Not enough history for a measured follow-through rate/i)).toBeInTheDocument();
  });

  it("does not render the 75% win rate even though it exists in the data", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_SPARSE] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText("75%")).not.toBeInTheDocument();
  });

  it("still shows sample count for sparse data", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_SPARSE] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("8")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// No evidence tier labels rendered — spec: count + rate only, no Strong/Solid/etc.
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – no tier labels", () => {
  it("does not render Strong tier label", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_STRONG] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText("Strong")).not.toBeInTheDocument();
    expect(screen.queryByText("Solid")).not.toBeInTheDocument();
    expect(screen.queryByText("Building")).not.toBeInTheDocument();
    expect(screen.queryByText("Emerging")).not.toBeInTheDocument();
  });

  it("does not render tier label for sparse samples either", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_SPARSE] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText("Emerging")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Multiple cards
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – multiple signal types", () => {
  it("renders a card for each signal type", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_STRONG, CARD_SPARSE] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("REVERSAL RISK RISING")).toBeInTheDocument();
    expect(screen.getByText("SPARSE SIGNAL")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Degraded / missing fields — graceful fallback
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – degraded data", () => {
  it("renders without crash when signal_types is missing", () => {
    const badData = { status: "live", product_id: "BTC-USD", total_outcomes: 0, target_pct: 2, adverse_pct: 1 };
    expect(() =>
      render(<CoinOutcomeHistory data={badData} loading={false} error={null} symbol="BTC" />)
    ).not.toThrow();
  });

  it("renders without crash when median fields are null", () => {
    const card = { ...CARD_STRONG, median_favorable_pct: null, median_adverse_pct: null };
    expect(() =>
      render(
        <CoinOutcomeHistory
          data={makeData({ signal_types: [card] })}
          loading={false}
          error={null}
          symbol="BTC"
        />
      )
    ).not.toThrow();
  });
});
