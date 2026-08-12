import { render, screen, waitFor } from "@testing-library/react";
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

  it("renders the overall accuracy as a percentage", async () => {
    render(<ScorecardPage />);
    await waitFor(() =>
      expect(screen.getByText("21.0%")).toBeInTheDocument()
    );
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
