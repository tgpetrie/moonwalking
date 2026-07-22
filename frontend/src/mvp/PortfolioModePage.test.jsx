import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PortfolioModePage from "./PortfolioModePage.jsx";
import {
  fetchPortfolioIntel,
  fetchPortfolioMarketContext,
  fetchCoinbaseOAuthStatus,
} from "./portfolioApi.js";

vi.mock("./portfolioApi.js", () => ({
  fetchPortfolio: vi.fn(),
  fetchPortfolioIntel: vi.fn(),
  fetchPortfolioMarketContext: vi.fn(),
  fetchCoinbaseOAuthStatus: vi.fn(),
  coinbaseAuthorizeUrl: vi.fn(() => "/api/oauth/coinbase/authorize"),
  disconnectCoinbaseOAuth: vi.fn(),
}));

describe("PortfolioModePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchPortfolioMarketContext.mockResolvedValue({ live_rankings: [] });
    fetchCoinbaseOAuthStatus.mockResolvedValue({ connected: false });
  });

  it("offers the OAuth connect path without a trading control", async () => {
    fetchPortfolioIntel.mockRejectedValue({
      payload: {
        code: "portfolio_owner_not_configured",
        error: "Portfolio Mode owner access is not configured on this server.",
      },
    });

    render(<PortfolioModePage />);

    await waitFor(() => {
      expect(screen.getByText("Connect your Coinbase account")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /connect coinbase oauth/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy|sell|trade|transfer/i })).not.toBeInTheDocument();
  });

  it("renders portfolio truth and live BHABIT holding state", async () => {
    fetchPortfolioIntel.mockResolvedValue({
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

  it("renders position intelligence when the enriched snapshot provides it", async () => {
    fetchPortfolioIntel.mockResolvedValue({
      status: "live",
      updated_at: "2026-07-18T01:00:00Z",
      intel_available: true,
      summary: {
        total_value_usd: 300,
        cash_value_usd: 0,
        known_unrealized_pnl_usd: 50,
        cost_basis_coverage_pct: 100,
        open_order_count: 0,
      },
      intel_summary: {
        holdings_with_signals: 1,
        total_holdings: 1,
        signal_coverage_pct: 100,
      },
      holdings: [
        {
          account_id: "eth-account",
          symbol: "ETH",
          name: "ETH Wallet",
          quantity: 1,
          market_value_usd: 300,
          allocation_pct: 100,
          price_change_24h_pct: 2.0,
          unrealized_pnl_usd: 50,
          unrealized_pnl_pct: 20,
          is_cash: false,
          cost_basis: { status: "complete", average_price: 250 },
          intel: {
            posture: "momentum_favorable",
            signal: {
              state: "Confirmed",
              direction: "up",
              confidence: 72,
              short_read: "Confirmed upside momentum",
            },
            history: {
              follow_through_pct: 64,
              sample_size: 18,
              median_favorable_pct: 3.4,
            },
            board: { change_1m: 0.8, change_3m: 2.1, volume_change_1h_pct: 15 },
            active_alert_count: 1,
          },
        },
      ],
      open_orders: [],
    });

    render(<PortfolioModePage />);

    await waitFor(() => {
      expect(screen.getByText(/Momentum favorable · 72/)).toBeInTheDocument();
    });
    expect(screen.getByText("Confirmed upside momentum")).toBeInTheDocument();
    expect(screen.getByText(/across 18 comparable signals/)).toBeInTheDocument();
    expect(screen.getByText(/Signal coverage/)).toBeInTheDocument();
  });
});
