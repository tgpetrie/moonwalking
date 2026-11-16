import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CoinHeaderStrip, { buildCoinStrip } from "./CoinHeaderStrip.jsx";
import { RiskLevelsPanel } from "./SentimentPopupAdvanced";

vi.mock("../context/DataContext", () => ({ useData: vi.fn(() => ({})) }));
vi.mock("../hooks/useMarketHeat", () => ({ useMarketHeat: () => ({}) }));
vi.mock("../api", () => ({ API_ENDPOINTS: {}, fetchData: vi.fn() }));
vi.mock("./CoinPositioning.jsx", () => ({ default: () => null }));
vi.mock("./AlertsTab", () => ({ default: () => null }));
vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

const wave = (overrides = {}) => ({
  available: true,
  active_pattern: "abc_in_progress",
  status: "in_c_zone",
  bias: "bullish",
  projected_c_zone: { low: 0.1314, high: 0.1348 },
  target_price: 0.1368,
  invalidation_price: 0.1314,
  short_headline: "Inside dip zone ($0.1314–$0.1348) · watching for a bounce toward $0.1368",
  ...overrides,
});

const plan = {
  available: true,
  stop: { trigger_price: 0.120903, limit_price: 0.120661, invalidation_price: 0.1228 },
  profit: { first_trim_price: 0.14643 },
  top_signal: { label: "No top signal", tone: "neutral", action: "No candle-and-signal combination currently meets the top-risk watch threshold." },
};

const waitPosture = {
  label: "WAIT", tone: "neutral", headline: "No clean setup is active right now.",
  supports: ["Volume is supporting the move."], blockers: ["The 1m, 3m, and 1h views do not agree."],
};
const riskPosture = {
  label: "STAY CLEAR", tone: "negative",
  headline: "Short-term tape is moving up, but an active risk warning is overriding the setup.",
  supports: [], blockers: ["A reversal warning is active."],
};
const ranking = { live_rank: 62, universe_size: 107, live_score: 49 };
const neutralLean = { label: "NEUTRAL", tone: "neutral", note: "No clear fast lean right now." };

describe("coin header strip", () => {
  it("leads with the chart read and puts the action levels in one row", () => {
    render(<CoinHeaderStrip wave={wave()} plan={plan} posture={waitPosture} earlyRead={neutralLean} liveRanking={ranking} />);

    const headline = screen.getByTestId("coin-strip-headline");
    expect(headline.textContent).toBe("Inside dip zone ($0.1314–$0.1348) · watching for a bounce toward $0.1368");
    expect(headline).toHaveAttribute("data-source", "chart");

    const cells = within(screen.getByTestId("coin-strip-levels")).getAllByRole("definition").map((dd) => dd.textContent);
    expect(cells).toEqual(["$0.1314–$0.1348", "$0.120903 / $0.120661", "$0.1368 / $0.14643"]);
    const labels = within(screen.getByTestId("coin-strip-levels")).getAllByRole("term").map((dt) => dt.textContent);
    expect(labels).toEqual(["Dip zone", "Stop / limit (uncal.)", "Recovery target / first trim"]);
  });

  it("keeps the tape as a pill without repeating WAIT on every coin", () => {
    render(<CoinHeaderStrip wave={wave()} plan={plan} posture={waitPosture} earlyRead={neutralLean} liveRanking={ranking} />);
    const tape = screen.getByTestId("coin-strip-tape");
    expect(tape.textContent).toContain("Tape #62/107 · 49/100");
    expect(tape.textContent).toContain("Volume is supporting the move");
    expect(within(tape).queryByText("WAIT")).toBeNull();
    expect(tape.getAttribute("title")).toContain("No clean setup is active right now.");
    expect(screen.queryByTestId("coin-strip-risk")).toBeNull();
  });

  it("never lets the chart read bury an active risk posture", () => {
    const lean = { label: "TAPE UP", tone: "caution", note: "Short-term tape is pushing up, but the risk warning overrides entry quality." };
    render(<CoinHeaderStrip wave={wave()} plan={plan} posture={riskPosture} earlyRead={lean} liveRanking={ranking} />);
    const tape = screen.getByTestId("coin-strip-tape");
    expect(within(tape).getByText("STAY CLEAR")).toBeTruthy();
    expect(within(tape).getByText("TAPE UP").getAttribute("title")).toContain("risk warning overrides");
    expect(screen.getByTestId("coin-strip").className).toContain("cp-strip--negative");
    // The chart headline stays, and the risk reason is written out beside it.
    expect(screen.getByTestId("coin-strip-headline").textContent).toContain("Inside dip zone");
    expect(screen.getByTestId("coin-strip-risk").textContent).toBe(
      "Tape risk: Short-term tape is moving up, but an active risk warning is overriding the setup.",
    );
  });

  it("uses the run of swings when there is no setup, and support when there is no zone", () => {
    const none = wave({ active_pattern: "none", projected_c_zone: null, target_price: null, short_headline: "7 lower highs in a row · needs a break above $82.32" });
    const strip = buildCoinStrip({ wave: none, plan, posture: waitPosture, earlyRead: neutralLean, liveRanking: ranking });
    expect(strip.headline).toBe("7 lower highs in a row · needs a break above $82.32");
    expect(strip.levels.map((l) => [l.label, l.value])).toEqual([
      ["Support fails", "$0.1228"],
      ["Stop / limit (uncal.)", "$0.120903 / $0.120661"],
      ["First trim", "$0.14643"],
    ]);
  });

  it("mirrors the wording for a bounce inside a decline", () => {
    const bear = wave({ bias: "bearish", projected_c_zone: { low: 70.1, high: 73.4 }, target_price: 67.37 });
    const strip = buildCoinStrip({ wave: bear, plan });
    expect(strip.levels[0]).toMatchObject({ label: "Bounce zone", value: "$70.10–$73.40" });
    expect(strip.levels[2].label).toBe("Downside target / first trim");
  });

  it("falls back to the tape posture only when chart history is unavailable", () => {
    const loading = buildCoinStrip({ wave: null, plan, posture: waitPosture, chartLoading: true });
    expect([loading.source, loading.headline]).toEqual(["loading", "Reading the chart…"]);

    const tapeOnly = buildCoinStrip({ wave: { available: false }, plan, posture: riskPosture, liveRanking: ranking });
    expect(tapeOnly.source).toBe("tape");
    expect(tapeOnly.headline).toBe("STAY CLEAR · Short-term tape is moving up, but an active risk warning is overriding the setup");
    expect(tapeOnly.risk).toBeNull(); // already the headline; not said twice

    const nothing = buildCoinStrip({});
    expect(nothing.headline).toBe("No chart history or live tape for this coin yet.");
    expect(nothing.levels.map((l) => l.value)).toEqual(["—", "— / —", "—"]);
    expect(nothing.tape.rank).toBe("Tape warming");
  });
});

describe("compact sell-side row", () => {
  const data = { plan, history: {} };

  it("shows the four prices and the way into the full plan in one row", () => {
    const onOpen = vi.fn();
    render(<RiskLevelsPanel data={data} compact onOpen={onOpen} />);
    const row = screen.getByTestId("risk-levels-compact");
    expect(within(row).getByText("Stop trigger").nextSibling.textContent).toBe("$0.120903");
    expect(within(row).getByText("Sell limit (uncalibrated)").nextSibling.textContent).toBe("$0.120661");
    expect(within(row).getByText("Support fails").nextSibling.textContent).toBe("$0.1228");
    expect(within(row).getByText("First trim").nextSibling.textContent).toBe("$0.14643");
    fireEvent.click(within(row).getByRole("button", { name: "Open risk levels" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("gives 'no top signal' no space but keeps a real warning", () => {
    const { unmount } = render(<RiskLevelsPanel data={data} compact />);
    expect(screen.queryByText(/No top signal/)).toBeNull();
    expect(screen.queryByText(/top-risk watch threshold/)).toBeNull();
    unmount();
    const warned = { plan: { ...plan, top_signal: { label: "Top watch", tone: "caution", action: "Watch for rejection before adding risk." } } };
    render(<RiskLevelsPanel data={warned} compact />);
    expect(screen.getByText("Top watch.")).toBeTruthy();
    expect(screen.getByText(/Watch for rejection before adding risk\./)).toBeTruthy();
  });
});
