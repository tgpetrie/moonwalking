import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock the context and hook so WatchlistPanel renders in isolation
vi.mock("../context/WatchlistContext.jsx", () => ({
  useWatchlist: vi.fn(),
}));
vi.mock("../hooks/useDataFeed", () => ({
  useDataFeed: vi.fn(),
}));
// TokenRowUnified imports rowCue / moveStatus — keep them real but mock coinbaseUrl
vi.mock("../utils/coinbaseUrl", () => ({
  coinbaseSpotUrl: () => "https://coinbase.com/trade/BTC",
}));
vi.mock("../context/IntelligenceContext.jsx", () => ({
  useIntelligence: () => ({ reports: {} }),
}));

import { useWatchlist } from "../context/WatchlistContext.jsx";
import { useDataFeed } from "../hooks/useDataFeed";
import WatchlistPanel from "./WatchlistPanel.jsx";

const noopDataFeed = {
  data: { data: { latest_by_symbol: {} } },
  lastGoodLatestBySymbol: {},
  getActiveAlert: () => null,
  getRecentAlerts: () => [],
};

function renderPanel() {
  return render(<WatchlistPanel />);
}

describe("WatchlistPanel — Since added label", () => {
  it("shows 'Since added' when a valid added-price baseline exists", async () => {
    const addedPrice = 100_000;
    const currentPrice = 112_400; // +12.4%

    useWatchlist.mockReturnValue({
      items: [{ symbol: "BTC", addedPrice, addedAt: Date.now() }],
      add: vi.fn(),
      toggle: vi.fn(),
    });
    useDataFeed.mockReturnValue({
      ...noopDataFeed,
      data: {
        data: {
          latest_by_symbol: {
            BTC: { symbol: "BTC", current_price: currentPrice },
          },
        },
      },
    });

    renderPanel();
    expect(await screen.findByText("Since added")).toBeInTheDocument();
  });

  it("does NOT show 'Since added' when the added-price baseline is missing", async () => {
    useWatchlist.mockReturnValue({
      items: [{ symbol: "BTC", addedPrice: null, addedAt: Date.now() }],
      add: vi.fn(),
      toggle: vi.fn(),
    });
    useDataFeed.mockReturnValue({
      ...noopDataFeed,
      data: {
        data: {
          latest_by_symbol: {
            BTC: { symbol: "BTC", current_price: 50_000 },
          },
        },
      },
    });

    renderPanel();
    // Wait for the symbol to appear then assert the label is absent
    expect(await screen.findByText("BTC")).toBeInTheDocument();
    expect(screen.queryByText("Since added")).not.toBeInTheDocument();
  });

  it("does NOT divide by zero when addedPrice is 0", async () => {
    useWatchlist.mockReturnValue({
      items: [{ symbol: "ETH", addedPrice: 0, addedAt: Date.now() }],
      add: vi.fn(),
      toggle: vi.fn(),
    });
    useDataFeed.mockReturnValue({
      ...noopDataFeed,
      data: {
        data: {
          latest_by_symbol: {
            ETH: { symbol: "ETH", current_price: 2500 },
          },
        },
      },
    });

    renderPanel();
    expect(await screen.findByText("ETH")).toBeInTheDocument();
    // No "Since added" because addedPrice=0 is treated as missing baseline
    expect(screen.queryByText("Since added")).not.toBeInTheDocument();
  });

  it("renders a negative change correctly without crashing", async () => {
    useWatchlist.mockReturnValue({
      items: [{ symbol: "SOL", addedPrice: 200, addedAt: Date.now() }],
      add: vi.fn(),
      toggle: vi.fn(),
    });
    useDataFeed.mockReturnValue({
      ...noopDataFeed,
      data: {
        data: {
          latest_by_symbol: {
            SOL: { symbol: "SOL", current_price: 180 }, // -10%
          },
        },
      },
    });

    renderPanel();
    expect(await screen.findByText("Since added")).toBeInTheDocument();
    // The change value should be negative (rendered as a negative formatted pct)
    const changeEl = document.querySelector(".bh-change-neg");
    expect(changeEl).toBeInTheDocument();
  });

  it("shows current price for a tiny coin (not $0)", async () => {
    useWatchlist.mockReturnValue({
      items: [{ symbol: "IMU", addedPrice: 0.002, addedAt: Date.now() }],
      add: vi.fn(),
      toggle: vi.fn(),
    });
    useDataFeed.mockReturnValue({
      ...noopDataFeed,
      data: {
        data: {
          latest_by_symbol: {
            IMU: { symbol: "IMU", current_price: 0.00226 },
          },
        },
      },
    });

    renderPanel();
    expect(await screen.findByText("$0.00226")).toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("shows empty list when watchlist has no items", async () => {
    useWatchlist.mockReturnValue({
      items: [],
      add: vi.fn(),
      toggle: vi.fn(),
    });
    useDataFeed.mockReturnValue(noopDataFeed);

    renderPanel();
    expect(await screen.findByText(/star a token/i)).toBeInTheDocument();
  });
});
