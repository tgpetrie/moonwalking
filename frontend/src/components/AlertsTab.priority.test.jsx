import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const NOW = 1_800_000_000_000;

const liveAlert = (overrides = {}) => ({
  id: "btc-moonshot",
  symbol: "BTC-USD",
  type_key: "moonshot",
  primary_state: "Moonwalking",
  severity: "high",
  ts_ms: NOW - 30_000,
  expires_at: new Date(NOW + 5 * 60_000).toISOString(),
  message: "BTC moved +2.0% in 1m",
  evidence: { pct_1m: 2, volume_change_1h_pct: 50, streak: 3 },
  ...overrides,
});

const alerts = [
  liveAlert(),
  liveAlert({
    id: "btc-breakout",
    type_key: "breakout",
    primary_state: "Breakout",
    severity: "low",
    ts_ms: NOW - 60_000,
    message: "BTC broke out",
    evidence: { pct_1m: 1, volume_change_1h_pct: 20, streak: 2 },
  }),
  liveAlert({
    id: "eth-dump",
    symbol: "ETH-USD",
    type_key: "dump",
    primary_state: "Building",
    severity: "medium",
    message: "ETH moved down",
    evidence: { pct_1m: -1, volume_change_1h_pct: 15, streak: 1 },
  }),
];

const dashboardData = {
  activeAlerts: alerts,
  alertsRecent: alerts,
  pulseAlerts: alerts,
  signalEvents: alerts,
  alertsMeta: {
    fallback_from_data: false,
    market_pressure: { index: 60, breadth_up: 0.7, breadth_down: 0.3 },
  },
  latestBySymbol: {},
  gainers_1m: [{ symbol: "BTC-USD", rank: 2 }],
  gainers_3m: [{ symbol: "BTC-USD", rank: 3 }],
  losers_3m: [{ symbol: "ETH-USD", rank: 1 }],
  market_pressure: { index: 60, breadth_up: 0.7, breadth_down: 0.3 },
};

vi.mock("../context/DataContext", () => ({ useData: () => dashboardData }));
vi.mock("../context/WatchlistContext.jsx", () => ({
  useWatchlist: () => ({ items: [], has: () => false, toggle: vi.fn() }),
}));

import AlertsTab from "./AlertsTab.jsx";

const prioritySnapshot = () => {
  const region = screen.getByRole("region", { name: "Hot right now" });
  const row = within(region).getByText("BTC").closest("button");
  return {
    label: row.querySelector(".bh-priority-row__label")?.textContent,
    score: row.querySelector(".bh-priority-row__score")?.textContent,
  };
};

describe("AlertsTab priority semantics", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps priority state stable while display filters change visible rows", () => {
    const { container } = render(<AlertsTab />);
    const baseline = prioritySnapshot();
    const controls = container.querySelectorAll(".bh-control-select");

    expect(container.querySelectorAll(".bh-signal-row")).toHaveLength(3);

    fireEvent.change(controls[0], { target: { value: "LOW" } });
    expect(container.querySelectorAll(".bh-signal-row")).toHaveLength(1);
    expect(prioritySnapshot()).toEqual(baseline);

    fireEvent.change(controls[0], { target: { value: "ALL" } });
    fireEvent.click(screen.getByRole("button", { name: "Dump" }));
    expect(container.querySelectorAll(".bh-signal-row")).toHaveLength(1);
    expect(prioritySnapshot()).toEqual(baseline);

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    fireEvent.change(controls[2], { target: { value: "ETH" } });
    expect(container.querySelectorAll(".bh-signal-row")).toHaveLength(1);
    expect(prioritySnapshot()).toEqual(baseline);

    fireEvent.click(screen.getByRole("button", { name: "Watchlist" }));
    expect(container.querySelectorAll(".bh-signal-row")).toHaveLength(0);
    expect(prioritySnapshot()).toEqual(baseline);
  });
});
