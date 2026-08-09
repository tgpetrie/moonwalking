import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// The legacy market feed is a large context-driven component; stub it so this
// suite proves *routing and preservation*, not AlertsTab's own internals.
vi.mock("./AlertsTab", () => ({
  default: ({ compact, onOpenCoinSentiment }) => (
    <div data-testid="legacy-alerts-tab" data-compact={String(compact)}>
      {["All", "Watchlist", "Moonshot", "Bullish", "Heating Up", "Whale", "Dump",
        "Breakout", "Liq Shock"].map((f) => (
        <button key={f} type="button">{f}</button>
      ))}
      <button
        type="button"
        onClick={() =>
          onOpenCoinSentiment?.("SOL", {
            source: "alerts_center",
            alert: {
              id: "alert_1",
              symbol: "SOL",
              type_key: "BREAKOUT",
              evidence: { window: "3m", price: 148.2 },
            },
          })
        }
      >
        open-chart
      </button>
    </div>
  ),
}));

// For You reads app contexts internally; stub it so host tests stay focused
// on routing, defaults, and the alert-intent contract.
vi.mock("./alerts/ForYouTab.jsx", () => ({
  default: ({ recommendations, onSetAlertFor }) => (
    <div data-testid="foryou-tab">
      {(recommendations || []).map((r) => (
        <span key={r.id}>{r.symbol}</span>
      ))}
      <button type="button" onClick={() => onSetAlertFor?.("SOL")}>
        stub-set-alert
      </button>
    </div>
  ),
}));

vi.mock("./alerts/alertRulesApi.js", () => ({
  listRules: vi.fn().mockResolvedValue([]),
  createRule: vi.fn(),
  pauseRule: vi.fn(),
  resumeRule: vi.fn(),
  deleteRule: vi.fn(),
  listRecommendations: vi.fn().mockResolvedValue([]),
  acceptRecommendation: vi.fn(),
  dismissRecommendation: vi.fn(),
  listHistory: vi.fn().mockResolvedValue([]),
}));

import * as api from "./alerts/alertRulesApi.js";
import AlertsPanelGlobal from "./AlertsPanelGlobal.jsx";

const open = (props = {}) =>
  render(<AlertsPanelGlobal isOpen onClose={() => {}} {...props} />);

beforeEach(() => {
  vi.clearAllMocks();
  api.listRules.mockResolvedValue([]);
  api.listRecommendations.mockResolvedValue([]);
  api.listHistory.mockResolvedValue([]);
});

describe("AlertsPanelGlobal", () => {
  it("exposes the four sections: For You, Active, History, Market Feed", () => {
    open();
    for (const label of ["For You", "Active", "History", "Market Feed"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument();
    }
    // Recommendations are events inside For You now, not a destination.
    expect(screen.queryByRole("tab", { name: "Recommended" })).not.toBeInTheDocument();
  });

  it("preserves the legacy market feed with all nine filters", async () => {
    open();
    fireEvent.click(screen.getByRole("tab", { name: "Market Feed" }));

    const feed = await screen.findByTestId("legacy-alerts-tab");
    expect(feed).toBeInTheDocument();
    expect(feed).toHaveAttribute("data-compact", "false");

    for (const filter of ["All", "Watchlist", "Moonshot", "Bullish", "Heating Up",
                          "Whale", "Dump", "Breakout", "Liq Shock"]) {
      expect(screen.getByRole("button", { name: filter })).toBeInTheDocument();
    }
  });

  it("forwards alert launch context from the market feed", async () => {
    const onOpenCoinSentiment = vi.fn();
    open({ onOpenCoinSentiment });
    fireEvent.click(screen.getByRole("tab", { name: "Market Feed" }));

    await screen.findByTestId("legacy-alerts-tab");
    fireEvent.click(screen.getByRole("button", { name: "open-chart" }));

    expect(onOpenCoinSentiment).toHaveBeenCalledWith("SOL", {
      source: "alerts_center",
      alert: {
        id: "alert_1",
        symbol: "SOL",
        type_key: "BREAKOUT",
        evidence: { window: "3m", price: 148.2 },
      },
    });
  });

  it("defaults to Market Feed when there are no recommendations", async () => {
    open();
    await waitFor(() => expect(api.listRecommendations).toHaveBeenCalled());
    expect(screen.getByRole("tab", { name: "Market Feed" })).toHaveAttribute(
      "aria-selected", "true"
    );
    expect(await screen.findByTestId("legacy-alerts-tab")).toBeInTheDocument();
  });

  it("defaults to Market Feed when the user is signed out", async () => {
    api.listRecommendations.mockRejectedValue(
      Object.assign(new Error("Sign in"), { isAuthRequired: true, status: 401 })
    );
    open();
    await waitFor(() => expect(api.listRecommendations).toHaveBeenCalled());
    expect(screen.getByRole("tab", { name: "Market Feed" })).toHaveAttribute(
      "aria-selected", "true"
    );
  });

  it("leads with For You when suggestions exist", async () => {
    api.listRecommendations.mockResolvedValue([
      { id: "rec_1", symbol: "ETH", basis: "portfolio", reason: "Because ETH…" },
    ]);
    open();
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "For You" })).toHaveAttribute(
        "aria-selected", "true"
      )
    );
    expect(await screen.findByTestId("foryou-tab")).toBeInTheDocument();
  });

  it("routes a Set-alert intent to the Active tab with the builder prefilled", async () => {
    api.listRecommendations.mockResolvedValue([
      { id: "rec_1", symbol: "ETH", basis: "portfolio", reason: "Because ETH…" },
    ]);
    open();
    await screen.findByTestId("foryou-tab");

    fireEvent.click(screen.getByRole("button", { name: "stub-set-alert" }));

    expect(screen.getByRole("tab", { name: "Active" })).toHaveAttribute(
      "aria-selected", "true"
    );
    // Builder opens automatically, prefilled with the intent's symbol only —
    // the intelligence layer never touches builder internals.
    expect(await screen.findByLabelText("Coin")).toHaveValue("SOL");
  });

  it("does not fetch history until that tab is opened", async () => {
    open();
    await waitFor(() => expect(api.listRecommendations).toHaveBeenCalled());
    expect(api.listHistory).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    await waitFor(() => expect(api.listHistory).toHaveBeenCalledTimes(1));
  });

  it("opening Market Feed costs no rule API calls", async () => {
    open();
    await waitFor(() => expect(api.listRecommendations).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("tab", { name: "Market Feed" }));
    await screen.findByTestId("legacy-alerts-tab");
    expect(api.listRules).not.toHaveBeenCalled();
    expect(api.listHistory).not.toHaveBeenCalled();
  });

  it("switches between new tabs and back to the legacy feed", async () => {
    open();
    fireEvent.click(screen.getByRole("tab", { name: "Active" }));
    expect(await screen.findByRole("button", { name: "New alert" })).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-alerts-tab")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Market Feed" }));
    expect(await screen.findByTestId("legacy-alerts-tab")).toBeInTheDocument();
  });

  it("keeps the Alerts Center title and closes on Escape", () => {
    const onClose = vi.fn();
    open({ onClose });
    expect(screen.getByRole("heading", { name: "Alerts Center" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <AlertsPanelGlobal isOpen={false} onClose={() => {}} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
