import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PortfolioRiskBoard from "./PortfolioRiskBoard.jsx";

vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));
vi.mock("../context/WatchlistContext.jsx", () => ({ readGuestItems: () => [{ symbol: "BTC" }, { symbol: "SOL" }] }));

const plan = {
  available: true, product_id: "BTC-USD", current_price: 100,
  price_as_of: Math.floor(Date.now() / 1000),
  top_signal: { status: "clear", label: "No top signal", reasons: ["Price is not near resistance."] },
  market_structure: { range_position_pct: 8, support: 95, resistance: 112 },
  stop: { trigger_price: 94.6, limit_price: 94.3, invalidation_price: 95, why: ["A buffer below support."] },
  profit: { first_trim_price: 112 },
};

const reclaim = {
  product_id: "BTC-USD", symbol: "BTC", quantity: 2, price_usd: 100, market_value_usd: 200,
  status: "clear", entry_status: "entry_watch", distance_to_stop_pct: 5.4, distance_to_resistance_pct: 12,
  capital_to_stop_usd: 10.8, plan,
  entry: {
    available: true, product_id: "BTC-USD", current_price: 100,
    entry_signal: {
      label: "Support reclaim", status: "entry_watch", tone: "positive", score: 6,
      action: "Watch for the reclaim to hold on a completed candle.",
      reasons: ["Price is in the bottom 15% of its recent candle range, just above the structural support at 95."],
    },
    entry_zone: { low: 94.8, high: 95.5, label: "Support / reclaim watch zone", why: "Require a hold or a reclaim." },
    invalidation: { price: 95, distance_pct: -5, why: "A completed candle below support removes the structure." },
    target_reference: { first_resistance: 112, reward_pct: 12, reward_risk_ratio: 2.4, why: "Measured to the resistance." },
    methodology: { version: "entry_levels_v1", outcome_validated: false, order_placement: false },
  },
};

const extended = {
  product_id: "SOL-USD", symbol: "SOL", quantity: 1, price_usd: 100, market_value_usd: 100,
  status: "watch", entry_status: "extended", distance_to_stop_pct: 9.1, distance_to_resistance_pct: null,
  capital_to_stop_usd: 9.1, plan: { ...plan, product_id: "SOL-USD", top_signal: { status: "watch", label: "Top watch", reasons: ["Price is in the top 15% of its recent candle range."] } },
  entry: {
    available: true, product_id: "SOL-USD", current_price: 100,
    entry_signal: {
      label: "Too extended", status: "extended", tone: "caution", score: 2,
      action: "Entering here pays the top of the measured range.",
      reasons: ["Price is at or above the measured resistance at 99 with no overhead reference left in this window."],
    },
    entry_zone: { low: null, high: null, label: "No entry zone", why: "Naming an entry band here would invent a level." },
    invalidation: { price: 91, distance_pct: -9, why: "A completed candle below support removes the structure." },
    target_reference: { first_resistance: null, reward_pct: null, reward_risk_ratio: null, why: "No overhead reference." },
  },
};

function payload(overrides = {}) {
  return {
    source: "portfolio", updated_at: 1800000000, rows: [reclaim, extended],
    summary: {
      counts: { clear: 1, watch: 1 },
      entry_counts: { breakout: 0, entry_watch: 1, pullback: 0, extended: 1, invalidated: 0, clear: 0, unavailable: 0 },
      capital_to_stop_usd: 19.9, sized_plan_count: 2, excluded_symbols: [], breached_symbols: [],
    },
    ...overrides,
  };
}
function respond(body) { return Promise.resolve({ ok: true, json: async () => body }); }
afterEach(() => vi.unstubAllGlobals());

describe("Portfolio Risk Board entry read", () => {
  it("shows the protection read and the entry read on the same card", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(payload())));
    render(<PortfolioRiskBoard />);
    const card = await screen.findByRole("article", { name: "BTC risk levels" });

    expect(within(card).getByText("No top signal")).toBeInTheDocument();
    expect(within(card).getByText("Support reclaim")).toBeInTheDocument();
    expect(within(card).getByRole("region", { name: "BTC protection read" })).toBeInTheDocument();
    const entryRead = within(card).getByRole("region", { name: "BTC entry read" });
    expect(within(entryRead).getByText(/bottom 15% of its recent candle range/)).toBeInTheDocument();
    expect(within(entryRead).getByText("$94.8 to $95.5")).toBeInTheDocument();
    expect(within(entryRead).getByText(/^\$95 .* 5\.0% under price$/)).toBeInTheDocument();
    expect(within(entryRead).getByText("2.4x to $112")).toBeInTheDocument();
    expect(within(entryRead).getByText("6 of 10 declared cues")).toBeInTheDocument();
  });

  it("never invents an entry band or a reward it cannot measure", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(payload())));
    render(<PortfolioRiskBoard />);
    const card = await screen.findByRole("article", { name: "SOL risk levels" });
    const entryRead = within(card).getByRole("region", { name: "SOL entry read" });

    expect(within(card).getByText("Too extended")).toBeInTheDocument();
    expect(within(entryRead).getByText("No honest entry band here")).toBeInTheDocument();
    expect(within(entryRead).getByText("No overhead reference to measure")).toBeInTheDocument();
  });

  it("counts entry states without turning them into advice", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(payload())));
    render(<PortfolioRiskBoard />);
    const summary = await screen.findByRole("region", { name: "Entry summary" });

    expect(within(summary).getByText(/support reclaim/)).toBeInTheDocument();
    expect(within(summary).getByText(/no chase/)).toBeInTheDocument();
    expect(within(summary).getByText(/not buy instructions, forecasts, or orders/)).toBeInTheDocument();
  });

  it("says the entry read is unavailable instead of implying a clear entry", async () => {
    const withoutEntry = { ...reclaim, entry: undefined };
    const unavailable = { ...extended, entry: { available: false, reason: "A fresh quote is unavailable. Refresh when the price feed is current.", entry_signal: { label: "Not ready", status: "unavailable", tone: "neutral", score: 0, reasons: [] } } };
    vi.stubGlobal("fetch", vi.fn(() => respond(payload({ rows: [withoutEntry, unavailable], summary: { ...payload().summary, entry_counts: { unavailable: 2 } } }))));
    render(<PortfolioRiskBoard />);

    const missing = await screen.findByRole("article", { name: "BTC risk levels" });
    expect(within(missing).getByText("Entry read unavailable")).toBeInTheDocument();
    expect(within(missing).getByText(/Not enough history for an entry read yet/)).toBeInTheDocument();
    const stale = screen.getByRole("article", { name: "SOL risk levels" });
    expect(within(stale).getByText(/A fresh quote is unavailable/)).toBeInTheDocument();
    expect(within(stale).queryByText(/declared cues/)).not.toBeInTheDocument();
  });
});
