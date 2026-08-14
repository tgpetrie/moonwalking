import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ScorecardCompareView, ScorecardVariantSwitch } from "./ScorecardCompare";

vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

const PAYLOAD = {
  status: "live",
  signals: {
    total_graded: 1500,
    overall_win_rate: 0.21,
    target_pct: 2.0,
    adverse_pct: 1.0,
    horizon_minutes: 60,
    signal_types: [
      {
        state: "Escalating",
        direction: "up",
        label: "STRONG_BUY",
        sample_size: 55,
        win_rate: 0.62,
        recent_win_rate: 0.58,
        recent_sample: 18,
        median_favorable_pct: 2.6,
        median_adverse_pct: -1.0,
        median_return: { "5m": 0.6, "15m": 0.9, "30m": 1.3, "60m": 1.9 },
      },
    ],
  },
  boards: {
    total_entries: 300,
    boards: {
      ignition_1m: {
        board: "ignition_1m",
        status: "measured",
        read: "No clear edge",
        sample_size: 150,
        matched_sample_size: 130,
        continuation_rate: 0.18,
        reversal_rate: 0.2,
        continuation_ci95: [0.12, 0.24],
        continuation_lift_vs_control: -0.02,
        median_directional_return: { "5m": -0.1, "15m": -0.2, "30m": 0.1, "60m": 0.3 },
      },
    },
  },
};

const LINKS = [
  { variant: "original", label: "Original", to: "/scorecard" },
  { variant: "redesign", label: "Redesign", to: "/scorecard-redesign" },
  { variant: "compare", label: "Side by side", to: "/scorecard-compare" },
];

// ---------------------------------------------------------------------------
// Variant switcher
// ---------------------------------------------------------------------------

describe("ScorecardVariantSwitch", () => {
  it("renders every variant and marks the current one", () => {
    render(<ScorecardVariantSwitch variant="redesign" links={LINKS} navigate={() => {}} />);

    const nav = screen.getByRole("navigation", { name: "Scorecard version" });
    expect(within(nav).getByText("Original")).toBeInTheDocument();
    expect(within(nav).getByText("Redesign")).toBeInTheDocument();
    expect(within(nav).getByText("Side by side")).toBeInTheDocument();

    expect(within(nav).getByText("Redesign")).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByText("Original")).not.toHaveAttribute("aria-current");
  });

  it("navigates client-side instead of following the href", () => {
    const navigate = vi.fn();
    render(<ScorecardVariantSwitch variant="original" links={LINKS} navigate={navigate} />);

    const link = screen.getByText("Redesign");
    const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
    link.dispatchEvent(event);

    expect(navigate).toHaveBeenCalledWith("/scorecard-redesign");
    expect(event.defaultPrevented).toBe(true);
  });

  it("leaves modified clicks to the browser so links still open in a new tab", () => {
    const navigate = vi.fn();
    render(<ScorecardVariantSwitch variant="original" links={LINKS} navigate={navigate} />);

    fireEvent.click(screen.getByText("Redesign"), { metaKey: true });
    expect(navigate).not.toHaveBeenCalled();
  });

  it("keeps a real href on every variant so links are shareable", () => {
    render(<ScorecardVariantSwitch variant="compare" links={LINKS} navigate={() => {}} />);
    expect(screen.getByText("Original")).toHaveAttribute("href", "/scorecard");
    expect(screen.getByText("Redesign")).toHaveAttribute("href", "/scorecard-redesign");
    expect(screen.getByText("Side by side")).toHaveAttribute("href", "/scorecard-compare");
  });
});

// ---------------------------------------------------------------------------
// Side-by-side view
// ---------------------------------------------------------------------------

describe("ScorecardCompareView", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(PAYLOAD),
    });
  });

  it("mounts both the original page and the redesign", async () => {
    const { container } = render(<ScorecardCompareView />);

    await waitFor(() => expect(container.querySelector(".sc-page")).toBeTruthy());
    await waitFor(() => expect(container.querySelector(".scr-page")).toBeTruthy());

    // Baseline hero and redesign hero are both present and distinct.
    expect(container.querySelector(".sc-hero__title").textContent).toBe("Outcome Scorecard");
    expect(container.querySelector(".scr-hero__coin").textContent).toBe("BTC");
  });

  it("labels which pane is which, original first", async () => {
    const { container } = render(<ScorecardCompareView />);
    await waitFor(() => expect(container.querySelectorAll(".scr-compare__pane").length).toBe(2));

    const titles = [...container.querySelectorAll(".scr-compare__pane-title")].map(
      (el) => el.textContent
    );
    expect(titles).toEqual(["Original", "Redesign"]);
  });

  it("says both panes read the same data", async () => {
    render(<ScorecardCompareView />);
    await waitFor(() =>
      expect(screen.getByText(/Both versions read the same live data/i)).toBeInTheDocument()
    );
  });

  it("passes preview mode down to both panes", async () => {
    // Preview mode must not error out even when the network is unavailable.
    global.fetch = vi.fn().mockRejectedValue(new Error("offline"));
    const { container } = render(<ScorecardCompareView previewMode />);

    await waitFor(() => expect(container.querySelector(".scr-page")).toBeTruthy());
    expect(container.querySelector(".scr-hero__source").textContent).toBe("Preview data");
    expect(container.querySelector(".sc-page")).toBeTruthy();
    expect(screen.queryByText(/Failed to load scorecard/i)).not.toBeInTheDocument();
  });
});
