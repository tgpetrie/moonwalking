import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, it, expect, vi } from "vitest";
import PaperExecutionControls from "./PaperExecutionControls.jsx";
import { fetchData } from "../api";
import { useData } from "../context/DataContext";
import SentimentPopupAdvanced, { CoinDossierScore, CoinOutcomeHistory, DEFAULT_CHART_HORIZON, RiskLevelsPanel } from "./SentimentPopupAdvanced";
import ChartReadPanel from "./ChartReadPanel.jsx";

// Keep the popup's broad dependency surface deterministic for both the pure
// CoinOutcomeHistory tests and the rendered popup regression below.
vi.mock("../context/DataContext", () => ({ useData: vi.fn(() => ({})) }));
vi.mock("../hooks/useMarketHeat", () => ({ useMarketHeat: () => ({}) }));
vi.mock("../api", () => ({ API_ENDPOINTS: {}, fetchData: vi.fn() }));
vi.mock("../utils/coinHistoryCache", async (importOriginal) => ({
  ...(await importOriginal()),
  getCoinEvents: vi.fn(() => []),
}));
vi.mock("../utils/marketPressure", () => ({ getMarketPressure: vi.fn() }));
vi.mock("./CoinPositioning.jsx", () => ({ default: () => null }));
vi.mock("./AlertsTab", () => ({ default: () => null }));
vi.mock("./ChartReadPanel.jsx", () => ({ default: vi.fn(() => null) }));
vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

describe("Coin Dossier score and owner controls", () => {
  it("combines measured sub-gauges into a bounded composite without hiding risk warnings", () => {
    render(<CoinDossierScore change1m={2} change3m={4}
      ranking={{ live_rank: 1, universe_size: 120 }}
      cycle={{ cycle_range_position_pct: 10, rsi_regimes: { "1w": { value: 50 } },
        multiyear_cycle_anatomy: { accumulation_base: { stage_label: "Deep Accumulation · 21 mo base" } } }}
      volumeChange={80} persistence={4} exhausted trigger="Wait for a reclaim." sentiment="Tape-led." />);
    expect(screen.getByText("73/100")).toBeInTheDocument();
    expect(screen.getByText("Deep Accumulation · 21 mo base")).toBeInTheDocument();
    expect(screen.getByText(/Exhaustion \/ reversal warning/)).toBeInTheDocument();
    const gauges = screen.getAllByRole("meter");
    expect(gauges).toHaveLength(3);
    for (const gauge of gauges) expect(Number(gauge.getAttribute("value"))).toBeLessThanOrEqual(100);
    expect(screen.getByText("Wait for a reclaim.")).toBeInTheDocument();
  });

  it("does not turn absent data into a neutral conviction score", () => {
    render(<CoinDossierScore />);
    expect(screen.getByText("Pending evidence")).toBeInTheDocument();
    expect(screen.queryAllByRole("meter")).toHaveLength(0);
  });

  it("uses fractional tape velocity and the actual weekly RSI payload", () => {
    render(<CoinDossierScore change1m={0.25} change3m={0.25}
      cycle={{ cycle_range_position_pct: 10, rsi_regimes: { "1w": { value: 40 } } }} />);
    expect(screen.getByRole("meter", { name: "Tape Momentum" })).toHaveAttribute("value", "53");
    expect(screen.getByRole("meter", { name: "Volume & Sentiment Confirmation" })).toHaveAttribute("value", "80");
    expect(screen.getByText("74/100")).toBeInTheDocument();
  });

  it("keeps operational errors visible rather than treating them as anonymous access", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 500, json: async () => ({ error: "Paper store unavailable" }),
    }));
    try {
      render(<PaperExecutionControls collapsible />);
      expect(await screen.findByRole("alert")).toHaveTextContent("Paper store unavailable");
    } finally { vi.unstubAllGlobals(); }
  });

  it.each([401, 403])("hides paper boilerplate on HTTP %s", async (status) => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status, json: async () => ({ error: "Not authenticated" }) });
    vi.stubGlobal("fetch", fetch);
    try {
      render(<PaperExecutionControls collapsible />);
      await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
      expect(screen.queryByText("Paper execution")).not.toBeInTheDocument();
      expect(screen.queryByText("Owner paper controls")).not.toBeInTheDocument();
      expect(screen.queryByText("Not authenticated")).not.toBeInTheDocument();
    } finally { vi.unstubAllGlobals(); }
  });
});

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

// Readiness now travels with the payload. The client renders what the server
// declares rather than deciding from a sample count, so a card carrying a
// win_rate is only ever shown when the server marked that track measured.
const CARD_MEASURED = {
  ...CARD_STRONG,
  peer_status: "measured",
  placebo_status: "measured",
  required_market_periods: 100,
  peer_market_periods: 120,
  placebo_market_periods: 110,
};

const CARD_LEARNING = {
  ...CARD_STRONG,
  label: "LEARNING SIGNAL",
  peer_status: "learning",
  placebo_status: "learning",
  required_market_periods: 100,
  peer_market_periods: 34,
  placebo_market_periods: 12,
  // Deliberately non-null: a stale or buggy server could still send a rate,
  // and the client must refuse to render it while the track is learning.
  win_rate: 0.75,
};

const CARD_PEER_ONLY = {
  ...CARD_MEASURED,
  label: "PEER ONLY SIGNAL",
  placebo_status: "learning",
  placebo_market_periods: 40,
  win_rate: 0.35,
};

function makeData(overrides = {}) {
  return {
    status: "live", // transport health
    measurement_status: "measured", // measurement readiness
    product_id: "BTC-USD",
    total_outcomes: 150,
    target_pct: 2.0,
    adverse_pct: 1.0,
    horizon_minutes: 60,
    signal_types: [CARD_MEASURED],
    ...overrides,
  };
}

const RISK_LEVELS = {
  status: "live",
  plan: {
    available: true,
    current_price: 100,
    top_signal: {
      label: "Top watch",
      tone: "caution",
      score: 4,
      action: "Watch for rejection before adding risk.",
      reasons: ["Price is in the top 15% of its recent candle range."],
    },
    stop: {
      trigger_price: 94.6,
      limit_price: 94.2,
      invalidation_price: 95,
      distance_pct: -5.4,
      risk_band: "standard",
      why: ["Recent structural support is $95."],
      execution_warning: "A fast gap can pass the limit without a fill.",
    },
    profit: {
      first_trim_price: 112,
      reward_pct: 12,
      reward_risk_ratio: 2.22,
    },
    support_zone: {
      low: 94.8,
      high: 95.5,
      why: "Require a hold or reclaim.",
    },
    market_structure: {
      resistance: 112,
      atr: 2,
      range_position_pct: 90,
      window_hours: 50,
    },
    methodology: { disclosure: "Descriptive decision support, not an order." },
  },
  history: {
    total_plans: 3,
    open_plans: 1,
    outcomes: { target_first: 1, stop_first: 1, expired: 0 },
    disclosure: "Raw boundary counts only.",
    history: [],
  },
};

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

describe("RiskLevelsPanel", () => {
  it("clearly separates the stop trigger, limit, invalidation, and trim area", () => {
    render(<RiskLevelsPanel data={RISK_LEVELS} />);

    expect(screen.getByText("Top watch")).toBeInTheDocument();
    expect(screen.getByText("Stop trigger")).toBeInTheDocument();
    expect(screen.getByText("Sell limit (uncalibrated)")).toBeInTheDocument();
    expect(screen.queryByText("Sell limit", { exact: true })).not.toBeInTheDocument();
    expect(screen.getByText("Structure invalidates")).toBeInTheDocument();
    expect(screen.getByText("First trim area")).toBeInTheDocument();
    expect(screen.getByText(/fast gap can pass the limit/i)).toBeInTheDocument();
  });

  it("shows raw plan history counts without inventing a success rate", () => {
    render(<RiskLevelsPanel data={RISK_LEVELS} />);

    expect(screen.getByText("3 recorded plans")).toBeInTheDocument();
    expect(screen.getByText("Target first")).toBeInTheDocument();
    expect(screen.getByText("Stop first")).toBeInTheDocument();
    expect(screen.queryByText(/win rate/i)).not.toBeInTheDocument();
  });
});

describe("SentimentPopupAdvanced - rendered semantic consistency", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.mocked(useData).mockReset();
    vi.mocked(useData).mockReturnValue({});
    vi.mocked(fetchData).mockReset();
  });

  it("opens RENDER's exact USD spot page from the modal Trade link", () => {
    vi.mocked(useData).mockReturnValue({});
    vi.mocked(fetchData).mockResolvedValue(null);
    render(<SentimentPopupAdvanced isOpen onClose={vi.fn()} symbol="RENDER" />);
    const link = screen.getByRole("link", { name: "Trade RENDER on Coinbase Advanced" });
    expect(link).toHaveAttribute("href", "https://www.coinbase.com/advanced-trade/spot/RENDER-USD");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("opens the dossier chart on the multi-year cycle and never loses it when switching views", async () => {
    vi.mocked(useData).mockReturnValue({});
    vi.mocked(ChartReadPanel).mockClear();
    const anatomy = { available: true, pivots: [], accumulation_base: { floor: 10, ceiling: 25 } };
    const reads = {
      cycle: { horizon: "cycle", multiyear_cycle_anatomy: anatomy },
      swing: { horizon: "swing", wave_analysis: { available: false } },
      short: { horizon: "short" },
    };
    vi.mocked(fetchData).mockImplementation(async (endpoint) => {
      const url = String(endpoint);
      if (!url.includes("/api/chart-read/")) return null;
      return reads[url.match(/horizon=(\w+)/)?.[1] || "swing"];
    });
    const chartCalls = () => vi.mocked(fetchData).mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/api/chart-read/"));
    const props = () => vi.mocked(ChartReadPanel).mock.calls.at(-1)[0];

    render(<SentimentPopupAdvanced isOpen onClose={vi.fn()} symbol="SOL" />);
    expect(DEFAULT_CHART_HORIZON).toBe("cycle");
    expect(props().horizon).toBe("cycle");
    // The cycle view is asked for first; the swing read loads beside it.
    expect(chartCalls()[0]).toBe("/api/chart-read/SOL?horizon=cycle");
    expect(chartCalls()).toContain("/api/chart-read/SOL");
    await waitFor(() => expect(props().data).toBe(reads.cycle));
    expect(props().loading).toBe(false);

    // Switching keeps the last read on screen while the next one loads...
    act(() => props().onHorizonChange("short"));
    expect(props().horizon).toBe("short");
    expect(props().loading).toBe(true);
    expect(props().data).toBe(reads.cycle);
    // ...and every view carries the cycle anatomy for the multi-year levels.
    await waitFor(() => expect(props().data).toBe(reads.short));
    expect(props().cycleAnatomy).toBe(anatomy);

    // Back to a cached view: instant, no second request.
    act(() => props().onHorizonChange("cycle"));
    expect(props().data).toBe(reads.cycle);
    expect(props().loading).toBe(false);
    expect(chartCalls().filter((url) => url.endsWith("horizon=cycle"))).toHaveLength(1);
    expect(chartCalls().filter((url) => url === "/api/chart-read/SOL")).toHaveLength(1);
  });
  it("keeps Reversal Risk negative when positive 3m tape activates bullish fallbacks", async () => {
    const nowMs = 1_800_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(nowMs);

    vi.mocked(useData).mockReturnValue({
      activeAlerts: [
        {
          id: "btc-social-divergence",
          symbol: "BTC-USD",
          type_key: "social_divergence",
          severity: "high",
          ts_ms: nowMs - 30_000,
          expires_at: new Date(nowMs + 5 * 60_000).toISOString(),
          evidence: {
            pct_3m: 2.4,
            volume_change_1h_pct: -20,
            streak: 4,
          },
        },
        {
          id: "btc-breadth-thrust",
          symbol: "BTC-USD",
          type_key: "breadth_thrust",
          severity: "info",
          ts_ms: nowMs - 20_000,
          expires_at: new Date(nowMs + 5 * 60_000).toISOString(),
          evidence: { pct_1m: 0.1 },
        },
        {
          id: "btc-breakout",
          symbol: "BTC-USD",
          type_key: "breakout",
          severity: "info",
          ts_ms: nowMs - 40_000,
          expires_at: new Date(nowMs + 5 * 60_000).toISOString(),
          evidence: { pct_1m: 0.1 },
        },
      ],
      alertsRecent: [],
      connectionStatus: "LIVE",
      gainers_1m: [{ symbol: "BTC-USD", rank: 1 }],
      gainers_3m: [{ symbol: "BTC-USD", rank: 1 }],
      losers_3m: [],
      liveRankings: [{
        symbol: "BTC-USD",
        live_rank: 1,
        universe_size: 100,
        live_score: 88,
        data_quality: 100,
        observed_inputs: 6,
        expected_inputs: 6,
      }],
    });
    vi.mocked(fetchData).mockImplementation(async (endpoint) => {
      if (String(endpoint).includes("/api/insights/")) {
        return {
          symbol: "BTC",
          change_1m: 0.8,
          change_3m: 2.4,
          change_1h: 4.1,
          volume_change_1h: 20,
          updated_at: nowMs,
        };
      }
      if (String(endpoint).includes("/api/positioning/")) return { available: false };
      return null;
    });

    render(
      <SentimentPopupAdvanced
        isOpen
        onClose={vi.fn()}
        symbol="BTC"
      />
    );

    // The risk posture rides on the header strip's tape pill, not a full-screen card.
    expect(await screen.findByText("STAY CLEAR")).toBeInTheDocument();
    const tape = screen.getByTestId("coin-strip-tape");
    expect(within(tape).getByText("STAY CLEAR")).toBeInTheDocument();
    const lean = within(tape).getByText("TAPE UP");
    expect(lean).toHaveStyle({ color: "#f1b43a" });
    expect(lean.getAttribute("title")).toMatch(/risk warning overrides entry quality/i);
    // With no chart history the tape posture is the headline, risk reason included.
    const headline = screen.getByTestId("coin-strip-headline");
    expect(headline).toHaveAttribute("data-source", "tape");
    expect(headline.textContent).toMatch(/active risk warning is overriding the setup/i);

    // The full reasoning is still there, under "See the evidence".
    const posture = screen.getByTestId("coin-tape-posture");
    expect(posture.closest("details")).not.toBeNull();
    expect(within(posture).getByText(/risk warning overrides entry quality/i)).toBeInTheDocument();
    expect(within(posture).getByText("What blocks it")).toBeInTheDocument();

    // No wall of text above the chart, and the chart read is not behind an accordion.
    expect(screen.queryByText(/RIGHT NOW/)).not.toBeInTheDocument();
    expect(screen.queryByText("Early read")).not.toBeInTheDocument();
    expect(document.querySelector(".cp-simple-read")).toBeNull();
    const hero = screen.getByTestId("coin-chart-hero");
    expect(hero.closest("details")).toBeNull();
    expect(screen.getByTestId("coin-strip").compareDocumentPosition(hero) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText("Chart & Read")).not.toBeInTheDocument();

    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Composite Conviction Score" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("Pulse evidence"));

    const actionBias = screen.getByText("Action Bias").closest(".cp-hero");
    expect(actionBias).toHaveClass("cp-hero--negative");
    expect(actionBias).not.toHaveClass("cp-hero--positive");
    expect(within(actionBias).getByText("Stand aside")).toBeInTheDocument();

    const pulse = screen.getByText("Pulse evidence").closest("details");
    const fragileSetup = within(pulse).getByText("Fragile").closest(".cp-support-pill");
    expect(fragileSetup).toHaveClass("cp-support-pill--negative");

    const freshTrigger = screen.getByText("Fresh 30s").closest(".cp-support-pill");
    expect(freshTrigger).toHaveClass("cp-support-pill--neutral");
    expect(freshTrigger).not.toHaveClass("cp-support-pill--positive");

    const quickBuyRead = screen.getByText("Quick Buy Read").closest(".cp-quick-read");
    expect(quickBuyRead).toHaveClass("cp-quick-read--negative");
    await waitFor(() => {
      expect(within(quickBuyRead).getByText("WAIT")).toBeInTheDocument();
      expect(within(quickBuyRead).getByText("This setup can break either way. Wait for reclaim or cleaner failure.")).toBeInTheDocument();
      expect(within(quickBuyRead).getByText(/active risk warning to clear/i)).toBeInTheDocument();
      expect(within(quickBuyRead).queryByText("BUY WATCH")).not.toBeInTheDocument();
    });
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
    expect(screen.getByText(/No signal history for BTC yet/i)).toBeInTheDocument();
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

  it("shows total outcome count in header once measured", () => {
    render(<CoinOutcomeHistory data={makeData({ total_outcomes: 150 })} loading={false} error={null} symbol="BTC" />);
    expect(screen.getByText(/150 comparable outcomes/i)).toBeInTheDocument();
  });

  it("does not claim an outcome count while still learning", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ measurement_status: "learning", total_outcomes: 0 })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText(/comparable outcomes/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Measuring against matched control coins/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// n >= 20 — measured follow-through rate is shown
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – server-declared measured track", () => {
  it("shows follow-through percentage when the server marks the peer track measured", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_MEASURED] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("21%")).toBeInTheDocument();
  });

  it("shows the rate on peer evidence alone, with timing still collecting", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_PEER_ONLY] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    // Coin-selection is measured, so its rate may show...
    expect(screen.getByText("35%")).toBeInTheDocument();
    // ...while the timing track reports its own separate progress.
    expect(screen.getByText(/40 of 100 market periods/i)).toBeInTheDocument();
  });

  it("does not show the collecting message when the track is measured", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_MEASURED] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText(/still collecting/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// n < 20 — rate is suppressed
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – learning track", () => {
  it("shows the collecting message instead of a percentage", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_LEARNING] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText(/No clear edge detected yet — still collecting/i)).toBeInTheDocument();
  });

  it("refuses to render a win rate the server sent while the track is learning", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_LEARNING] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText("75%")).not.toBeInTheDocument();
  });

  it("reports the two control tracks separately, since they fill at different rates", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_LEARNING] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("Coin-selection")).toBeInTheDocument();
    expect(screen.getByText(/34 of 100 market periods/i)).toBeInTheDocument();
    expect(screen.getByText("Timing")).toBeInTheDocument();
    expect(screen.getByText(/12 of 100 market periods/i)).toBeInTheDocument();
  });

  it("suppresses the median move figures while learning", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_LEARNING] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.queryByText(/Typical best move/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Typical worst dip/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// No evidence tier labels rendered — spec: count + rate only, no Strong/Solid/etc.
// ---------------------------------------------------------------------------

describe("CoinOutcomeHistory – no tier labels", () => {
  it("does not render Strong tier label", () => {
    render(
      <CoinOutcomeHistory
        data={makeData({ signal_types: [CARD_MEASURED] })}
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
        data={makeData({ signal_types: [CARD_LEARNING] })}
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
        data={makeData({ signal_types: [CARD_MEASURED, CARD_LEARNING] })}
        loading={false}
        error={null}
        symbol="BTC"
      />
    );
    expect(screen.getByText("REVERSAL RISK RISING")).toBeInTheDocument();
    expect(screen.getByText("LEARNING SIGNAL")).toBeInTheDocument();
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
