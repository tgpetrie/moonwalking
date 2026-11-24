import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AnomalyStream from "./AnomalyStream.jsx";

vi.mock("../context/WatchlistContext.jsx", () => ({ useWatchlist: () => ({ watchlist: [] }) }));

afterEach(cleanup);

const NOW = Date.now();
const alert = (id, symbol, type, over = {}) => ({
  id,
  symbol,
  type,
  severity: "high",
  event_ts_ms: NOW - 30_000,
  ...over,
});

const SCAN = {
  status: "ready",
  industry: { available: true, stage_number: 1 },
  coins: [{ symbol: "ATOM", bucket: "deep_accumulation_exhaustion", monthly_bearish_streak: 23 }],
  buckets: {},
};

const ALERTS = [
  alert("a1", "ATOM-USD", "coin_trend_break_up"),
  alert("a2", "XRP-USD", "coin_trend_break_up"),
  alert("a3", "DOGE-USD", "coin_trend_break_down"),
];

const rowSymbols = () => screen.queryAllByTestId("intel-row").map((r) => r.getAttribute("data-symbol"));

describe("AnomalyStream desk tape", () => {
  it("renders cycle badges, the confluence call and a per-row stage badge", async () => {
    render(<AnomalyStream data={{ alerts: ALERTS }} cycleScan={SCAN} watchSymbols={["DOGE"]} />);
    await screen.findByText("DEEP ACCUM · 23m");
    expect(screen.getByText("EXHAUSTION BREAKOUT")).toBeInTheDocument();
    expect(screen.getByText("WATCHLIST")).toBeInTheDocument();
    const rows = screen.getAllByTestId("intel-row");
    expect(rows.length).toBeGreaterThan(1);
    rows.forEach((row) => expect(within(row).getByText("STAGE 1")).toBeInTheDocument());
  });

  it("includes held coins in the Watchlist filter with a HELD badge", async () => {
    render(<AnomalyStream data={{ alerts: ALERTS }} cycleScan={SCAN} watchSymbols={["DOGE"]} heldSymbols={["XRP"]} />);
    await screen.findByText("DEEP ACCUM · 23m");
    fireEvent.click(screen.getByRole("button", { name: "Watchlist" }));
    expect(rowSymbols().sort()).toEqual(["DOGE", "XRP"]);
    const xrp = screen.getAllByTestId("intel-row").find((r) => r.getAttribute("data-symbol") === "XRP");
    expect(within(xrp).getByText("HELD")).toBeInTheDocument();
  });

  it("switches between Confluence & Desk, Watchlist and Raw Tape", async () => {
    render(<AnomalyStream data={{ alerts: ALERTS }} cycleScan={SCAN} watchSymbols={["DOGE"]} />);
    await screen.findByText("DEEP ACCUM · 23m");
    const pills = screen.getByRole("group", { name: "Intelligence log filter" });
    expect(within(pills).getByRole("button", { name: "Confluence & Desk" })).toHaveAttribute("aria-pressed", "true");
    expect(rowSymbols().sort()).toEqual(["ATOM", "DOGE"]);

    fireEvent.click(within(pills).getByRole("button", { name: "Watchlist" }));
    expect(rowSymbols()).toEqual(["DOGE"]);

    fireEvent.click(within(pills).getByRole("button", { name: "Raw Tape" }));
    expect(rowSymbols()).toEqual(expect.arrayContaining(["ATOM", "XRP", "DOGE"]));
  });

  it("never shows a breakout and a breakdown for the same coin together", async () => {
    render(
      <AnomalyStream
        data={{ alerts: [alert("b1", "BTC-USD", "coin_trend_break_up", { severity: "medium" }), alert("b2", "BTC-USD", "coin_trend_break_down")] }}
      />,
    );
    await screen.findAllByTestId("intel-row");
    fireEvent.click(screen.getByRole("button", { name: "Raw Tape" }));
    expect(rowSymbols().filter((s) => s === "BTC")).toHaveLength(1);
  });

  it("uses backend event times when opposite signals arrive in one poll", async () => {
    render(<AnomalyStream data={{ alerts: [
      alert("old", "BTC-USD", "coin_trend_break_up", { event_ts_ms: NOW - 100_000 }),
      alert("new", "BTC-USD", "coin_trend_break_down", { event_ts_ms: NOW - 1_000 }),
    ] }} />);
    await screen.findAllByTestId("intel-row");
    fireEvent.click(screen.getByRole("button", { name: "Raw Tape" }));
    expect(rowSymbols().filter((s) => s === "BTC")).toHaveLength(2);
  });
});
