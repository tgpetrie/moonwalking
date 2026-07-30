import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import IntelligenceFeed from "../IntelligenceFeed.jsx";
import { IntelligenceFeedError } from "../intelligenceFeedClient.js";

const feedPayload = {
  count: 1,
  events: [
    {
      event_id: "event-1",
      event_type: "PORTFOLIO_CHANGE_INTELLIGENCE",
      status: "detected",
      observed_at: "2026-07-26T12:00:00Z",
      headline: "Portfolio up 19.05% over the 12 hours — driven by SOL",
      what_changed: {
        reasons: [
          { type: "asset_contribution", asset_symbol: "SOL", magnitude_pct: 19.05, direction: "up" },
        ],
        total_change_pct: 19.05,
        total_change_usd: 40,
      },
      affected_assets: ["SOL"],
      portfolio_impact: {
        previous_total_usd: 210,
        current_total_usd: 250,
        change_usd: 40,
        change_pct: 19.05,
      },
      supporting_metrics: {
        biggest_movers: [
          { asset_symbol: "SOL", value_delta_usd: 40, contribution_pct: 19.05 },
        ],
        allocation_changes: [],
      },
      confidence: { level: "deterministic", source: "portfolio_change_intelligence" },
      evidence: { packet_id: "portfolio-change-abc", available: true },
      explanation: null,
    },
  ],
};

const fetcherFor = (payload) => vi.fn(async () => payload);

describe("IntelligenceFeed", () => {
  it("renders what changed, the asset, impact, timestamp and confidence", async () => {
    render(<IntelligenceFeed fetcher={fetcherFor(feedPayload)} />);

    expect(
      await screen.findByText(/Portfolio up 19.05% over the 12 hours/)
    ).toBeInTheDocument();
    expect(screen.getByText("SOL")).toBeInTheDocument();
    expect(screen.getByText("+19.05%")).toBeInTheDocument();
    expect(screen.getByText("+$40.00")).toBeInTheDocument();
    expect(screen.getByText("+$210.00 → +$250.00")).toBeInTheDocument();
    expect(
      screen.getByText(/SOL moved 19.05% of your portfolio value up/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Measured/)).toBeInTheDocument();
  });

  it("shows an explicit empty state rather than a blank panel", async () => {
    render(<IntelligenceFeed fetcher={fetcherFor({ events: [] })} />);
    expect(
      await screen.findByText(/Nothing material changed since your last snapshot/)
    ).toBeInTheDocument();
  });

  it("asks the user to sign in when unauthorized", async () => {
    const fetcher = vi.fn(async () => {
      throw new IntelligenceFeedError("unauthorized", "Authentication required.");
    });
    render(<IntelligenceFeed fetcher={fetcher} />);
    expect(
      await screen.findByText(/Sign in to see what changed/)
    ).toBeInTheDocument();
  });

  it("degrades without claiming nothing happened when the backend fails", async () => {
    const fetcher = vi.fn(async () => {
      throw new IntelligenceFeedError("network_failure", "boom");
    });
    render(<IntelligenceFeed fetcher={fetcher} />);
    expect(
      await screen.findByText(/Intelligence is temporarily unavailable/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Nothing material changed/)).not.toBeInTheDocument();
  });

  it("removes an event from the feed when dismissed", async () => {
    const statusSetter = vi.fn(async () => ({ status: "dismissed" }));
    render(
      <IntelligenceFeed fetcher={fetcherFor(feedPayload)} statusSetter={statusSetter} />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(screen.queryByTestId("intelligence-event")).not.toBeInTheDocument()
    );
    expect(statusSetter).toHaveBeenCalledWith("event-1", "dismissed");
  });

  it("keeps the event visible when the dismiss request fails", async () => {
    const statusSetter = vi.fn(async () => {
      throw new IntelligenceFeedError("network_failure", "boom");
    });
    render(
      <IntelligenceFeed fetcher={fetcherFor(feedPayload)} statusSetter={statusSetter} />
    );

    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(statusSetter).toHaveBeenCalled());
    expect(screen.getByTestId("intelligence-event")).toBeInTheDocument();
  });
});
