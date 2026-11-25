import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const NOW = 1_800_000_000_000;

// Each test mutates these between renders to simulate DataContext polls.
const mock = vi.hoisted(() => ({
  data: {},
  watched: new Set(),
}));

vi.mock("../context/DataContext", () => ({ useData: () => mock.data }));
vi.mock("../context/WatchlistContext.jsx", () => ({
  useWatchlist: () => ({
    items: [...mock.watched].map((symbol) => ({ symbol })),
    has: (symbol) => mock.watched.has(String(symbol || "").toUpperCase()),
    toggle: vi.fn(),
  }),
}));

import AlertsTab from "./AlertsTab.jsx";

const signal = (overrides = {}) => ({
  id: "btc-breakout",
  symbol: "BTC-USD",
  type_key: "breakout",
  primary_state: "Breakout",
  severity: "high",
  ts_ms: NOW - 30_000,
  expires_at: new Date(NOW + 5 * 60_000).toISOString(),
  message: "BTC broke out",
  evidence: { pct_1m: 1.4, volume_change_1h_pct: 40, streak: 2 },
  ...overrides,
});

const payload = (alerts) => ({
  activeAlerts: alerts,
  alertsRecent: alerts,
  pulseAlerts: alerts,
  signalEvents: alerts,
  alertsMeta: { fallback_from_data: false },
  latestBySymbol: {},
});

const sectionOrder = () => {
  const evolving = screen.getByRole("region", { name: "Evolving events" });
  const watchlist = screen.getByRole("region", { name: "Watchlist attention" });
  // DOCUMENT_POSITION_FOLLOWING: watchlist comes after evolving in the DOM.
  return evolving.compareDocumentPosition(watchlist) & Node.DOCUMENT_POSITION_FOLLOWING
    ? "evolving-first"
    : "watchlist-first";
};

describe("AlertsTab sections", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    mock.data = {};
    mock.watched = new Set();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows loading, not empty copy, before the first alerts payload", () => {
    mock.watched = new Set(["ETH"]);
    render(<AlertsTab />);

    expect(screen.getByText("Loading live tape…")).toBeInTheDocument();
    expect(screen.getAllByText("Loading signals…").length).toBeGreaterThan(0);
    expect(screen.queryByText("No dominant live setup right now.")).not.toBeInTheDocument();
    expect(screen.queryByText("No evolving signals right now.")).not.toBeInTheDocument();
    expect(screen.queryByText("No active watchlist alerts right now")).not.toBeInTheDocument();
  });

  it("switches to the empty copy once a payload with no signals arrives", () => {
    const { rerender } = render(<AlertsTab />);
    mock.data = payload([]);
    rerender(<AlertsTab />);

    expect(screen.queryByText("Loading live tape…")).not.toBeInTheDocument();
    expect(screen.queryByText("Loading signals…")).not.toBeInTheDocument();
    expect(screen.getByText("No dominant live setup right now.")).toBeInTheDocument();
  });

  it("puts EVOLVING above an empty WATCHLIST and keeps that order on later polls", () => {
    const { rerender } = render(<AlertsTab />);

    // First payload: live signals, nothing watched -> evolving first.
    mock.data = payload([signal()]);
    rerender(<AlertsTab />);
    expect(sectionOrder()).toBe("evolving-first");

    // Later poll: BTC is now watched and has a live alert. The watchlist gains
    // attention rows, but the order was frozen at first load and must not jump.
    mock.watched = new Set(["BTC"]);
    mock.data = payload([signal({ id: "btc-breakout-2", ts_ms: NOW - 5_000 })]);
    rerender(<AlertsTab />);

    expect(screen.getByRole("region", { name: "Watchlist attention" })).toHaveTextContent("1 live");
    expect(sectionOrder()).toBe("evolving-first");
  });

  it("puts WATCHLIST first when it has attention at first load", () => {
    mock.watched = new Set(["BTC"]);
    const { rerender } = render(<AlertsTab />);
    mock.data = payload([signal()]);
    rerender(<AlertsTab />);

    expect(sectionOrder()).toBe("watchlist-first");
  });
});
