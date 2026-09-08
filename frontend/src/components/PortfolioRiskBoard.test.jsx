import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PortfolioRiskBoard from "./PortfolioRiskBoard.jsx";

vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));
vi.mock("../context/WatchlistContext.jsx", () => ({ readGuestItems: () => [{ symbol: "BTC" }, { symbol: "ETH" }] }));

const row = {
  product_id: "BTC-USD", symbol: "BTC", quantity: 2, price_usd: 100,
  market_value_usd: 200, status: "high", distance_to_stop_pct: 5.4,
  distance_to_resistance_pct: 12, capital_to_stop_usd: 10.8,
  plan: {
    available: true, product_id: "BTC-USD", current_price: 100,
    price_as_of: Math.floor(Date.now() / 1000),
    top_signal: { status: "high", label: "Protect now", reasons: ["Hourly momentum is fading."] },
    market_structure: { range_position_pct: 60, support: 95, resistance: 112 },
    stop: { trigger_price: 94.6, limit_price: 94.3, invalidation_price: 95, trigger_source: "volatility_reference", structural_actionable: false, why: ["A buffer below support."] },
    profit: { first_trim_price: 112 },
    chart: { candles: [[1000, 95, 105, 99, 100, 10], [4600, 94, 106, 100, 102, 11], [8200, 96, 108, 102, 103, 12]], granularity_seconds: 3600, last_close_at: 11800 },
  },
};
const unavailable = { product_id: "ETH-USD", symbol: "ETH", quantity: 1, price_usd: null, status: "unavailable", plan: { available: false, reason: "Not enough completed candle history yet, or history is still loading." } };
function payload(overrides = {}) {
  return { source: "portfolio", updated_at: 1800000000, rows: [row, unavailable], summary: { counts: { high: 1, unavailable: 1 }, capital_to_stop_usd: 10.8, sized_plan_count: 1, excluded_symbols: ["ETH"], breached_symbols: [] }, ...overrides };
}
function respond(body) { return Promise.resolve({ ok: true, json: async () => body }); }
afterEach(() => vi.unstubAllGlobals());

describe("Portfolio Risk Board", () => {
  it("shows real sizes and separately names positions excluded from the dollar total", async () => {
    const fetcher = vi.fn(() => respond(payload()));
    vi.stubGlobal("fetch", fetcher);
    render(<PortfolioRiskBoard />);
    await screen.findByRole("article", { name: "BTC risk levels" });
    const summary = screen.getByRole("region", { name: "Risk summary" });
    expect(within(summary).getByText("$10.80")).toBeInTheDocument();
    expect(within(summary).getByText(/Excluded from the dollar total: ETH/)).toBeInTheDocument();
    expect(screen.getByText("2 held · $200.00")).toBeInTheDocument();
    expect(screen.getByText("5.4% below current price")).toBeInTheDocument();
    expect(screen.getByText("Stop trigger (volatility-derived)")).toBeInTheDocument();
    expect(screen.getByText(/Wide stop distance — outside this board's actionable-distance convention/)).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "ETH risk levels" })).toHaveTextContent(/Not enough completed candle history/);
    expect(fetcher.mock.calls[0][0]).toContain("symbols=BTC%2CETH");
    expect(fetcher.mock.calls[0][1].credentials).toBe("include");
  });

  it("expands the existing interactive chart in place and collapses it", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(payload())));
    render(<PortfolioRiskBoard />);
    const expand = await screen.findByRole("button", { name: "Explore levels" });
    fireEvent.click(expand);
    expect(screen.getByRole("button", { name: "Hide chart" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /^Suggested stop trigger/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Suggested sell limit/ }));
    expect(screen.getByRole("heading", { name: /Suggested sell limit \(uncalibrated\)/ })).toBeInTheDocument();
    expect(screen.getByText(/uncalibrated legacy placeholder/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hide chart" }));
    expect(screen.queryByRole("button", { name: /^Suggested sell limit/ })).not.toBeInTheDocument();
  });

  it("labels watchlist fallback and never implies an unknown position has zero risk", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(payload({ source: "watchlist", fallback_reason: "Showing your saved watchlist without position sizes.", rows: [{ ...row, quantity: null, market_value_usd: null, capital_to_stop_usd: null }], summary: { counts: { high: 1 }, capital_to_stop_usd: null, sized_plan_count: 0, excluded_symbols: [] } }))));
    render(<PortfolioRiskBoard />);
    expect(await screen.findByText("Position sizes needed")).toBeInTheDocument();
    expect(screen.getByText("Watchlist coin · position size unknown")).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("preserves the last snapshot with a stale label after refresh fails", async () => {
    const fetcher = vi.fn().mockImplementationOnce(() => respond(payload())).mockResolvedValueOnce({ ok: false, status: 503 });
    vi.stubGlobal("fetch", fetcher);
    render(<PortfolioRiskBoard />);
    await screen.findByRole("article", { name: "BTC risk levels" });
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/Showing the last snapshot; it may be stale/));
    expect(screen.getByRole("article", { name: "BTC risk levels" })).toBeInTheDocument();
    expect(fetcher.mock.calls[1][0]).toContain("refresh=1");
  });

  it("shows an actionable empty guest watchlist without creating sample holdings", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(payload({ source: "watchlist", rows: [], summary: { counts: {}, capital_to_stop_usd: null } }))));
    render(<PortfolioRiskBoard />);
    expect(await screen.findByRole("heading", { name: "No watchlist coins yet" })).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open live board" })).toHaveAttribute("href", "/");
  });
});
