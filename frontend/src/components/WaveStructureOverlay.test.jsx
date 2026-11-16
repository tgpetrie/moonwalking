import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ChartReadPanel from "./ChartReadPanel.jsx";
import RiskLevelsChart from "./RiskLevelsChart.jsx";
import { waveIsDrawable, wavePlainLabels, wavePrices } from "./WaveStructureOverlay.jsx";
import { runLabel, swingColor, SWING_DOWN_COLOR, SWING_UP_COLOR } from "./SwingHistoryOverlay.jsx";

const HOUR = 3600;
const candles = Array.from({ length: 30 }, (_, i) => {
  const open = 100 + Math.sin(i / 3) * 4;
  const close = 100 + Math.sin((i + 1) / 3) * 4;
  return [i * HOUR, Math.min(open, close) - 1, Math.max(open, close) + 1, open, close, 10 + i];
});

const point = (label, i, price, kind, confirmed = true) => ({ label, ts: i * HOUR, price, kind, index: i, confirmed });
const swing = (i, price, kind, relation, label) => ({ ts: i * HOUR, price, kind, relation, label });

const story = {
  kind: "pullback_in_advance",
  headline: "Pulling back after an advance, now inside the usual dip zone",
  steps: [
    { key: "prior_move", number: 1, title: "Prior advance", text: "Rose 19.6% from $92.00 to $110.00." },
    { key: "zone", number: 2, title: "Pullback / dip zone", short_title: "Dip zone", text: "$93.06 to $101.06. Price is inside it now." },
    { key: "target", number: 3, title: "Recovery target", text: "$106.00, the high of the last bounce. The prior peak is $110.00." },
    { key: "breaks", title: "Setup breaks below $93.06", text: "A trade below that price means this read no longer applies." },
  ],
  why_it_matters: [
    { name: "higher_tf_trend", state: "present", plain: "Bigger trend points up too", technical: "4h trend", detail: "Higher-timeframe trend is up." },
    { name: "volume_contraction", state: "present", plain: "Dipping on lighter volume", technical: "Volume contraction", detail: "Wave C traded 0.50x the per-bar volume of wave A." },
    { name: "macd_divergence", state: "opposed", plain: "Bigger trend points down", technical: "MACD divergence", detail: "" },
  ],
};

const swingHistory = {
  swings: [
    swing(2, 92, "low", "first", "Swing low"), swing(8, 110, "high", "first", "Swing high"),
    swing(14, 102, "low", "higher", "Higher low"), swing(19, 106, "high", "lower", "Lower high"),
  ],
  trend: "mixed",
  higher_lows: 1,
  lower_highs: 1,
  floor: { kind: "rising_floor", count: 1, intact: true, points: [{ ts: 2 * HOUR, price: 92 }, { ts: 14 * HOUR, price: 102 }] },
  ceiling: { kind: "falling_ceiling", count: 1, intact: true, points: [{ ts: 8 * HOUR, price: 110 }, { ts: 19 * HOUR, price: 106 }] },
  watch_level: 102,
  headline: "The last dip stopped at a higher price than the one before it.",
  why: "One higher low is a start, not a run. Holding above $102.00 on the next dip would make it two.",
};

function wave(overrides = {}) {
  return {
    available: true,
    active_pattern: "abc_in_progress",
    status: "in_c_zone",
    bias: "bullish",
    timeframe: "1h",
    bar_seconds: HOUR,
    wave_points: [
      point("start", 2, 92, "low"), point("0", 8, 110, "high"), point("A", 14, 102, "low"),
      point("B", 19, 106, "high"), point("C", 25, 99.5, "low", false),
    ],
    projected_c_zone: { low: 93.06, high: 101.06, direction: "down", levels: { "0.618": 101.06, "1.000": 98, "1.272": 95.82, "1.618": 93.06 }, extended: { low: 93.06, high: 95.82 } },
    invalidation_price: 93.06,
    target_price: 106,
    fib_ratios: { b_retrace_of_a: 0.5, c_projection_of_a: 0.8125 },
    confluence_factors: [],
    confluence_score: 0.45,
    confidence: 0.57,
    confidence_label: "medium",
    summary: "A three-swing pullback inside a larger advance (A-B-C) is unfolding.",
    story,
    swing_history: swingHistory,
    chart: { candles, granularity_seconds: HOUR },
    ...overrides,
  };
}

const plan = {
  available: true, product_id: "SOL-USD", current_price: 100, price_as_of: Math.floor(Date.now() / 1000),
  market_structure: { support: 95, resistance: 112 },
  stop: { trigger_price: 94.6, limit_price: 94.3, invalidation_price: 95, why: ["A buffer below support."] },
  profit: { first_trim_price: 112 },
  chart: { candles, granularity_seconds: HOUR, last_close_at: 30 * HOUR },
};

const read = (overrides = {}) => ({
  summary: "Basic read.", direction: { label: "up" }, trading_activity: { label: "normal" }, confidence: "medium",
  timeframe: "1h", window_hours: 50, wave_analysis: wave(), ...overrides,
});

// Words a reader without charting vocabulary would not know.
const JARGON = /\bwave\b|a-b-c|\bfib|0\.618|1\.618|\bB \/ A\b|\bC \/ A\b|\bRSI\b|\bEMA\b|Bollinger|impulse/i;

describe("plain-English setup on the risk chart", () => {
  it("draws the prior advance, the dip zone, the recovery target and the break line", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);

    const prior = screen.getByTestId("wave-prior-move");
    expect(prior.textContent).toContain("Prior advance");
    expect(Number(prior.querySelector("line").getAttribute("stroke-width"))).toBeGreaterThan(2);

    const zone = screen.getByTestId("wave-c-zone");
    expect(Number(zone.querySelector("rect").getAttribute("height"))).toBeGreaterThan(1);
    expect(screen.getByTestId("wave-zone-label").textContent).toBe("Dip zone · $93.06 to $101.06");

    expect(screen.getByTestId("wave-target").textContent).toContain("Recovery target $106");
    const broken = screen.getByTestId("wave-invalidation");
    expect(broken.querySelector("line").getAttribute("stroke-dasharray")).toBe("6 4");
    expect(broken.querySelector("text").textContent).toBe("Setup breaks below $93.06");

    // The pullback after the peak is one line; the leg still forming is dashed.
    expect(screen.getByTestId("wave-polyline").getAttribute("points").trim().split(" ")).toHaveLength(3);
    expect(screen.getByTestId("wave-open-leg").getAttribute("stroke-dasharray")).toBeTruthy();
    expect(screen.getByTestId("risk-chart-wave-note").textContent).toContain("has not been tested against outcomes");
  });

  it("shows no wave letters or ratios on the chart, only on hover", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);
    const overlay = screen.getByTestId("wave-overlay");
    const visible = [...overlay.querySelectorAll("text")].map((node) => node.textContent).join(" | ");
    expect(visible).not.toMatch(JARGON);
    expect(visible).not.toMatch(/\b[ABC]\?/);
    for (const label of ["0", "A", "B", "C"]) {
      const node = screen.getByTestId(`wave-node-${label}`);
      expect(node.querySelector("text")).toBeNull();
      expect(node.querySelector("title").textContent).toBeTruthy();
    }
    expect(screen.getByTestId("wave-node-C").querySelector("title").textContent).toContain("still forming");
    expect(screen.getByTestId("risk-chart-wave-note").textContent).not.toMatch(JARGON);
  });

  it("marks earlier swing lows and highs with the run of higher lows", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);
    const markers = screen.getAllByTestId("swing-marker");
    expect(markers).toHaveLength(4);
    expect(markers.map((m) => m.getAttribute("data-relation"))).toContain("higher-low");
    expect(markers[2].querySelector("title").textContent).toBe("Higher low · $102.00");
    // One higher low is a start, not a floor: no run line until there are two.
    expect(screen.queryByTestId("swing-floor")).toBeNull();
    expect(screen.queryByTestId("swing-ceiling")).toBeNull();
  });

  it("draws a rising floor once there are two higher lows in a row", () => {
    const floor = { kind: "rising_floor", count: 2, intact: true, points: [{ ts: 2 * HOUR, price: 92 }, { ts: 14 * HOUR, price: 96 }, { ts: 22 * HOUR, price: 99 }] };
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave({ swing_history: { ...swingHistory, floor, higher_lows: 2 } })} />);
    const line = screen.getByTestId("swing-floor");
    expect(line.textContent).toContain("Rising floor · 2 higher lows");
    expect(line.querySelector("polyline").getAttribute("points").trim().split(" ")).toHaveLength(3);
    expect(line.getAttribute("opacity")).toBe("1");
  });

  it("captions only the parts that are on the chart", () => {
    const { unmount } = render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);
    const full = screen.getByTestId("risk-chart-wave-note").textContent;
    expect(full).toContain("The thick line marked 1 is the prior advance.");
    expect(full).toContain("The shaded band marked 2 is the dip zone");
    expect(full).toContain("The dotted line marked 3 is the recovery target.");
    unmount();
    const late = { ...plan, chart: { ...plan.chart, candles: candles.slice(10) } };
    render(<RiskLevelsChart plan={late} waveAnalysis={wave()} />);
    const partial = screen.getByTestId("risk-chart-wave-note").textContent;
    expect(partial).not.toContain("marked 1"); // the prior advance is off the left edge
    expect(partial).toContain("The shaded band marked 2");
  });

  it("keeps the overlay inside the plotted price range", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);
    const ys = screen.getByTestId("wave-polyline").getAttribute("points").trim().split(" ").map((p) => Number(p.split(",")[1]));
    const breakY = Number(screen.getByTestId("wave-invalidation").querySelector("line").getAttribute("y1"));
    const targetY = Number(screen.getByTestId("wave-target").querySelector("line").getAttribute("y1"));
    for (const y of [...ys, breakY, targetY]) {
      expect(y).toBeGreaterThanOrEqual(24);
      expect(y).toBeLessThanOrEqual(314);
    }
  });

  it("leaves the risk chart unchanged without a usable read", () => {
    const cases = [null, { available: false, active_pattern: "none" }, wave({ bar_seconds: 900 })];
    for (const waveAnalysis of cases) {
      const { unmount } = render(<RiskLevelsChart plan={plan} waveAnalysis={waveAnalysis} />);
      expect(screen.queryByTestId("wave-overlay")).toBeNull();
      expect(screen.queryByTestId("swing-history")).toBeNull();
      expect(screen.queryByTestId("risk-chart-wave-note")).toBeNull();
      expect(screen.getByText("Your levels on the chart")).toBeTruthy();
      unmount();
    }
  });

  it("still marks earlier swings when there is no active setup", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave({ active_pattern: "none", wave_points: [] })} />);
    expect(screen.queryByTestId("wave-overlay")).toBeNull();
    expect(screen.getAllByTestId("swing-marker")).toHaveLength(4);
  });

  it("skips swings that sit before the first plotted candle", () => {
    const late = { ...plan, chart: { ...plan.chart, candles: candles.slice(10) } };
    render(<RiskLevelsChart plan={late} waveAnalysis={wave()} />);
    expect(screen.queryByTestId("wave-node-0")).toBeNull();
    expect(screen.queryByTestId("wave-prior-move")).toBeNull();
    expect(screen.getByTestId("wave-node-A")).toBeTruthy();
    expect(screen.getAllByTestId("swing-marker")).toHaveLength(2);
    expect(wavePrices(wave(), 10 * HOUR)).not.toContain(110);
  });

  it("mirrors the wording for a bounce inside a decline", () => {
    const names = wavePlainLabels(wave({ bias: "bearish", story: undefined }));
    expect(names).toMatchObject({ priorMove: "Prior decline", zone: "Bounce zone", target: "Downside target", side: "above" });
  });
});

describe("chart read panel in plain English", () => {
  it("tells the setup as numbered steps with a plain headline", () => {
    render(<ChartReadPanel data={read()} />);
    const section = screen.getByTestId("chart-read-wave");
    expect(screen.getByTestId("chart-read-headline").textContent).toBe(story.headline);
    const steps = within(screen.getByTestId("chart-read-story")).getAllByRole("listitem");
    expect(steps.map((li) => li.querySelector("strong").textContent)).toEqual([
      "Prior advance", "Pullback / dip zone", "Recovery target", "Setup breaks below $93.06",
    ]);
    expect(screen.getByTestId("chart-read-step-zone").textContent).toContain("Price is inside it now.");
    expect(section.textContent).toContain("Read strength: medium");
    expect(screen.getByText("Basic read.")).toBeTruthy();
  });

  it("keeps wave letters and ratios inside the collapsed technical details", () => {
    render(<ChartReadPanel data={read()} />);
    const technical = screen.getByTestId("chart-read-technical");
    expect(technical.open).toBe(false);
    expect(technical.textContent).toContain("B / A: 0.50");
    expect(technical.textContent).toContain("A-B-C correction · wave C underway");

    const outside = screen.getByTestId("chart-read-wave").cloneNode(true);
    outside.querySelector('[data-testid="chart-read-technical"]').remove();
    outside.querySelectorAll("title").forEach((node) => node.remove());
    outside.querySelectorAll("[data-technical]").forEach((node) => node.remove());
    expect(outside.textContent).not.toMatch(JARGON);
  });

  it("turns supporting signs into plain badges with the technical name underneath", () => {
    render(<ChartReadPanel data={read()} />);
    const why = screen.getByTestId("chart-read-why");
    expect(why.textContent).toContain("Why this matters");
    const badge = within(why).getByText(/Dipping on lighter volume/).parentElement;
    expect(badge.textContent).toContain("Volume contraction");
    expect(badge.getAttribute("title")).toContain("0.50x");
    expect(within(why).getByText(/✕ Bigger trend points down/)).toBeTruthy();
  });

  it("explains the bigger picture from the swing history", () => {
    render(<ChartReadPanel data={read()} />);
    const history = screen.getByTestId("chart-read-history");
    expect(history.textContent).toContain("The last dip stopped at a higher price");
    expect(history.textContent).toContain("Holding above $102.00");
    expect(screen.getByTestId("chart-read-legend").textContent).toContain("dip that held higher");
    expect(within(screen.getByTestId("chart-read-wave-chart")).getAllByTestId("swing-marker")).toHaveLength(4);
  });

  it("still shows the bigger picture when there is no active setup", () => {
    const none = wave({ active_pattern: "none", wave_points: [], story: { kind: "none", headline: "No clear setup in the recent swings.", steps: [], why_it_matters: [] } });
    render(<ChartReadPanel data={read({ wave_analysis: none })} />);
    expect(screen.getByTestId("chart-read-headline").textContent).toBe("No clear setup in the recent swings.");
    expect(screen.queryByTestId("chart-read-story")).toBeNull();
    expect(screen.queryByTestId("chart-read-technical")).toBeNull();
    expect(screen.getByTestId("chart-read-history")).toBeTruthy();
  });

  it("omits the section when the read is unavailable", () => {
    const data = read({ wave_analysis: { available: false, active_pattern: "none", wave_points: [] } });
    render(<ChartReadPanel data={data} />);
    expect(screen.queryByTestId("chart-read-wave")).toBeNull();
    expect(waveIsDrawable(data.wave_analysis)).toBe(false);
    expect(wavePrices(data.wave_analysis)).toEqual([]);
  });
});

describe("chart read horizon switcher", () => {
  it.each(["swing", "cycle"])("shows top-down support on %s", (horizon) => {
    render(<ChartReadPanel data={read({ horizon, top_down_confluence: {
      available: true, at_multi_year_support: true,
      macro_log_support_box: { low: 60, high: 80 },
      micro_support_box: { low: 70, high: 90 },
      micro_timeframe: "1h", micro_breakout_pivot: 110,
    } })} />);
    const region = screen.getByTestId("top-down-confluence");
    expect(region.textContent).toContain("At observed multi-year support");
    expect(region.textContent).toContain("Wave B pivot");
    expect(region.textContent).toContain("1h support");
  });
  it("offers short-term, swing, macro and cycle and reports the choice", () => {
    const onHorizonChange = vi.fn();
    render(<ChartReadPanel data={read({ horizon: "swing" })} horizon="swing" onHorizonChange={onHorizonChange} />);
    const group = screen.getByTestId("chart-read-horizons");
    const buttons = within(group).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Short-term", "Swing", "Macro", "Cycle (Multi-Year)"]);
    expect(buttons.map((b) => b.getAttribute("aria-pressed"))).toEqual(["false", "true", "false", "false"]);
    expect(screen.getByTestId("chart-read-horizon-detail").textContent).toBe("1-hour candles · ~12 days");
    fireEvent.click(buttons[2]);
    expect(onHorizonChange).toHaveBeenCalledWith("macro");
    fireEvent.click(buttons[3]);
    expect(onHorizonChange).toHaveBeenCalledWith("cycle");
  });

  it("uses the horizon list the server sends", () => {
    const horizons = [{ key: "short", label: "Short-term", detail: "15-minute candles · ~3 days" }, { key: "macro", label: "Macro", detail: "4-hour candles · ~1 month" }];
    render(<ChartReadPanel data={read({ horizons, horizon: "macro" })} onHorizonChange={() => {}} />);
    expect(within(screen.getByTestId("chart-read-horizons")).getAllByRole("button")).toHaveLength(2);
    expect(screen.getByTestId("chart-read-horizon-detail").textContent).toBe("4-hour candles · ~1 month");
  });

  it("keeps the previous read on screen while another view loads", () => {
    render(<ChartReadPanel data={read()} loading horizon="macro" onHorizonChange={() => {}} />);
    expect(screen.getByText("Basic read.")).toBeTruthy();
    expect(screen.getByTestId("chart-read-horizon-detail").textContent).toBe("Reading this view…");
    expect(screen.queryByText("Reading the chart…")).toBeNull();
  });

  it("keeps the switcher when a view fails, and hides it without a handler", () => {
    const { unmount } = render(<ChartReadPanel data={null} error="unavailable" horizon="short" onHorizonChange={() => {}} />);
    expect(screen.getByText("Chart data temporarily unavailable.")).toBeTruthy();
    expect(screen.getByTestId("chart-read-horizons")).toBeTruthy();
    unmount();
    render(<ChartReadPanel data={read()} />);
    expect(screen.queryByTestId("chart-read-horizons")).toBeNull();
  });
});

describe("swing history helpers", () => {
  it("colours each swing by whether it came in higher or lower", () => {
    expect(swingColor({ kind: "low", relation: "higher" })).toBe(SWING_UP_COLOR);
    expect(swingColor({ kind: "low", relation: "equal" })).toBe(SWING_UP_COLOR);
    expect(swingColor({ kind: "low", relation: "lower" })).toBe(SWING_DOWN_COLOR);
    expect(swingColor({ kind: "high", relation: "higher" })).toBe(SWING_UP_COLOR);
    expect(swingColor({ kind: "high", relation: "lower" })).toBe(SWING_DOWN_COLOR);
  });

  it("names the run in plain words", () => {
    expect(runLabel({ kind: "rising_floor", count: 3 })).toBe("3 higher lows");
    expect(runLabel({ kind: "falling_ceiling", count: 1 })).toBe("1 lower high");
    expect(runLabel(null)).toBe("");
  });
});
