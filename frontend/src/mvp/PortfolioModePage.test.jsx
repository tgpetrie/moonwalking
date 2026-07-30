import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PortfolioModePage from "./PortfolioModePage.jsx";
import {
  fetchPortfolioIntel,
  fetchPortfolioMarketContext,
  fetchCoinbaseOAuthStatus,
  saveManualCostBasis,
} from "./portfolioApi.js";

vi.mock("./portfolioApi.js", () => ({
  fetchPortfolio: vi.fn(),
  fetchPortfolioIntel: vi.fn(),
  fetchPortfolioMarketContext: vi.fn(),
  fetchCoinbaseOAuthStatus: vi.fn(),
  coinbaseAuthorizeUrl: vi.fn(() => "/api/oauth/coinbase/authorize"),
  disconnectCoinbaseOAuth: vi.fn(),
  saveManualCostBasis: vi.fn(),
  deleteManualCostBasis: vi.fn(),
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
    // With no comparable-outcome history, the graded gate reads "No history yet".
    expect(screen.getAllByText(/No history yet/i).length).toBeGreaterThan(0);
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
    // 18 comparable outcomes -> "Building" tier (shown on the intel badge and
    // the Historical-plan cell), and the rate is quotable.
    expect(screen.getAllByText("Building · 18").length).toBeGreaterThan(0);
    expect(screen.getByText(/Follow-through/)).toBeInTheDocument();
    expect(screen.getByText(/Signal coverage/)).toBeInTheDocument();
  });

  it("renders a descriptive 24h read for holdings with no live signal", async () => {
    fetchPortfolioIntel.mockResolvedValue({
      status: "live",
      updated_at: "2026-07-18T01:00:00Z",
      intel_available: true,
      summary: {
        total_value_usd: 100,
        cash_value_usd: 0,
        known_unrealized_pnl_usd: 0,
        cost_basis_coverage_pct: 0,
        open_order_count: 0,
      },
      intel_summary: {
        holdings_with_signals: 0,
        holdings_with_read: 1,
        total_holdings: 1,
        signal_coverage_pct: 0,
        read_coverage_pct: 100,
      },
      holdings: [
        {
          account_id: "arx-account",
          symbol: "ARX",
          name: "ARX Wallet",
          quantity: 1000,
          market_value_usd: 100,
          allocation_pct: 100,
          price_change_24h_pct: 4.2,
          is_cash: false,
          cost_basis: { status: "partial" },
          intel: {
            posture: "descriptive_up",
            read_source: "descriptive",
            read: {
              short: "Up +4.20% over 24h.",
              label: "Up today",
              tone: "positive",
              change_24h_pct: 4.2,
              horizon: "24h",
              source: "descriptive",
            },
          },
        },
      ],
      open_orders: [],
    });

    render(<PortfolioModePage />);

    await waitFor(() => {
      expect(screen.getByText("Up today")).toBeInTheDocument();
    });
    // Descriptive reads are visibly marked as not-a-signal.
    expect(screen.getByText("24h price read")).toBeInTheDocument();
    expect(screen.getByText("Up +4.20% over 24h.")).toBeInTheDocument();
    // Signal coverage stays pure; a separate read-coverage figure is shown.
    expect(screen.getByText(/Signal coverage 0\.00%/)).toBeInTheDocument();
    expect(screen.getByText(/reads 100\.00%/)).toBeInTheDocument();
  });

  it("lets the owner enter manual cost basis on a partial holding", async () => {
    saveManualCostBasis.mockResolvedValue({ status: "saved" });
    fetchPortfolioIntel.mockResolvedValue({
      status: "live",
      updated_at: "2026-07-18T01:00:00Z",
      intel_available: true,
      summary: {
        total_value_usd: 500,
        cash_value_usd: 0,
        known_unrealized_pnl_usd: 0,
        cost_basis_coverage_pct: 0,
        open_order_count: 0,
      },
      holdings: [
        {
          account_id: "ada-account",
          symbol: "ADA",
          name: "ADA Wallet",
          quantity: 1000,
          market_value_usd: 500,
          allocation_pct: 100,
          price_change_24h_pct: 1.0,
          is_cash: false,
          cost_basis: { status: "partial", unknown_quantity: 600, average_price: 0.3 },
        },
      ],
      open_orders: [],
    });

    render(<PortfolioModePage />);

    const openBtn = await screen.findByText(/Add cost basis to unlock/i);
    fireEvent.click(openBtn);

    const input = screen.getByLabelText(/Average price paid per ADA/i);
    fireEvent.change(input, { target: { value: "0.40" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => {
      expect(saveManualCostBasis).toHaveBeenCalledWith({
        symbol: "ADA",
        averagePrice: 0.4,
      });
    });
  });

  it("renders descriptive price levels labeled not-yet-outcome-validated", async () => {
    fetchPortfolioIntel.mockResolvedValue({
      status: "live",
      updated_at: "2026-07-18T01:00:00Z",
      intel_available: true,
      summary: {
        total_value_usd: 500,
        cash_value_usd: 0,
        known_unrealized_pnl_usd: 0,
        cost_basis_coverage_pct: 0,
        open_order_count: 0,
      },
      holdings: [
        {
          account_id: "arx-account",
          symbol: "ARX",
          name: "ARX Wallet",
          quantity: 1000,
          market_value_usd: 500,
          allocation_pct: 100,
          price_change_24h_pct: 2.0,
          is_cash: false,
          cost_basis: { status: "complete", average_price: 0.4 },
          levels: {
            support: 0.4,
            resistance: 0.6,
            band_low: 0.45,
            band_high: 0.55,
            range_position_pct: 80,
            range_zone: "near_resistance",
            volatility_pct: 5.0,
            momentum_1h_pct: 1.2,
            volume_ratio: 2.0,
            outcome_validated: false,
          },
        },
      ],
      open_orders: [],
    });

    render(<PortfolioModePage />);

    expect(await screen.findByText("Recent levels")).toBeInTheDocument();
    expect(screen.getByText("not yet outcome-validated")).toBeInTheDocument();
    expect(screen.getByText("Near resistance")).toBeInTheDocument();
    expect(screen.getByText("2.00×")).toBeInTheDocument();
  });

  it("rejects a non-positive manual cost basis without calling the API", async () => {
    saveManualCostBasis.mockResolvedValue({ status: "saved" });
    fetchPortfolioIntel.mockResolvedValue({
      status: "live",
      updated_at: "2026-07-18T01:00:00Z",
      intel_available: true,
      summary: {
        total_value_usd: 500,
        cash_value_usd: 0,
        known_unrealized_pnl_usd: 0,
        cost_basis_coverage_pct: 0,
        open_order_count: 0,
      },
      holdings: [
        {
          account_id: "doge-account",
          symbol: "DOGE",
          name: "DOGE Wallet",
          quantity: 1000,
          market_value_usd: 200,
          allocation_pct: 100,
          price_change_24h_pct: 0.5,
          is_cash: false,
          cost_basis: { status: "unavailable" },
        },
      ],
      open_orders: [],
    });

    render(<PortfolioModePage />);

    const openBtn = await screen.findByText(/Add cost basis to unlock/i);
    fireEvent.click(openBtn);
    fireEvent.change(screen.getByLabelText(/Average price paid per DOGE/i), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    expect(await screen.findByText(/positive average price/i)).toBeInTheDocument();
    expect(saveManualCostBasis).not.toHaveBeenCalled();
  });
});
