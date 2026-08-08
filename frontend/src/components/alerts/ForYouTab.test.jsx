import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// For You reads market data and watchlist membership from app contexts.
const mockData = { activeAlerts: [], alertsRecent: [] };
let mockWatchlisted = new Set();

vi.mock("../../context/DataContext", () => ({
  useData: () => mockData,
}));
vi.mock("../../context/WatchlistContext.jsx", () => ({
  useWatchlist: () => ({ items: [], has: (s) => mockWatchlisted.has(s) }),
}));
vi.mock("../../mvp/portfolioApi.js", () => ({
  fetchPortfolio: vi.fn(),
}));

import { fetchPortfolio } from "../../mvp/portfolioApi.js";
import { __resetHoldingsCacheForTests } from "./useHoldingSymbols.js";
import ForYouTab from "./ForYouTab.jsx";

const NOW_S = Math.floor(Date.now() / 1000);

const SUGGESTION = {
  id: "rec_1",
  symbol: "ETH",
  basis: "portfolio",
  reason: "Because ETH is in your portfolio, Moonwalkings can notify you if it moves.",
  created_at: new Date().toISOString(),
};

const FIRED = {
  id: "evt_1",
  symbol: "BTC",
  event_type: "price_cross",
  observed_value: 115,
  boundary_value: 110,
  triggered_ts: NOW_S - 600,
  explanation: "BTC rose above $110.00, reaching $115.00. You created this alert.",
};

const MARKET = {
  id: "mk_1",
  symbol: "SOL",
  type_key: "moonshot",
  severity: "high",
  message: "SOL strong upside move",
  ts: NOW_S - 300,
};

const baseProps = {
  events: [],
  recommendations: [],
  rules: [],
  loading: { rules: false, recs: false, events: false },
  errors: { rules: null, recs: null, events: null },
  authRequired: false,
  onLoad: () => {},
  onAccept: () => {},
  onDismiss: () => {},
};

beforeEach(() => {
  vi.clearAllMocks();
  mockData.activeAlerts = [];
  mockData.alertsRecent = [];
  mockWatchlisted = new Set();
  __resetHoldingsCacheForTests();
  // Default: portfolio unavailable — For You must not depend on it.
  fetchPortfolio.mockRejectedValue(
    Object.assign(new Error("Authentication required"), { status: 401 })
  );
});

describe("ForYouTab", () => {
  it("shows a calm empty state when nothing is relevant", () => {
    render(<ForYouTab {...baseProps} />);
    expect(screen.getByText("Nothing needs your attention right now")).toBeInTheDocument();
  });

  it("keeps non-relevant market signals out", () => {
    mockData.alertsRecent = [MARKET]; // SOL not watchlisted, not held
    render(<ForYouTab {...baseProps} />);
    expect(screen.queryByText(/SOL/)).not.toBeInTheDocument();
  });

  it("shows watchlisted market signals with reason and kind labels", () => {
    mockData.alertsRecent = [MARKET];
    mockWatchlisted = new Set(["SOL"]);
    render(<ForYouTab {...baseProps} />);
    expect(screen.getByText("SOL")).toBeInTheDocument();
    expect(screen.getByText("Market signal")).toBeInTheDocument();
    expect(screen.getByText(/On your watchlist/)).toBeInTheDocument();
  });

  it("renders suggestions inline with Enable/Dismiss and explains why", async () => {
    const onAccept = vi.fn().mockResolvedValue({});
    render(
      <ForYouTab {...baseProps} recommendations={[SUGGESTION]} onAccept={onAccept} />
    );
    expect(screen.getByText("Suggested")).toBeInTheDocument();
    expect(screen.getByText(/Because ETH is in your portfolio/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Enable" }));
    await waitFor(() => expect(onAccept).toHaveBeenCalledWith("rec_1"));
  });

  it("never auto-enables a suggestion", () => {
    const onAccept = vi.fn();
    render(<ForYouTab {...baseProps} recommendations={[SUGGESTION]} onAccept={onAccept} />);
    expect(onAccept).not.toHaveBeenCalled();
  });

  it("shows fired alerts with their deterministic explanation", () => {
    render(<ForYouTab {...baseProps} events={[FIRED]} />);
    expect(screen.getByText("Your alert")).toBeInTheDocument();
    expect(screen.getByText(/You created this alert/)).toBeInTheDocument();
  });

  it("does not repeat a redundant reason on fired-alert cards", () => {
    render(<ForYouTab {...baseProps} events={[FIRED]} />);
    // The kind chip already says "Your alert"; the badge carries only time.
    expect(screen.queryByText(/You track this/)).not.toBeInTheDocument();
    expect(screen.getByText("10m ago")).toBeInTheDocument();
  });

  it("wires Details and Set alert intents for market items", () => {
    mockData.alertsRecent = [MARKET];
    mockWatchlisted = new Set(["SOL"]);
    const onOpen = vi.fn();
    const onSet = vi.fn();
    render(
      <ForYouTab {...baseProps} onOpenCoinSentiment={onOpen} onSetAlertFor={onSet} />
    );
    fireEvent.click(screen.getByRole("button", { name: "Details" }));
    expect(onOpen).toHaveBeenCalledWith("SOL");
    fireEvent.click(screen.getByRole("button", { name: "Set alert" }));
    expect(onSet).toHaveBeenCalledWith("SOL");
  });

  it("signed-out: shows a calm note but still surfaces watchlist market signals", () => {
    mockData.alertsRecent = [MARKET];
    mockWatchlisted = new Set(["SOL"]);
    render(
      <ForYouTab
        {...baseProps}
        authRequired
        recommendations={[SUGGESTION]} // must NOT render while signed out
        events={[FIRED]}
      />
    );
    expect(
      screen.getByText(/Sign in to see your own alerts and suggestions/)
    ).toBeInTheDocument();
    expect(screen.getByText("SOL")).toBeInTheDocument();
    expect(screen.queryByText("Suggested")).not.toBeInTheDocument();
    expect(screen.queryByText("Your alert")).not.toBeInTheDocument();
  });

  it("admits a held coin's market signal even when not watchlisted", async () => {
    fetchPortfolio.mockResolvedValue({
      holdings: [
        { symbol: "ADA", is_cash: false },
        { symbol: "USD", is_cash: true }, // cash rows are not holdings
      ],
    });
    mockData.alertsRecent = [{ ...MARKET, id: "mk_ada", symbol: "ADA" }];
    // ADA is NOT watchlisted and has no rule — portfolio is the only tie.
    render(<ForYouTab {...baseProps} />);

    expect(await screen.findByText("ADA")).toBeInTheDocument();
    expect(screen.getByText(/In your portfolio/)).toBeInTheDocument();
  });

  it("still excludes ambient signals when a portfolio exists", async () => {
    fetchPortfolio.mockResolvedValue({ holdings: [{ symbol: "ADA", is_cash: false }] });
    mockData.alertsRecent = [
      { ...MARKET, id: "mk_ada", symbol: "ADA" },
      { ...MARKET, id: "mk_doge", symbol: "DOGE" }, // not held/watched/tracked
    ];
    render(<ForYouTab {...baseProps} />);

    expect(await screen.findByText("ADA")).toBeInTheDocument();
    expect(screen.queryByText("DOGE")).not.toBeInTheDocument();
  });

  it("falls back gracefully when the portfolio API is unavailable", async () => {
    fetchPortfolio.mockRejectedValue(
      Object.assign(new Error("upstream_unavailable"), { status: 503 })
    );
    mockData.alertsRecent = [MARKET];
    mockWatchlisted = new Set(["SOL"]);
    const { container } = render(<ForYouTab {...baseProps} />);

    // Watchlist relevance carries the stream; the raw error never renders.
    expect(await screen.findByText("SOL")).toBeInTheDocument();
    expect(container.textContent).not.toContain("upstream_unavailable");
  });

  it("treats an empty portfolio as no extra relevance, nothing more", async () => {
    fetchPortfolio.mockResolvedValue({ holdings: [] });
    mockData.alertsRecent = [MARKET]; // SOL: not watchlisted here
    render(<ForYouTab {...baseProps} />);

    expect(
      await screen.findByText("Nothing needs your attention right now")
    ).toBeInTheDocument();
  });

  it("rule-symbol relevance works independently of portfolio", async () => {
    mockData.alertsRecent = [{ ...MARKET, id: "mk_dot", symbol: "DOT" }];
    render(
      <ForYouTab
        {...baseProps}
        rules={[{ id: "rule_9", symbol: "DOT", status: "active", params: {} }]}
      />
    );
    expect(await screen.findByText("DOT")).toBeInTheDocument();
    expect(screen.getByText(/You track this/)).toBeInTheDocument();
  });

  it("does not fetch the portfolio while signed out", () => {
    render(<ForYouTab {...baseProps} authRequired />);
    expect(fetchPortfolio).not.toHaveBeenCalled();
  });

  it("leaks no internal machinery or advice language", () => {
    mockData.alertsRecent = [MARKET];
    mockWatchlisted = new Set(["SOL"]);
    const { container } = render(
      <ForYouTab {...baseProps} events={[FIRED]} recommendations={[SUGGESTION]} />
    );
    const html = container.innerHTML;
    for (const hidden of ["arm_cycle", "fingerprint", "reset_pct", "percent_rearm_ratio"]) {
      expect(html).not.toContain(hidden);
    }
    const text = container.textContent.toLowerCase();
    for (const word of [" buy ", " sell ", " hold ", "stop loss", "take profit"]) {
      expect(text).not.toContain(word);
    }
  });
});
