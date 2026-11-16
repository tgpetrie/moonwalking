import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api.js", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, fetchMacroCycleScan: vi.fn() };
});

import { fetchMacroCycleScan } from "../api.js";
import IndustryPulse, { BREADTH_METRICS, CYCLE_BUCKETS, IndustryPulseView, breadthText, coinFacts } from "./IndustryPulse.jsx";
import { SCAN_PENDING_MS } from "../hooks/useMacroCycleScan.js";

// Shapes copied from macro_industry_scanner.scan_universe_cycles.
const coin = (symbol, bucket, extra = {}) => ({
  symbol, product_id: `${symbol}-USD`, available: true, price: 1.7162, bucket, score: 10,
  weekly_rsi: 28.16, weekly_rsi_regime: "oversold_compression", monthly_rsi: 11.33,
  weekly_stoch_direction: "bullish_expansion", monthly_bearish_streak: 21, multi_year_oversold_exhaustion: true,
  above_50w_sma: false, pct_from_cycle_high: -87.14, at_multi_year_support: true, cycle_pattern: "wxy_terminal_sweep",
  low_confirmation_pivot: { price: 1.8824, distance_pct: 9.68, at_support: true },
  breaking_confirmation_pivot: false,
  accumulation_invalidation_stop: { stop_price: 1.5627, stop_distance_pct: 8.94 },
  weekly_macd_bullish_cross: false, rollover_target_box: { low: 5.1, high: 8.2 }, fib_confluence_clusters: 1,
  active_target_tier: "rollover_target_box", macro_regime_gate: "risk_on_aligned",
  ...extra,
});

const breadth = {
  pct_monthly_exhausted: { pct: 25.0, count: 2, of: 8 },
  pct_weekly_rsi_above_60: { pct: 50.0, count: 4, of: 8 },
  pct_above_50w_sma: { pct: 37.5, count: 3, of: 8 },
  pct_breaking_confirmation_pivot: { pct: 12.5, count: 1, of: 8 },
  coins: 8,
};

const scan = (overrides = {}) => ({
  status: "ready",
  computed_at: 1794700800,
  industry: {
    available: true,
    liquidity_rotation_stage: "stage_3_alt_index_breakout",
    stage_number: 3,
    stage_label: "Stage 3 · Alt index breakout",
    macro_regime_gate: "risk_on_aligned",
    gate_label: "Risk-on aligned",
    active_target_tier: "full_extension_targets",
    reasons: [
      "The altcoin index is back above its 50-week average with weekly MACD above its signal line, or has weekly RSI above 60.",
      "The altcoin index has broken out and breadth agrees.",
    ],
    alt_index: { available: true, name: "ALT_INDEX_3Y", member_count: 7 },
    breadth,
    outcome_validated: false,
  },
  breadth,
  buckets: {
    deep_accumulation_exhaustion: [
      coin("ETH", "deep_accumulation_exhaustion", { monthly_bearish_streak: 33, multi_year_oversold_exhaustion: false, weekly_rsi: 12.4 }),
      coin("RENDER", "deep_accumulation_exhaustion"),
      coin("FET", "deep_accumulation_exhaustion", { monthly_bearish_streak: 19 }),
    ],
    low_confirmation_breakout: [coin("BRK", "low_confirmation_breakout", { weekly_rsi: 55.1, breaking_confirmation_pivot: true, weekly_macd_bullish_cross: true })],
    growth_expansion_ride: [
      coin("BTC", "growth_expansion_ride", { weekly_rsi: 71.26, above_50w_sma: true, pct_from_cycle_high: -1.27 }),
      coin("UP", "growth_expansion_ride", { weekly_rsi: 64, above_50w_sma: true }),
    ],
    rollover_profit_zone: [],
  },
  bucket_labels: {
    deep_accumulation_exhaustion: "Deep accumulation · exhaustion",
    low_confirmation_breakout: "Low-confirmation breakout",
    growth_expansion_ride: "Growth expansion",
    rollover_profit_zone: "Rollover zone",
  },
  coins: [],
  scanned: 8,
  skipped: ["NEW"],
  blocks_alerts: false,
  outcome_validated: false,
  ...overrides,
});

const warming = {
  status: "warming", industry: { available: false, reason: "warming" }, breadth: null, buckets: {}, coins: [],
  blocks_alerts: false, outcome_validated: false,
};

const bucketButtons = () => within(screen.getByTestId("industry-pulse-buckets")).getAllByRole("button");
const coinSymbols = () => Array.from(screen.getByTestId("industry-pulse-coins").querySelectorAll(".bh-pulse__symbol")).map((el) => el.textContent);

describe("industry pulse summary", () => {
  it("shows the liquidity stage, 1 to 4, with the gate", () => {
    render(<IndustryPulseView scan={scan()} />);
    const stage = screen.getByTestId("industry-pulse-stage");
    expect(stage.getAttribute("data-stage")).toBe("3");
    expect(stage.textContent).toContain("Stage 3 · Alt index breakout");
    const steps = Array.from(stage.querySelectorAll(".bh-pulse__step"));
    expect(steps.map((el) => el.textContent)).toEqual(["1", "2", "3", "4"]);
    expect(steps.map((el) => el.className.includes("is-active"))).toEqual([false, false, true, false]);
    const gate = screen.getByTestId("industry-pulse-gate");
    expect(gate.getAttribute("data-gate")).toBe("risk_on_aligned");
    expect(gate.textContent).toBe("Risk-on aligned");
    expect(gate.className).toContain("bh-pulse__gate--ok");
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("READY");
  });

  it.each([
    ["neutral_chop", "Neutral chop", "neutral"],
    ["risk_off_headwind", "Risk-off headwind", "danger"],
  ])("colours the %s gate as a status, not a price move", (gate, label, tone) => {
    const data = scan();
    data.industry = { ...data.industry, macro_regime_gate: gate, gate_label: label, stage_number: 1, stage_label: "Stage 1 · Macro compression" };
    render(<IndustryPulseView scan={data} />);
    expect(screen.getByTestId("industry-pulse-gate").className).toContain(`bh-pulse__gate--${tone}`);
    expect(screen.getByTestId("industry-pulse-stage").getAttribute("data-stage")).toBe("1");
  });

  it("reports the three breadth shares with their counts", () => {
    render(<IndustryPulseView scan={scan()} />);
    expect(BREADTH_METRICS.map((m) => m.label)).toEqual(["1M Exhausted", "1W RSI > 60", "Above 50W SMA"]);
    const read = (key) => screen.getByTestId(`industry-pulse-${key}`).textContent;
    expect(read("pct_monthly_exhausted")).toContain("1M Exhausted");
    expect(read("pct_monthly_exhausted")).toContain("25%");
    expect(read("pct_monthly_exhausted")).toContain("2 of 8");
    expect(read("pct_weekly_rsi_above_60")).toContain("50%");
    expect(read("pct_above_50w_sma")).toContain("38%");
    expect(read("pct_above_50w_sma")).toContain("3 of 8");
  });

  it("shows a dash, never zero, for a breadth share nothing could be read for", () => {
    expect(breadthText({ pct: null, count: 0, of: 0 })).toBe("—");
    expect(breadthText(undefined)).toBe("—");
    expect(breadthText({ pct: 0, count: 0, of: 8 })).toBe("0%");
    const data = scan({ breadth: { ...breadth, pct_monthly_exhausted: { pct: null, count: 0, of: 0 } } });
    render(<IndustryPulseView scan={data} />);
    const cell = screen.getByTestId("industry-pulse-pct_monthly_exhausted").textContent;
    expect(cell).toContain("—");
    expect(cell).toContain("no read");
    expect(cell).not.toContain("0%");
  });

  it("keeps breadth and buckets but marks the stage unavailable when the stage could not be read", () => {
    render(<IndustryPulseView scan={scan({ industry: { available: false, reason: "alt_index_unavailable" } })} />);
    const stage = screen.getByTestId("industry-pulse-stage");
    expect(stage.getAttribute("data-stage")).toBe("none");
    expect(stage.textContent).toContain("Stage unavailable");
    expect(stage.textContent).toContain("Too few altcoins with history to build the index.");
    expect(stage.querySelector(".is-active")).toBeNull();
    expect(screen.queryByTestId("industry-pulse-gate")).toBeNull();
    expect(screen.getByTestId("industry-pulse-pct_weekly_rsi_above_60").textContent).toContain("50%");
    expect(coinSymbols()).toEqual(["ETH", "RENDER", "FET"]);
  });

  it("says it is context only and how much was read", () => {
    render(<IndustryPulseView scan={scan()} />);
    const text = screen.getByTestId("industry-pulse").textContent;
    expect(text).toContain("not tested against outcomes");
    expect(text).toContain("does not feed alerts");
    expect(text).toContain("8 coins read");
    expect(text).toContain("1 skipped");
    expect(text).toContain("equal-weight proxy of 7 coins");
  });
});

describe("industry pulse cycle buckets", () => {
  it("offers the four buckets with their counts and opens the first one that has coins", () => {
    render(<IndustryPulseView scan={scan()} />);
    expect(CYCLE_BUCKETS.map((b) => b.label)).toEqual(["Deep Accumulation", "Confirmation Breakout", "Growth Expansion", "Rollover Zone"]);
    const buttons = bucketButtons();
    expect(buttons.map((b) => b.textContent)).toEqual(["Deep Accumulation3", "Confirmation Breakout1", "Growth Expansion2", "Rollover Zone0"]);
    expect(buttons.map((b) => b.getAttribute("aria-pressed"))).toEqual(["true", "false", "false", "false"]);
    expect(coinSymbols()).toEqual(["ETH", "RENDER", "FET"]);
  });

  it("keeps the backend's ranking inside a bucket", () => {
    render(<IndustryPulseView scan={scan()} />);
    const ranks = Array.from(screen.getByTestId("industry-pulse-coins").querySelectorAll(".bh-pulse__rank")).map((el) => el.textContent);
    expect(ranks).toEqual(["1", "2", "3"]);
  });

  it("filters to the chosen bucket and says when one is empty", () => {
    render(<IndustryPulseView scan={scan()} />);
    fireEvent.click(bucketButtons()[2]);
    expect(bucketButtons()[2].getAttribute("aria-pressed")).toBe("true");
    expect(coinSymbols()).toEqual(["BTC", "UP"]);
    fireEvent.click(bucketButtons()[3]);
    expect(screen.queryByTestId("industry-pulse-coins")).toBeNull();
    expect(screen.getByTestId("industry-pulse-empty").textContent).toContain("No scanned coin is in this bucket");
  });

  it("opens with the first filled bucket when the earlier ones are empty", () => {
    const data = scan();
    data.buckets.deep_accumulation_exhaustion = [];
    data.buckets.low_confirmation_breakout = [];
    render(<IndustryPulseView scan={data} />);
    expect(bucketButtons().map((b) => b.getAttribute("aria-pressed"))).toEqual(["false", "false", "true", "false"]);
    expect(coinSymbols()).toEqual(["BTC", "UP"]);
  });

  it("opens the coin when a ranked coin is clicked", () => {
    const onInfo = vi.fn();
    render(<IndustryPulseView scan={scan()} onInfo={onInfo} />);
    fireEvent.click(screen.getByRole("button", { name: /RENDER/ }));
    expect(onInfo).toHaveBeenCalledWith("RENDER");
  });

  it("shows eight coins and expands to the rest on request", () => {
    const data = scan();
    data.buckets.growth_expansion_ride = Array.from({ length: 11 }, (_, i) => coin(`C${i}`, "growth_expansion_ride", { weekly_rsi: 80 - i }));
    render(<IndustryPulseView scan={data} />);
    fireEvent.click(bucketButtons()[2]);
    expect(coinSymbols()).toHaveLength(8);
    fireEvent.click(screen.getByRole("button", { name: "Show all 11" }));
    expect(coinSymbols()).toHaveLength(11);
    fireEvent.click(screen.getByRole("button", { name: "Show fewer" }));
    expect(coinSymbols()).toHaveLength(8);
  });

  it("picks the number that explains why a coin is in its bucket", () => {
    expect(coinFacts(coin("A", "x"), "deep_accumulation_exhaustion")).toEqual({ metric: "21 mo", note: "1M exhausted" });
    expect(coinFacts(coin("A", "x", { multi_year_oversold_exhaustion: false }), "deep_accumulation_exhaustion")).toEqual({ metric: "21 mo", note: "1W RSI 28.2" });
    expect(coinFacts(coin("A", "x", { weekly_rsi: 55.1, weekly_macd_bullish_cross: true }), "low_confirmation_breakout")).toEqual({ metric: "55.1", note: "broke pivot · 1W MACD cross" });
    expect(coinFacts(coin("A", "x", { weekly_rsi: 71.26, above_50w_sma: true }), "growth_expansion_ride")).toEqual({ metric: "71.3", note: "above 50W SMA" });
    expect(coinFacts(coin("A", "x", { pct_from_cycle_high: -41.58 }), "rollover_profit_zone")).toEqual({ metric: "−41.6%", note: "from cycle high" });
    expect(coinFacts({ symbol: "A" }, "growth_expansion_ride").metric).toBe("—");
  });
});

describe("industry pulse states", () => {
  it("reads as loading before the first answer and unavailable after a failure", () => {
    const { rerender } = render(<IndustryPulseView scan={null} loading />);
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("LOADING");
    expect(screen.getByText("Reading the industry cycle…")).toBeTruthy();
    rerender(<IndustryPulseView scan={null} error="unavailable" />);
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("UNAVAILABLE");
    expect(screen.getByText("Industry pulse unavailable.")).toBeTruthy();
  });

  it("shows warming with no stage, shares or buckets", () => {
    render(<IndustryPulseView scan={warming} />);
    const panel = screen.getByTestId("industry-pulse");
    expect(panel.getAttribute("data-status")).toBe("WARMING");
    expect(panel.textContent).toContain("Warming up");
    expect(screen.queryByTestId("industry-pulse-stage")).toBeNull();
    expect(screen.queryByTestId("industry-pulse-breadth")).toBeNull();
    expect(screen.queryByTestId("industry-pulse-buckets")).toBeNull();
    expect(panel.textContent).not.toMatch(/\d%/);
  });

  it("keeps the last scan on screen while refreshing or after a failed update", () => {
    const { rerender } = render(<IndustryPulseView scan={scan({ status: "refreshing" })} />);
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("REFRESHING");
    expect(screen.getByTestId("industry-pulse").textContent).toContain("refreshing");
    rerender(<IndustryPulseView scan={scan()} error="unavailable" />);
    expect(screen.getByTestId("industry-pulse").textContent).toContain("last update failed");
    expect(screen.getByTestId("industry-pulse-stage").textContent).toContain("Stage 3");
  });
});

describe("industry pulse on the dashboard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    fetchMacroCycleScan.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks for the scan with the watchlist symbols and renders the answer", async () => {
    fetchMacroCycleScan.mockResolvedValue(scan());
    render(<IndustryPulse symbols={["render-usd", "FET", "RENDER"]} />);
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("LOADING");
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(fetchMacroCycleScan).toHaveBeenCalledTimes(1);
    expect(fetchMacroCycleScan).toHaveBeenCalledWith(["FET", "RENDER"]);
    expect(screen.getByTestId("industry-pulse-stage").textContent).toContain("Stage 3 · Alt index breakout");
  });

  it("polls again while the server is warming, then shows the scan", async () => {
    fetchMacroCycleScan.mockResolvedValueOnce(warming).mockResolvedValue(scan());
    render(<IndustryPulse />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("WARMING");
    await act(async () => { await vi.advanceTimersByTimeAsync(SCAN_PENDING_MS); });
    expect(fetchMacroCycleScan).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("READY");
  });

  it("reads as unavailable when the request fails and there is nothing to keep", async () => {
    fetchMacroCycleScan.mockRejectedValue(new Error("HTTP error! status: 503"));
    render(<IndustryPulse />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId("industry-pulse").getAttribute("data-status")).toBe("UNAVAILABLE");
  });
});
