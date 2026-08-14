import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ScorecardPage, { evidenceTier } from "./ScorecardPage";

vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

// ---------------------------------------------------------------------------
// Fixtures — named after the evidence tier they exercise
// ---------------------------------------------------------------------------

const SIGNAL_STRONG = {
  state: "Reversal Risk",
  direction: "up",
  label: "REVERSAL RISK RISING",
  sample_size: 200,           // 100+ → Deep evidence
  win_rate: 0.18,
  recent_win_rate: 0.14,
  recent_sample: 50,
  median_favorable_pct: 1.8,
  median_adverse_pct: -0.8,
  median_return: { "5m": 0.3, "15m": 0.5, "30m": -0.2, "60m": -0.8 },
  oldest_ts: 1700000000,
  newest_ts: 1700086400,
};

const SIGNAL_SOLID    = { ...SIGNAL_STRONG, label: "SOLID SIGNAL",    sample_size: 45 };  // 30–99 → Solid
const SIGNAL_BUILDING = { ...SIGNAL_STRONG, label: "BUILDING SIGNAL", sample_size: 15 };  // 10–29 → Building
const SIGNAL_EMERGING = { ...SIGNAL_STRONG, label: "EMERGING SIGNAL", sample_size: 7  };  // 1–9  → Emerging
const SIGNAL_ESCALATING = {
  ...SIGNAL_STRONG,
  state: "Escalating",
  label: "STRONG BUY",
  sample_size: 55,
  win_rate: 0.62,
  recent_win_rate: 0.58,
};
const SIGNAL_BUILDING_STATE = {
  ...SIGNAL_STRONG,
  state: "Building",
  label: "WATCH",
  sample_size: 15,
  win_rate: 0.34,
  recent_win_rate: 0.31,
};

const BOARD_STRONG = {
  board: "ignition_1m",
  status: "measured",
  read: "No clear edge",
  sample_size: 150,           // 100+ → Deep evidence
  matched_sample_size: 130,
  continuation_rate: 0.18,
  reversal_rate: 0.20,
  continuation_ci95: [0.12, 0.24],
  continuation_lift_vs_control: -0.02,
  median_directional_return: { "5m": -0.1, "15m": -0.2, "30m": 0.1, "60m": 0.3 },
};

const BOARD_SOLID = {
  ...BOARD_STRONG,
  board: "confirmation_3m_up",
  status: "learning",
  sample_size: 45,            // 30–99 → Solid evidence
};

function makeResponse(overrides = {}) {
  return {
    status: "live",
    signals: {
      total_graded: 1500,
      overall_win_rate: 0.21,
      target_pct: 2.0,
      adverse_pct: 1.0,
      horizon_minutes: 60,
      signal_types: [SIGNAL_STRONG],
      ...overrides.signals,
    },
    boards: {
      total_entries: 300,
      boards: { ignition_1m: BOARD_STRONG },
      ...overrides.boards,
    },
  };
}

function mockFetch(payload, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    json: vi.fn().mockResolvedValue(payload),
  });
}

function mockFetchSequence(responses) {
  const queued = [...responses];
  global.fetch = vi.fn(async () => {
    const next = queued.shift();
    if (!next) {
      throw new Error("Unexpected fetch");
    }
    return {
      ok: next.ok !== false,
      status: next.status ?? 200,
      json: vi.fn().mockResolvedValue(next.payload),
    };
  });
}

// ---------------------------------------------------------------------------
// evidenceTier adapter — pure function unit tests
// Thresholds come from describeEvidenceTier() in portfolioSignals.js:
//   100+ → strong, 30–99 → solid, 10–29 → building, 1–9 → emerging, 0 → none
// ---------------------------------------------------------------------------

describe("evidenceTier", () => {
  it("returns 'Deep evidence' for 100 or more samples", () => {
    expect(evidenceTier(100).label).toBe("Deep evidence");
    expect(evidenceTier(100).tier).toBe("strong");
    expect(evidenceTier(8487).label).toBe("Deep evidence");
  });

  it("returns 'Solid evidence' for 30–99 samples", () => {
    expect(evidenceTier(30).label).toBe("Solid evidence");
    expect(evidenceTier(99).label).toBe("Solid evidence");
    expect(evidenceTier(30).tier).toBe("solid");
  });

  it("returns 'Thin evidence' for 10–29 samples", () => {
    expect(evidenceTier(10).label).toBe("Thin evidence");
    expect(evidenceTier(29).label).toBe("Thin evidence");
    expect(evidenceTier(10).tier).toBe("building");
  });

  it("shares no vocabulary with the event states on the same card", () => {
    // FRIENDLY_STATES renders event-state "Building (early)" in the card header
    // while EvidenceTier renders in the card body. They must not collide.
    for (const n of [1, 10, 30, 100]) {
      expect(evidenceTier(n).label).not.toContain("Building");
      expect(evidenceTier(n).label).not.toContain("Strong");
    }
  });

  it("returns 'Emerging evidence' for 1–9 samples", () => {
    expect(evidenceTier(9).label).toBe("Emerging evidence");
    expect(evidenceTier(1).label).toBe("Emerging evidence");
    expect(evidenceTier(9).tier).toBe("emerging");
  });

  it("returns null label for zero samples", () => {
    expect(evidenceTier(0).label).toBeNull();
    expect(evidenceTier(0).tier).toBe("none");
  });
});

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe("ScorecardPage – loading and error states", () => {
  it("shows loading text while fetch is pending", () => {
    global.fetch = vi.fn(() => new Promise(() => {}));
    render(<ScorecardPage />);
    expect(screen.getByText(/Loading outcome scorecard/i)).toBeInTheDocument();
  });

  it("shows error message when fetch rejects", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network failure"));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText(/Failed to load scorecard/i)).toBeInTheDocument()
    );
  });

  it("shows error message when fetch returns a non-ok status", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText(/Failed to load scorecard/i)).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// Aggregate statistics
// ---------------------------------------------------------------------------

describe("ScorecardPage – aggregate statistics", () => {
  beforeEach(() => mockFetch(makeResponse()));

  it("renders the total graded count", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("1,500")).toBeInTheDocument()
    );
  });

  it("labels target-before-adverse results as follow-through, not accuracy", async () => {
    render(<ScorecardPage />);
    await waitFor(() => {
      expect(screen.getByText("Overall follow-through")).toBeInTheDocument();
      expect(screen.getByText("Best follow-through")).toBeInTheDocument();
      expect(screen.getByText("21.0%")).toBeInTheDocument();
      expect(screen.queryByText(/accuracy/i)).not.toBeInTheDocument();
    });
  });

  it("renders the target move percentage", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("+2%")).toBeInTheDocument()
    );
  });

  it("renders the stop level percentage", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("-1%")).toBeInTheDocument()
    );
  });

  it("renders the time window in minutes", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("60 min")).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// State rollup
// ---------------------------------------------------------------------------

describe("ScorecardPage – state rollup", () => {
  it("summarizes signal families by state before individual cards", async () => {
    mockFetch(
      makeResponse({
        signals: {
          signal_types: [SIGNAL_ESCALATING, SIGNAL_BUILDING_STATE, SIGNAL_STRONG],
        },
      })
    );

    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("State Rollup")).toBeInTheDocument()
    );
    const cards = [...document.querySelectorAll(".sc-rollup-grid:not(.sc-rollup-grid--boards) .sc-rollup-card")];
    expect(cards.length).toBe(3);
    expect(cards.some((card) => card.textContent.includes("Escalating"))).toBe(true);
    expect(cards.some((card) => card.textContent.includes("Building"))).toBe(true);
    expect(cards.some((card) => card.textContent.includes("62% follow-through"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Signal cards
// ---------------------------------------------------------------------------

describe("ScorecardPage – signal card rendering", () => {
  beforeEach(() => mockFetch(makeResponse()));

  it("renders the signal label", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("REVERSAL RISK RISING")).toBeInTheDocument()
    );
  });

  it("renders the direction chip", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("Bullish")).toBeInTheDocument()
    );
  });

  it("renders the sample count", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("200")).toBeInTheDocument()
    );
  });

  it("shows the empty message when signal_types list is empty", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [] } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText(/No signal types with enough data yet/i)).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// Board cards
// ---------------------------------------------------------------------------

describe("ScorecardPage – board card rendering", () => {
  beforeEach(() => mockFetch(makeResponse()));

  it("renders the board name", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("1-Minute Ignition")).toBeInTheDocument()
    );
  });

  it("renders the board read summary", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("No clear pattern yet")).toBeInTheDocument()
    );
  });

  it("renders the board status chip as Ready when measured", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("Ready")).toBeInTheDocument()
    );
  });

  it("shows the empty message when boards object is empty", async () => {
    mockFetch(makeResponse({ boards: { boards: {} } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText(/No board outcome data yet/i)).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// Board rollup
// ---------------------------------------------------------------------------

describe("ScorecardPage – board rollup", () => {
  it("summarizes board status before the individual board cards", async () => {
    mockFetch(
      makeResponse({
        boards: {
          boards: {
            ignition_1m: {
              ...BOARD_STRONG,
              status: "measured",
              sample_size: 150,
              continuation_rate: 0.18,
              reversal_rate: 0.2,
              continuation_lift_vs_control: -0.02,
            },
            confirmation_3m_up: {
              ...BOARD_SOLID,
              status: "learning",
              sample_size: 45,
              continuation_rate: 0.44,
              reversal_rate: 0.31,
              continuation_lift_vs_control: 0.08,
            },
          },
        },
      })
    );

    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("Board Rollup")).toBeInTheDocument()
    );
    const cards = [...document.querySelectorAll(".sc-rollup-card--boards")];
    expect(cards.length).toBe(2);
    expect(cards.some((card) => card.textContent.includes("Measured boards"))).toBe(true);
    expect(cards.some((card) => card.textContent.includes("Learning boards"))).toBe(true);
    expect(cards.some((card) => card.textContent.includes("18% continuation"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Coin drilldown
// ---------------------------------------------------------------------------

describe("ScorecardPage – coin drilldown", () => {
  it("loads coin history and renders the summary", async () => {
    mockFetchSequence([
      { payload: makeResponse() },
      {
        payload: {
          status: "live",
          product_id: "BTC-USD",
          total_outcomes: 32,
          target_pct: 2.0,
          adverse_pct: 1.0,
          horizon_minutes: 60,
          signal_types: [
            {
              state: "Confirmed",
              direction: "up",
              label: "BUY WATCH",
              sample_size: 32,
              win_rate: 0.5625,
              recent_win_rate: 0.6,
              recent_sample: 10,
              median_favorable_pct: 1.9,
              median_adverse_pct: -0.8,
              median_return: { "5m": 0.4, "15m": 0.6, "30m": 0.8, "60m": 1.1 },
            },
          ],
        },
      },
    ]);

    render(<ScorecardPage />);
    await waitFor(() => expect(screen.getByText("Coin Drilldown")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Coin/i), { target: { value: "BTC" } });
    fireEvent.click(screen.getByRole("button", { name: "Load" }));

    await waitFor(() =>
      expect(screen.getByText("32 comparable outcomes - 56% followed through")).toBeInTheDocument()
    );
    expect(screen.getByText("BTC history")).toBeInTheDocument();
  });

  it("shows a measured-history message for small samples", async () => {
    mockFetchSequence([
      { payload: makeResponse() },
      {
        payload: {
          status: "live",
          product_id: "ETH-USD",
          total_outcomes: 12,
          target_pct: 2.0,
          adverse_pct: 1.0,
          horizon_minutes: 60,
          signal_types: [],
        },
      },
    ]);

    render(<ScorecardPage />);
    await waitFor(() => expect(screen.getByText("Coin Drilldown")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Coin/i), { target: { value: "ETH" } });
    fireEvent.click(screen.getByRole("button", { name: "Load" }));

    await waitFor(() =>
      expect(
        screen.getByText("12 comparable outcomes - Not enough history for a measured rate")
      ).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// Evidence tier labels on signal cards
// Thresholds delegated to describeEvidenceTier() in portfolioSignals.js
// ---------------------------------------------------------------------------

describe("ScorecardPage – evidence tier labels on signal cards", () => {
  it("shows 'Deep evidence' for 100+ samples", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [SIGNAL_STRONG] } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Deep evidence").length).toBeGreaterThan(0)
    );
  });

  it("shows 'Solid evidence' for 30–99 samples", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [SIGNAL_SOLID] } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Solid evidence").length).toBeGreaterThan(0)
    );
  });

  it("shows 'Thin evidence' for 10–29 samples", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [SIGNAL_BUILDING] } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Thin evidence").length).toBeGreaterThan(0)
    );
  });

  it("shows 'Emerging evidence' for 1–9 samples", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [SIGNAL_EMERGING] } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Emerging evidence").length).toBeGreaterThan(0)
    );
  });

  it("applies the correct data-tier attribute for CSS styling", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [SIGNAL_STRONG] } }));
    render(<ScorecardPage />);
    await waitFor(() => {
      const tiers = document.querySelectorAll(".sc-evidence-tier");
      const strongTier = [...tiers].find(el => el.getAttribute("data-tier") === "strong");
      expect(strongTier).toBeTruthy();
    });
  });
});

// ---------------------------------------------------------------------------
// Evidence tier labels on board cards
// ---------------------------------------------------------------------------

describe("ScorecardPage – evidence tier labels on board cards", () => {
  it("shows 'Deep evidence' when board has 100+ samples", async () => {
    mockFetch(makeResponse({ signals: { signal_types: [] } }));
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Deep evidence").length).toBeGreaterThan(0)
    );
  });

  it("shows 'Solid evidence' when board has 30–99 samples", async () => {
    mockFetch(
      makeResponse({
        signals: { signal_types: [] },
        boards: { boards: { confirmation_3m_up: BOARD_SOLID } },
      })
    );
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Solid evidence").length).toBeGreaterThan(0)
    );
  });
});

// ---------------------------------------------------------------------------
// Null rates must never render as 0%
// ---------------------------------------------------------------------------

const SIGNAL_LEARNING = {
  ...SIGNAL_STRONG,
  label: "LEARNING SIGNAL",
  sample_size: 0,
  win_rate: null,
  recent_win_rate: null,
  median_favorable_pct: null,
  median_adverse_pct: null,
  peer_status: "learning",
  placebo_status: "learning",
  peer_market_periods: 12,
  required_market_periods: 100,
};

describe("ScorecardPage – learning categories never render as 0%", () => {
  it("shows a collecting state instead of 0% for a null win rate", async () => {
    mockFetch(
      makeResponse({
        signals: {
          measurement_status: "learning",
          total_graded: 0,
          overall_win_rate: null,
          signal_types: [SIGNAL_LEARNING],
        },
      })
    );
    render(<ScorecardPage />);

    await waitFor(() =>
      expect(screen.getByText("LEARNING SIGNAL")).toBeInTheDocument()
    );
    // "0%" would claim the category played out and lost every time — a
    // stronger and more damaging statement than "we have not measured it".
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Still collecting/i).length).toBeGreaterThan(0);
  });

  it("renders a dash rather than a percentage for a null overall rate", async () => {
    mockFetch(
      makeResponse({
        signals: {
          measurement_status: "learning",
          total_graded: 0,
          overall_win_rate: null,
          signal_types: [SIGNAL_LEARNING],
        },
      })
    );
    render(<ScorecardPage />);

    await waitFor(() =>
      expect(screen.getByText("Overall follow-through")).toBeInTheDocument()
    );
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
  });

  it("still renders measured rates when the server marks them measured", async () => {
    mockFetch(makeResponse());
    render(<ScorecardPage />);
    await waitFor(() => expect(screen.getByText("21.0%")).toBeInTheDocument());
  });
});
