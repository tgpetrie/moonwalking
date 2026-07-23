import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MarketPositioningStatus, {
  describeFundingBias,
  exchangeStatuses,
} from "./MarketPositioningStatus.jsx";
import { buildMarketPositioning } from "../adapters/normalizeSentiment.js";

const LIVE_PAYLOAD = {
  live_exchanges: ["okx"],
  blocked_exchanges: ["binance", "bybit"],
  failed_exchanges: [],
  configured_exchanges: ["binance", "bybit", "okx"],
  stale: false,
  summary: {
    funding_bias: "neutral",
    live_exchange_count: 1,
    configured_exchange_count: 3,
    coverage_ratio: 0.333,
  },
};

describe("MarketPositioningStatus", () => {
  it("shows per-exchange status, funding bias, and coverage when live", () => {
    const positioning = buildMarketPositioning(LIVE_PAYLOAD);
    render(<MarketPositioningStatus positioning={positioning} />);

    const block = screen.getByText("Market positioning").closest(".mw-positioning");
    expect(block).toHaveAttribute("data-status", "LIVE");
    // Live exchange listed first, blocked ones flagged as blocked (not live).
    expect(block).toHaveTextContent("OKX live");
    expect(block).toHaveTextContent("Binance blocked");
    expect(block).toHaveTextContent("Bybit blocked");
    expect(screen.getByText("Neutral")).toBeInTheDocument();
    expect(screen.getByText("1/3 exchanges")).toBeInTheDocument();
  });

  it("renders 'Unavailable' and never 'live' when there are no live exchanges", () => {
    const positioning = buildMarketPositioning({
      live_exchanges: [],
      blocked_exchanges: ["binance", "bybit", "okx"],
      configured_exchanges: ["binance", "bybit", "okx"],
      summary: { funding_bias: "unknown" },
    });
    render(<MarketPositioningStatus positioning={positioning} />);

    const block = screen.getByText("Market positioning").closest(".mw-positioning");
    expect(block).toHaveAttribute("data-status", "UNAVAILABLE");
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(block.textContent.toLowerCase()).not.toContain("live");
  });

  it("renders 'Unavailable' when positioning is null (missing source)", () => {
    render(<MarketPositioningStatus positioning={null} />);
    const block = screen.getByText("Market positioning").closest(".mw-positioning");
    expect(block).toHaveAttribute("data-status", "UNAVAILABLE");
    expect(block.textContent.toLowerCase()).not.toContain(" live");
  });

  it("flags stale positioning without dropping the data", () => {
    const positioning = buildMarketPositioning({ ...LIVE_PAYLOAD, stale: true });
    render(<MarketPositioningStatus positioning={positioning} />);
    const block = screen.getByText("Market positioning").closest(".mw-positioning");
    expect(block).toHaveAttribute("data-status", "STALE");
    expect(block).toHaveTextContent("stale");
  });
});

describe("exchangeStatuses ordering", () => {
  it("lists live exchanges before blocked/failed ones", () => {
    const positioning = buildMarketPositioning(LIVE_PAYLOAD);
    const rows = exchangeStatuses(positioning);
    expect(rows[0]).toMatchObject({ id: "okx", state: "live" });
    expect(rows.map((r) => r.state)).toEqual(["live", "blocked", "blocked"]);
  });
});

describe("describeFundingBias", () => {
  it("maps backend enums to descriptive, non-directional copy", () => {
    expect(describeFundingBias("longs_pay")).toMatch(/long/i);
    expect(describeFundingBias("shorts_pay")).toMatch(/short/i);
    expect(describeFundingBias("neutral")).toBe("Neutral");
    expect(describeFundingBias("anything_else")).toBe("Unknown");
    expect(describeFundingBias(undefined)).toBe("Unknown");
  });
});
