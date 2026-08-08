import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RecommendedAlertsTab from "./RecommendedAlertsTab.jsx";
import ActiveRulesTab from "./ActiveRulesTab.jsx";
import AlertHistoryTab from "./AlertHistoryTab.jsx";

const REC = {
  id: "rec_1",
  symbol: "ETH",
  basis: "portfolio",
  trigger_type: "percent_move",
  params: { direction: "either", threshold: 8, window: "24h" },
  reason:
    "Because ETH is in your portfolio, Moonwalkings can notify you if it makes an unusually large move of 8% or more during a rolling 24-hour period.",
  status: "pending",
};

const RULE = {
  id: "rule_1",
  symbol: "BTC",
  trigger_type: "percent_move",
  params: { direction: "up", threshold: 5, window: "24h" },
  repeat_mode: "recurring",
  status: "cooling_down",
  source: "manual",
  armed: false,
  arm_cycle: 3,
  reset_pct: 1.0,
  percent_rearm_ratio: 0.75,
  pending_since_ts: null,
};

const EVENT = {
  id: "evt_1",
  rule_id: "rule_1",
  symbol: "BTC",
  event_type: "price_cross",
  observed_value: 115.5,
  boundary_value: 110,
  triggered_ts: Math.floor(Date.now() / 1000) - 600,
  explanation:
    "BTC rose above $110.00, reaching $115.50. You created this alert. This alert stays active.",
  // Fake event fingerprint for the fixture, not a credential.
  fingerprint: "abc123def456", // pragma: allowlist secret
};

const noop = () => {};
const base = { loading: false, error: null, authRequired: false, onLoad: noop };

describe("RecommendedAlertsTab", () => {
  it("explains why each suggestion appears", () => {
    render(
      <RecommendedAlertsTab
        {...base}
        recommendations={[REC]}
        onAccept={noop}
        onDismiss={noop}
      />
    );
    expect(screen.getByText("ETH")).toBeInTheDocument();
    expect(screen.getByText("In your portfolio")).toBeInTheDocument();
    expect(screen.getByText(/Because ETH is in your portfolio/)).toBeInTheDocument();
  });

  it("never auto-enables a suggestion on mount", () => {
    const onAccept = vi.fn();
    render(
      <RecommendedAlertsTab
        {...base}
        recommendations={[REC]}
        onAccept={onAccept}
        onDismiss={noop}
      />
    );
    expect(onAccept).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Enable" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("enables only on explicit click", async () => {
    const onAccept = vi.fn().mockResolvedValue({ id: "rule_x" });
    render(
      <RecommendedAlertsTab
        {...base}
        recommendations={[REC]}
        onAccept={onAccept}
        onDismiss={noop}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Enable" }));
    await waitFor(() => expect(onAccept).toHaveBeenCalledWith("rec_1"));
  });

  it("rolls back an optimistic dismiss when the server rejects it", async () => {
    // The parent owns the list; this asserts the child surfaces the failure
    // and does not swallow it, so the hook's rollback is visible to the user.
    const onDismiss = vi.fn().mockRejectedValue(new Error("Suggestion not found."));
    render(
      <RecommendedAlertsTab
        {...base}
        recommendations={[REC]}
        onAccept={noop}
        onDismiss={onDismiss}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(await screen.findByText("Suggestion not found.")).toBeInTheDocument();
    expect(screen.getByText("ETH")).toBeInTheDocument(); // card still present
  });

  it("shows a calm sign-in state, not an error", () => {
    render(
      <RecommendedAlertsTab
        {...base}
        authRequired
        recommendations={[]}
        onAccept={noop}
        onDismiss={noop}
      />
    );
    expect(screen.getByText("Sign in to use your own alerts")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("shows a useful empty state", () => {
    render(
      <RecommendedAlertsTab {...base} recommendations={[]} onAccept={noop} onDismiss={noop} />
    );
    expect(screen.getByText("No suggestions right now")).toBeInTheDocument();
  });
});

describe("ActiveRulesTab", () => {
  const activeBase = {
    ...base,
    onCreate: noop,
    onSetStatus: noop,
    onRemove: noop,
  };

  it("renders human-readable status, never raw enums", () => {
    const { container } = render(<ActiveRulesTab {...activeBase} rules={[RULE]} />);
    expect(screen.getByText("Waiting to reset")).toBeInTheDocument();
    expect(container.textContent).not.toContain("cooling_down");
    expect(container.textContent).not.toContain("percent_move");
  });

  it("describes the rule in plain language", () => {
    render(<ActiveRulesTab {...activeBase} rules={[RULE]} />);
    expect(
      screen.getByText("BTC moves up 5% during a rolling 24-hour period")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Notifies again after the market resets/)
    ).toBeInTheDocument();
  });

  it("never leaks internal machinery", () => {
    const { container } = render(<ActiveRulesTab {...activeBase} rules={[RULE]} />);
    const html = container.innerHTML;
    for (const hidden of [
      "arm_cycle",
      "fingerprint",
      "reset_pct",
      "percent_rearm_ratio",
      "pending_since_ts",
      "armed",
    ]) {
      expect(html).not.toContain(hidden);
    }
    // The numeric values of those fields must not surface either.
    expect(container.textContent).not.toContain("0.75");
  });

  it("offers pause and delete but no inline editing", () => {
    render(<ActiveRulesTab {...activeBase} rules={[RULE]} />);
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
  });

  it("shows Resume for a paused rule", () => {
    render(<ActiveRulesTab {...activeBase} rules={[{ ...RULE, status: "paused" }]} />);
    expect(screen.getByText("Paused")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  it("surfaces a failed pause inline", async () => {
    const onSetStatus = vi.fn().mockRejectedValue(new Error("Alert not found."));
    render(<ActiveRulesTab {...activeBase} rules={[RULE]} onSetStatus={onSetStatus} />);
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(await screen.findByText("Alert not found.")).toBeInTheDocument();
  });

  it("shows a pending confirmation hint without exposing the timestamp", () => {
    const { container } = render(
      <ActiveRulesTab
        {...activeBase}
        rules={[{ ...RULE, status: "active", pending_since_ts: 1800000000 }]}
      />
    );
    expect(container.textContent).toContain("Checking…");
    expect(container.textContent).not.toContain("1800000000");
  });

  it("keeps the builder collapsed until asked", () => {
    render(<ActiveRulesTab {...activeBase} rules={[]} />);
    expect(screen.queryByText("Alert me when")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "New alert" }));
    expect(screen.getByText("Alert me when")).toBeInTheDocument();
  });

  it("shows empty and signed-out states", () => {
    const { rerender } = render(<ActiveRulesTab {...activeBase} rules={[]} />);
    expect(screen.getByText("You have no alerts yet")).toBeInTheDocument();
    rerender(<ActiveRulesTab {...activeBase} authRequired rules={[]} />);
    expect(screen.getByText("Sign in to use your own alerts")).toBeInTheDocument();
  });
});

describe("AlertHistoryTab", () => {
  it("shows the fired price and the deterministic explanation", () => {
    render(<AlertHistoryTab {...base} events={[EVENT]} />);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText(/Reached \$115\.50/)).toBeInTheDocument();
    expect(screen.getByText(/BTC rose above \$110\.00/)).toBeInTheDocument();
  });

  it("shows when it fired", () => {
    render(<AlertHistoryTab {...base} events={[EVENT]} />);
    expect(screen.getByText("10m ago")).toBeInTheDocument();
  });

  it("contains no advice language", () => {
    const { container } = render(<AlertHistoryTab {...base} events={[EVENT]} />);
    const text = container.textContent.toLowerCase();
    for (const word of [" buy ", " sell ", " hold ", "stop loss", "take profit"]) {
      expect(text).not.toContain(word);
    }
  });

  it("shows empty and signed-out states", () => {
    const { rerender } = render(<AlertHistoryTab {...base} events={[]} />);
    expect(screen.getByText("Nothing has triggered yet")).toBeInTheDocument();
    rerender(<AlertHistoryTab {...base} authRequired events={[]} />);
    expect(screen.getByText("Sign in to use your own alerts")).toBeInTheDocument();
  });

  it("shows an error with a retry affordance", () => {
    render(<AlertHistoryTab {...base} error="Could not reach the server." events={[]} />);
    expect(screen.getByText("Could not reach the server.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
