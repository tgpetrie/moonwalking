import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PortfolioModePage from "./PortfolioModePage.jsx";
import { fetchPortfolio, fetchPortfolioMarketContext } from "./portfolioApi.js";

vi.mock("./portfolioApi.js", () => ({
  fetchPortfolio: vi.fn(),
  fetchPortfolioMarketContext: vi.fn(),
}));

describe("PortfolioModePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchPortfolioMarketContext.mockResolvedValue({ live_rankings: [] });
  });

  it("shows safe server-side setup guidance without a trading control", async () => {
    fetchPortfolio.mockRejectedValue({
      payload: {
        code: "portfolio_owner_not_configured",
        error: "Portfolio Mode owner access is not configured on this server.",
      },
    });

    render(<PortfolioModePage />);

    await waitFor(() => {
      expect(screen.getByText("Connect a View-only Coinbase portfolio")).toBeInTheDocument();
    });
    expect(screen.getByText("COINBASE_API_KEY_SECRET")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy|sell|trade|transfer/i })).not.toBeInTheDocument();
  });

  it("renders portfolio truth and live BHABIT holding state", async () => {
    fetchPortfolio.mockResolvedValue({
      status: "live",
      updated_at: "2026-07-18T01:00:00Z",
      summary: {
        total_value_usd: 400,
        cash_value_usd: 100,
        known_unrealized_pnl_usd: 98,
        cost_basis_coverage_pct: 100,
        open_order_count: 0,
      },
      holdings: [
        {
          account_id: "btc-account",
          symbol: "BTC",
          name: "BTC Wallet",
          quantity: 2,
          market_value_usd: 300,
          allocation_pct: 75,
          price_change_24h_pct: 3.2,
          unrealized_pnl_usd: 98,
          unrealized_pnl_pct: 48.5,
          is_cash: false,
          cost_basis: { status: "complete", average_price: 101 },
        },
        {
          account_id: "usd-account",
          symbol: "USD",
          name: "USD Wallet",
          quantity: 100,
          market_value_usd: 100,
          allocation_pct: 25,
          is_cash: true,
          cost_basis: { status: "not_applicable" },
        },
      ],
      open_orders: [],
    });
    fetchPortfolioMarketContext.mockResolvedValue({
      live_rankings: [
        {
          symbol: "BTC",
          live_score: 82,
          data_quality: 84,
          live_reasons: ["3m +1.20%", "spot buying"],
          live_risks: [],
        },
      ],
    });

    render(<PortfolioModePage />);

    await waitFor(() => {
      expect(screen.getByText("HOLD STRONG · 82")).toBeInTheDocument();
    });
    expect(screen.getByText("$400.00")).toBeInTheDocument();
    expect(screen.getByText("Highly concentrated")).toBeInTheDocument();
    expect(screen.getAllByText(/Not enough proof/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /buy|sell|trade|transfer/i })).not.toBeInTheDocument();
  });
});
