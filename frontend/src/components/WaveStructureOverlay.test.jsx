import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ChartReadPanel from "./ChartReadPanel.jsx";
import RiskLevelsChart from "./RiskLevelsChart.jsx";
import { chartCandles } from "./ChartReadChart.jsx";
import { cycleLevels, cyclePhaseAt, waveIsDrawable, wavePlainLabels, wavePrices } from "./WaveStructureOverlay.jsx";
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

describe("multi-year cycle anatomy", () => {
  it("offers immediate cycle access when the swing setup is unclear", () => {
    const onChange = vi.fn();
    render(<ChartReadPanel data={read({ wave_analysis: { available: false, active_pattern: "none" } })}
      horizon="swing" onHorizonChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /No clear swing setup/ }));
    expect(onChange).toHaveBeenCalledWith("cycle");
  });

  it("draws the historical pivots, base boundaries and Wave B target on the one chart with the cycle story", () => {
    const anatomy = {
      available: true, accumulation_base: { floor: 10, ceiling: 25, duration_months: 21, stage_label: "Deep Accumulation · 21 mo base" },
      pivots: ["peak", "A", "B", "C", "D", "E"].map((key, i) => ({
        key, label: key, timestamp: i * 86400, date: `2020-01-0${i + 1}`, price: [100, 30, 60, 10, 25, 12][i],
      })),
      chart_closes: [[0, 100], [5 * 86400, 12]],
      story: [{ step: "base", text: "21-month base after the A-B-C retreat." }],
      projections: [{ key: "target_1", label: "Target 1", price: 60, distance_pct: 400 }],
    };
    render(<ChartReadPanel data={read({ horizon: "cycle", multiyear_cycle_anatomy: anatomy, wave_analysis: { available: false } })} horizon="cycle" />);
    const chart = screen.getByTestId("chart-read-chart");
    // With no candles the cycle view falls back to the anatomy's close line.
    expect(chart.getAttribute("data-mode")).toBe("line");
    for (const key of ["peak", "A", "B", "C", "D", "E"]) {
      expect(within(chart).getByTestId(`cycle-pivot-${key}`).textContent).toBe(key === "peak" ? "PEAK" : key);
    }
    for (const label of [/Accumulation Floor/, /Breakout Ceiling/, /Wave B Target/]) expect(within(chart).getByText(label)).toBeInTheDocument();
    expect(within(chart).getByTestId("cycle-overlay").querySelectorAll('line[stroke-dasharray="6 4"]')).toHaveLength(3);
    expect(screen.getByText("21-month base after the A-B-C retreat.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Multi-Year Cycle Story & Projected Targets" })).toBeInTheDocument();
  });
});

// A small daily cycle: peak, three-leg decline, then a base between $10 and $25.
const DAY = 86400;
const cyclePath = [100, 90, 100, 80, 60, 45, 38, 33, 31, 30, 30, 34, 40, 46, 52, 57, 59, 60, 60, 52, 40, 30, 22, 16, 12, 11, 10, 11, 13, 15,
  17, 19, 20, 22, 23, 24, 24, 25, 25, 25, 25, 22, 19, 16, 14, 13, 12, 12, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21];
const dailyBars = cyclePath.map((close, i) => {
  const open = i ? cyclePath[i - 1] : close;
  return { timestamp: i * DAY, open, high: Math.max(open, close) * 1.02, low: Math.min(open, close) * 0.98, close, volume: 1000 + i * 10 };
});
const pivotSpec = [["peak", 2, 100, "high"], ["A", 9, 30, "low"], ["B", 17, 60, "high"], ["C", 26, 10, "low"], ["D", 37, 25, "high"], ["E", 46, 12, "low"]];
const dailyAnatomy = {
  available: true,
  pivots: pivotSpec.map(([key, day, price, kind], i) => ({
    key, kind, label: { peak: "Macro Cycle Peak", A: "Wave A Crash Low", B: "Wave B Bull-Trap High", C: "Wave C Capitulation Low", D: "Wave D Compression High", E: "Wave E Compression Low" }[key],
    timestamp: day * DAY, date: new Date(day * DAY * 1000).toISOString().slice(0, 10), price,
    move_pct: i ? Math.round((price / pivotSpec[i - 1][2] - 1) * 1000) / 10 : null,
  })),
  accumulation_base: { floor: 10, ceiling: 25, duration_months: 1.1, stage: "mid_base", stage_label: "Mid Base · 1 mo base", start_timestamp: 26 * DAY, start_date: "1970-01-27" },
  projections: [
    { key: "breakout_trigger", label: "Breakout Reclaim Trigger", price: 25, distance_pct: 19 },
    { key: "target_1", label: "Target 1 · Prior Wave B High", price: 60, distance_pct: 185.7 },
  ],
  chart_closes: dailyBars.map((bar) => [bar.timestamp, bar.close]),
  story: [{ step: "base", text: "1-month base $10 – $25" }],
};
const SLOT = (652 - 8) / dailyBars.length;
const candleX = (i) => 8 + (i + 0.5) * SLOT;
const cycleData = (overrides = {}) => read({
  horizon: "cycle", timeframe: "1d", candles: dailyBars, multiyear_cycle_anatomy: dailyAnatomy,
  wave_analysis: { available: false, active_pattern: "none" }, ...overrides,
});

describe("interactive chart", () => {
  it("draws OHLC candlesticks with a volume histogram by default and toggles to an area line", () => {
    render(<ChartReadPanel data={cycleData()} horizon="cycle" />);
    const chart = screen.getByTestId("chart-read-chart");
    expect(chart.getAttribute("data-mode")).toBe("candles");
    expect(within(chart).getAllByTestId("chart-candle")).toHaveLength(dailyBars.length);
    expect(within(chart).getByTestId("chart-volume").querySelectorAll("rect")).toHaveLength(dailyBars.length);
    fireEvent.click(screen.getByTestId("chart-mode-line"));
    expect(chart.getAttribute("data-mode")).toBe("line");
    expect(within(chart).queryAllByTestId("chart-candle")).toHaveLength(0);
    expect(within(chart).getByTestId("chart-line").querySelector("polyline")).toBeTruthy();
    expect(within(chart).getByTestId("chart-volume").querySelectorAll("rect")).toHaveLength(dailyBars.length);
  });

  it("snaps a crosshair to the candle under the cursor and fills the HUD", () => {
    render(<ChartReadPanel data={cycleData()} horizon="cycle" />);
    const chart = screen.getByTestId("chart-read-chart");
    // At rest the HUD reads the latest candle.
    expect(screen.getByTestId("chart-hud").getAttribute("data-latest")).toBe("true");
    expect(screen.getByTestId("chart-hud-phase").textContent).toContain("Month 2 of Accumulation Base");

    fireEvent.mouseMove(chart, { clientX: candleX(22) + 2, clientY: 120 });
    expect(within(chart).getByTestId("chart-crosshair")).toBeTruthy();
    const hud = screen.getByTestId("chart-hud");
    expect(hud.getAttribute("data-latest")).toBe("false");
    expect(screen.getByTestId("chart-hud-date").textContent).toContain("1970");
    expect(screen.getByTestId("chart-hud-ohlc").textContent).toBe("O / H / L / C$30.00 / $30.60 / $21.56 / $22.00");
    expect(screen.getByTestId("chart-hud-change").textContent).toContain("−26.7%");
    expect(screen.getByTestId("chart-hud-volume").textContent).toContain("1.2K");
    expect(screen.getByTestId("chart-hud-phase").textContent).toContain("Wave C Retreat");
    expect(screen.getByTestId("chart-hud-ceiling").textContent).toContain("+13.6%");
    expect(screen.getByTestId("chart-hud-floor").textContent).toContain("−54.5%");

    fireEvent.mouseMove(chart, { clientX: candleX(30), clientY: 120 });
    expect(screen.getByTestId("chart-hud-phase").textContent).toContain("Month 1 of Accumulation Base · Wave D Compression Rally");
    fireEvent.keyDown(chart, { key: "ArrowLeft" });
    expect(screen.getByTestId("chart-hud-ohlc").textContent).toContain("$15.00");
    fireEvent.mouseLeave(chart);
    expect(within(chart).queryByTestId("chart-crosshair")).toBeNull();
  });

  it("inspects a pivot badge or a level line with its date, price, move and explanation", () => {
    render(<ChartReadPanel data={cycleData()} horizon="cycle" />);
    expect(screen.getByTestId("chart-inspect-hint")).toBeTruthy();
    fireEvent.mouseEnter(screen.getByTestId("cycle-pivot-C"));
    expect(screen.getByTestId("chart-inspect").getAttribute("data-key")).toBe("C");
    fireEvent.mouseLeave(screen.getByTestId("cycle-pivot-C"));

    fireEvent.click(screen.getByTestId("cycle-pivot-B"));
    const card = screen.getByTestId("chart-inspect");
    expect(card.textContent).toContain("Wave B Bull-Trap High");
    expect(screen.getByTestId("chart-inspect-date").textContent).toBe("1970-01-18");
    expect(screen.getByTestId("chart-inspect-price").textContent).toBe("$60.00");
    expect(screen.getByTestId("chart-inspect-move").textContent).toBe("+100.0% from A");
    expect(screen.getByTestId("chart-inspect-text").textContent).toContain("bull trap");
    expect(screen.getByTestId("chart-chip-B").getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByTestId("cycle-level-ceiling"));
    expect(screen.getByTestId("chart-inspect").getAttribute("data-key")).toBe("ceiling");
    expect(screen.getByTestId("chart-inspect-move").textContent).toBe("+19.0% from price now");
    expect(screen.getByTestId("chart-inspect-text").textContent).toContain("breakout trigger");
    fireEvent.click(screen.getByRole("button", { name: "Close inspector" }));
    expect(screen.getByTestId("chart-inspect-hint")).toBeTruthy();
  });

  it("zooms with the buttons and the wheel, pans by drag, and resets", () => {
    render(<ChartReadPanel data={cycleData()} horizon="cycle" />);
    const chart = screen.getByTestId("chart-read-chart");
    const range = () => screen.getByTestId("chart-read-chart-range").textContent;
    expect(range()).toBe("60 of 60 candles");
    fireEvent.click(screen.getByTestId("chart-zoom-in"));
    expect(range()).toBe("48 of 60 candles · zoomed");
    fireEvent.wheel(chart, { deltaY: -100, clientX: candleX(59) });
    expect(within(chart).getAllByTestId("chart-candle").length).toBeLessThan(48);
    const before = within(chart).getAllByTestId("chart-candle").length;
    fireEvent.mouseDown(chart, { button: 0, clientX: 300, clientY: 100 });
    fireEvent.mouseMove(chart, { clientX: 420, clientY: 100 });
    fireEvent.mouseUp(chart);
    expect(within(chart).getAllByTestId("chart-candle")).toHaveLength(before);
    fireEvent.click(screen.getByTestId("chart-zoom-reset"));
    expect(range()).toBe("60 of 60 candles");
  });

  it("keeps the multi-year levels on a short-term chart, pinned to the edge with their distance", () => {
    render(<ChartReadPanel data={read({ horizon: "swing" })} horizon="swing" cycleAnatomy={dailyAnatomy} />);
    const chart = screen.getByTestId("chart-read-chart");
    for (const key of ["ceiling", "wave_b_target", "floor"]) {
      expect(within(chart).getByTestId(`cycle-level-${key}`).getAttribute("data-offscale")).toBe("true");
    }
    expect(within(chart).getByTestId("cycle-level-floor").textContent).toMatch(/▼ Accumulation Floor \$10\.00 \(−\d+\.\d%\)/);
    // The pivots are years before these candles: they stay inspectable as chips.
    expect(within(chart).queryByTestId("cycle-pivot-B")).toBeNull();
    expect(screen.getByTestId("chart-chip-B").className).toContain("is-offchart");
    expect(screen.getByTestId("chart-hud-ceiling")).toBeTruthy();
    // The swing setup is drawn on the same chart.
    expect(within(chart).getByTestId("wave-overlay")).toBeTruthy();

    fireEvent.click(screen.getByTestId("chart-toggle-fit"));
    expect(within(chart).getByTestId("cycle-level-floor").getAttribute("data-offscale")).toBe("false");
    fireEvent.click(screen.getByTestId("chart-toggle-levels"));
    expect(within(chart).queryByTestId("cycle-overlay")).toBeNull();
    expect(screen.queryByTestId("chart-pivot-chips")).toBeNull();
  });

  it("keeps the same chart mounted, with its settings, across every horizon switch and while loading", () => {
    const { rerender } = render(<ChartReadPanel data={null} loading horizon="cycle" onHorizonChange={() => {}} />);
    const frame = screen.getByTestId("chart-read-chart-frame");
    expect(screen.getByTestId("chart-read-chart-busy").textContent).toBe("Loading Cycle (Multi-Year) view…");
    rerender(<ChartReadPanel data={cycleData()} horizon="cycle" onHorizonChange={() => {}} />);
    expect(screen.getByTestId("chart-read-chart-frame")).toBe(frame);
    fireEvent.click(screen.getByTestId("chart-mode-line"));

    for (const horizon of ["short", "swing", "macro"]) {
      // Switching: the previous read stays on screen, dimmed, while the next loads.
      rerender(<ChartReadPanel data={cycleData()} loading horizon={horizon} onHorizonChange={() => {}} />);
      expect(screen.getByTestId("chart-read-chart-frame")).toBe(frame);
      expect(screen.getByTestId("chart-read-chart-busy")).toBeTruthy();
      rerender(<ChartReadPanel data={read({ horizon })} horizon={horizon} cycleAnatomy={dailyAnatomy} onHorizonChange={() => {}} />);
      expect(screen.getByTestId("chart-read-chart-frame")).toBe(frame);
      expect(frame.getAttribute("data-horizon")).toBe(horizon);
      expect(screen.getByTestId("chart-read-chart").getAttribute("data-mode")).toBe("line");
      expect(screen.getByTestId("cycle-level-ceiling")).toBeTruthy();
    }
    rerender(<ChartReadPanel data={null} error="unavailable" horizon="short" onHorizonChange={() => {}} />);
    expect(screen.getByTestId("chart-read-chart-frame")).toBe(frame);
  });

  it("names the cycle phase of any date from the pivots and the base", () => {
    expect(cyclePhaseAt(dailyAnatomy, 0, 100)).toBe("Advance into the cycle peak");
    expect(cyclePhaseAt(dailyAnatomy, 5 * DAY, 45)).toBe("Wave A Decline");
    expect(cyclePhaseAt(dailyAnatomy, 12 * DAY, 40)).toBe("Wave B Relief Rally");
    expect(cyclePhaseAt(dailyAnatomy, 20 * DAY, 40)).toBe("Wave C Retreat");
    expect(cyclePhaseAt(dailyAnatomy, 26 * DAY, 10)).toBe("Month 1 of Accumulation Base · Wave D Compression Rally");
    expect(cyclePhaseAt(dailyAnatomy, (26 + 400) * DAY, 15)).toBe("Month 14 of Accumulation Base");
    expect(cyclePhaseAt(dailyAnatomy, 58 * DAY, 30)).toBe("Breakout above the accumulation base");
    expect(cyclePhaseAt({ available: false }, 0, 1)).toBeNull();
    expect(cycleLevels(dailyAnatomy).map((l) => l.key)).toEqual(["wave_b_target", "ceiling", "floor"]);
  });

  it("builds candles from the full OHLCV series, the wave candles, or the cycle close line", () => {
    expect(chartCandles({ candles: dailyBars })).toHaveLength(60);
    expect(chartCandles({ wave_analysis: { chart: { candles } } })[0]).toMatchObject({ t: 0, l: candles[0][1], h: candles[0][2], o: candles[0][3], c: candles[0][4] });
    const closes = chartCandles({}, dailyAnatomy);
    expect(closes).toHaveLength(60);
    expect(closes[0].closeOnly).toBe(true);
    expect(chartCandles({ candles: [{ timestamp: 1, open: 0, high: 1, low: 1, close: 1, volume: 1 }] })).toEqual([]);
  });
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
    expect(within(screen.getByTestId("chart-read-chart")).getAllByTestId("swing-marker")).toHaveLength(4);
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

// Shapes copied from chart_structure.multi_year_context / top_down_confluence
// run on the backend's theta_wxy_confluence fixture.
const rsi = (timeframe, value, regime, extra = {}) => ({
  timeframe, value, previous: value - 1, regime, near_bull_support: false, trend: "down", bars: 100, ...extra,
});

const cycleContext = (overrides = {}) => ({
  available: true,
  is_multi_year: true,
  current_price: 0.7996,
  log_fib_retracements: { "0.618": 1.3875, "0.886": 0.9002 },
  rsi_regimes: {
    "1d": rsi("1d", 78.79, "growth_expansion"),
    "1w": rsi("1w", 26.41, "oversold_compression"),
    "1m": rsi("1m", 42.41, "no_mans_land"),
  },
  weekly_stoch_rsi: { available: true, weekly_stoch_rsi_k: 82.16, weekly_stoch_rsi_d: 53.89, previous_k: 55.97, direction: "bullish_expansion", bars: 157 },
  monthly_cycle_exhaustion: {
    available: true, monthly_bearish_streak: 10, streak_threshold: 18, multi_year_oversold_exhaustion: false,
    histogram_shrinking: false, monthly_rsi: 42.41, monthly_bars: 35,
  },
  weekly_sma_ladder: {
    price: 0.7996, weekly_bars: 157, sma_50w: 1.0162, sma_100w: 1.1934, sma_200w: null,
    levels: [
      { key: "sma_50w", period: 50, value: 1.0162, available: true, role: "resistance", distance_pct: 27.08, bars_needed: 50 },
      { key: "sma_100w", period: 100, value: 1.1934, available: true, role: "resistance", distance_pct: 49.24, bars_needed: 100 },
      { key: "sma_200w", period: 200, value: null, available: false, role: null, distance_pct: null, bars_needed: 200 },
    ],
    overhead_resistance: ["sma_50w", "sma_100w"], reclaimed_support: [],
  },
  daily_structure: {
    structural_low: { price: 0.7489, timestamp: 1792108800 },
    low_confirmation_pivot: { price: 1.0714, timestamp: 1782864000, kind: "wave_4_swing_high", distance_pct: 33.98 },
    confirmation_breakout: { broken: false },
  },
  outcome_validated: false,
  ...overrides,
});

const cluster = {
  low: 2.6404, high: 2.6636, mid: 2.652, retracement_ratio: 0.786, retracement_price: 2.6636,
  extension_ratio: 1.618, extension_price: 2.6404, spread_pct: 0.88, score: 0.854, conviction: "high",
  position: "above_price", distance_pct: 231.64,
};

const cycleTop = (overrides = {}) => ({
  available: true,
  at_multi_year_support: true,
  in_accumulation_box: true,
  macro_log_support_box: { low: 0.9002, high: 1.3875 },
  micro_support_box: null, micro_breakout_pivot: null, micro_timeframe: null,
  cycle_pattern: { kind: "wxy_terminal_sweep", description: "Three-leg decline from the cycle high (5-3-5 / W-X-Y). The last leg has reached the base the prior advance started from." },
  confirmation_breakout: { broken: false },
  low_confirmation_pivot: { price: 1.0714, timestamp: 1782864000, kind: "wave_4_swing_high", distance_pct: 33.98, message: "Break above $1.07 signals cycle low is in" },
  accumulation_invalidation_stop: {
    stop_price: 0.7339, stop_distance_pct: 8.22, reference_low: 0.7489, basis: "wave_c_low", buffer_pct: 2.0, tight: true,
    message: "Accumulation read is invalid below $0.7339 (8.2% under price)",
  },
  fib_confluence_clusters: [cluster],
  rollover_target_box: {
    available: true, label: "Conservative / High-Probability Rollover Zone", low: 2.0309, high: 2.6636,
    levels: { "0.618": 2.0309, "0.702": 2.3258, "0.786": 2.6636 }, price_position: "below",
    extension_confluence: [{ source: "secondary_range", ratio: 1.618, price: 2.6404 }], clusters: [cluster],
  },
  full_extension_targets: {
    available: true, label: "Full Alt-Season Extension Confluence",
    levels: { "1.618": 2.6404, "2.618": 5.7531, "3.618": 12.535, "4.236": 20.2837 },
    targets: [
      { ratio: 1.618, price: 2.6404, confluence: true, distance_pct: 230.2 },
      { ratio: 2.618, price: 5.7531, confluence: false, distance_pct: 619.45 },
      { ratio: 3.618, price: 12.535, confluence: false, distance_pct: 1467.56 },
      { ratio: 4.236, price: 20.2837, confluence: false, distance_pct: 2436.6 },
    ],
    clusters: [cluster],
  },
  macro_regime_gate: "risk_off_headwind",
  liquidity_rotation_stage: "stage_1_macro_compression",
  active_target_tier: "rollover_target_box",
  outcome_validated: false,
  ...overrides,
});

const cycleRegime = (overrides = {}) => ({
  available: true,
  liquidity_rotation_stage: "stage_1_macro_compression",
  stage_number: 1,
  stage_label: "Stage 1 · Macro compression",
  macro_regime_gate: "risk_off_headwind",
  gate_label: "Risk-off headwind",
  active_target_tier: "rollover_target_box",
  reasons: ["Neither the majors nor the altcoin index is in an expansion.", "BTC is below its 50-week average with weak weekly momentum, which works against altcoin recoveries."],
  ...overrides,
});

const cycleRead = (overrides = {}) => read({
  horizon: "cycle", timeframe: "1d",
  multi_year_context: cycleContext(), top_down_confluence: cycleTop(), macro_industry_regime: cycleRegime(),
  ...overrides,
});

describe("chart read cycle horizon", () => {
  it("renders the cycle read only on the cycle view", () => {
    const { unmount } = render(<ChartReadPanel data={cycleRead({ horizon: "swing" })} />);
    expect(screen.queryByTestId("cycle-read")).toBeNull();
    unmount();
    render(<ChartReadPanel data={cycleRead()} />);
    expect(screen.getByTestId("cycle-read")).toBeTruthy();
    expect(screen.getByTestId("cycle-pattern").textContent).toContain("Three-leg decline");
  });

  it("shows the industry gate with its stage, and says so when it is warming", () => {
    const { unmount } = render(<ChartReadPanel data={cycleRead()} />);
    const badge = screen.getByTestId("cycle-gate-badge");
    expect(badge.getAttribute("data-gate")).toBe("risk_off_headwind");
    expect(badge.textContent).toBe("Risk-off headwind");
    expect(badge.className).toContain("cycle-read__badge--danger");
    expect(screen.getByTestId("cycle-gate").textContent).toContain("Stage 1 · Macro compression");
    unmount();
    render(<ChartReadPanel data={cycleRead({
      macro_industry_regime: { available: false, reason: "warming" },
      top_down_confluence: cycleTop({ macro_regime_gate: null, liquidity_rotation_stage: undefined }),
    })} />);
    expect(screen.getByTestId("cycle-gate-badge").getAttribute("data-gate")).toBe("unavailable");
    expect(screen.getByTestId("cycle-gate-badge").textContent).toBe("Warming up");
  });

  it("names the RSI regime on each timeframe around the 40 and 60 lines", () => {
    render(<ChartReadPanel data={cycleRead()} />);
    const tile = (tf) => screen.getByTestId(`cycle-rsi-${tf}`);
    expect(tile("1d").getAttribute("data-regime")).toBe("growth_expansion");
    expect(tile("1d").textContent).toContain("78.8");
    expect(tile("1d").textContent).toContain("Above 60 · growth expansion");
    expect(tile("1w").textContent).toContain("26.4");
    expect(tile("1w").textContent).toContain("Below 40 · oversold compression");
    expect(tile("1m").textContent).toContain("40–60 · no-man's-land");
    expect(tile("1m").textContent).not.toContain("Near 40 support");
  });

  it("flags RSI near 40 support in an uptrend and a timeframe with no history", () => {
    const context = cycleContext();
    context.rsi_regimes["1w"] = rsi("1w", 41.2, "no_mans_land", { near_bull_support: true, trend: "up" });
    context.rsi_regimes["1m"] = { timeframe: "1m", value: null, regime: "unavailable", near_bull_support: false };
    render(<ChartReadPanel data={cycleRead({ multi_year_context: context })} />);
    expect(screen.getByTestId("cycle-rsi-1w").textContent).toContain("Near 40 support in an uptrend");
    expect(screen.getByTestId("cycle-rsi-1m").textContent).toContain("—");
    expect(screen.getByTestId("cycle-rsi-1m").textContent).toContain("Not enough history");
  });

  it("reads weekly StochRSI and the monthly streak, with the exhaustion badge only when it fired", () => {
    const { unmount } = render(<ChartReadPanel data={cycleRead()} />);
    const stoch = screen.getByTestId("cycle-stoch");
    expect(stoch.getAttribute("data-direction")).toBe("bullish_expansion");
    expect(stoch.textContent).toContain("82 / 54");
    expect(stoch.textContent).toContain("Rising · %K above %D");
    const streak = screen.getByTestId("cycle-exhaustion");
    expect(streak.getAttribute("data-exhausted")).toBe("false");
    expect(streak.textContent).toContain("10 / 18");
    expect(streak.textContent).toContain("Not exhausted");
    expect(screen.queryByTestId("cycle-exhaustion-badge")).toBeNull();
    unmount();

    const context = cycleContext({
      weekly_stoch_rsi: { available: false, reason: "needs_more_weekly_history", direction: null },
      monthly_cycle_exhaustion: { available: true, monthly_bearish_streak: 21, streak_threshold: 18, multi_year_oversold_exhaustion: true, histogram_shrinking: true },
    });
    render(<ChartReadPanel data={cycleRead({ multi_year_context: context })} />);
    expect(screen.getByTestId("cycle-stoch").textContent).toContain("Needs more weekly history");
    expect(screen.getByTestId("cycle-exhaustion-badge").textContent).toBe("Multi-year exhaustion");
    expect(screen.getByTestId("cycle-exhaustion").textContent).toContain("21 / 18");
  });

  it("lays out the 50W, 100W and 200W averages with their role, and a missing one as missing", () => {
    const context = cycleContext();
    context.weekly_sma_ladder.levels[0] = { key: "sma_50w", period: 50, value: 0.71, available: true, role: "support", distance_pct: -11.2, bars_needed: 50 };
    render(<ChartReadPanel data={cycleRead({ multi_year_context: context })} />);
    const ladder = screen.getByTestId("cycle-sma-ladder");
    expect(within(ladder).getByTestId("cycle-sma_50w").textContent).toContain("Below price · support");
    expect(within(ladder).getByTestId("cycle-sma_50w").textContent).toContain("$0.71");
    expect(within(ladder).getByTestId("cycle-sma_100w").textContent).toContain("$1.19");
    expect(within(ladder).getByTestId("cycle-sma_100w").textContent).toContain("Above price · resistance");
    expect(within(ladder).getByTestId("cycle-sma_100w").textContent).toContain("+49.2%");
    const missing = within(ladder).getByTestId("cycle-sma_200w");
    expect(missing.getAttribute("data-role")).toBe("unavailable");
    expect(missing.textContent).toContain("Needs 200 weekly bars · 157 so far");
    expect(missing.textContent).not.toContain("$");
  });

  it("states the confirmation pivot and the invalidation stop in the backend's words", () => {
    render(<ChartReadPanel data={cycleRead()} />);
    const pivot = screen.getByTestId("cycle-pivot");
    expect(pivot.textContent).toContain("$1.07");
    expect(pivot.textContent).toContain("Break above $1.07 signals cycle low is in");
    const stop = screen.getByTestId("cycle-stop");
    expect(stop.textContent).toContain("$0.7339");
    expect(stop.textContent).toContain("Accumulation read is invalid below $0.7339 (8.2% under price)");
    expect(stop.textContent).toContain("Tight");
    expect(stop.textContent).toContain("2% under the last leg's low");
    expect(screen.queryByTestId("cycle-breakout")).toBeNull();
  });

  it("does not call a pivot break a cycle low away from support, and shows no stop there", () => {
    render(<ChartReadPanel data={cycleRead({ top_down_confluence: cycleTop({
      at_multi_year_support: false, in_accumulation_box: false, low_confirmation_pivot: null, accumulation_invalidation_stop: null,
      confirmation_breakout: { broken: true, pivot_price: 0.95, bars_since_break: 4, recent: true },
    }) })} />);
    const pivot = screen.getByTestId("cycle-pivot");
    expect(pivot.textContent).toContain("$1.07");
    expect(pivot.textContent).not.toContain("cycle low is in");
    expect(pivot.textContent).toContain("not at multi-year support");
    expect(screen.getByTestId("cycle-stop").textContent).toContain("None.");
    expect(screen.getByTestId("cycle-breakout").textContent).toContain("Closed above it 4 days ago");
  });

  it("lists where the two Fibonacci grids overlap, or says they do not", () => {
    const { unmount } = render(<ChartReadPanel data={cycleRead()} />);
    const found = within(screen.getByTestId("cycle-clusters")).getAllByTestId("cycle-cluster");
    expect(found).toHaveLength(1);
    expect(found[0].textContent).toContain("$2.64–$2.66");
    expect(found[0].textContent).toContain("0.786 retracement meets 1.618 extension");
    expect(found[0].textContent).toContain("+231.6% from price");
    unmount();
    render(<ChartReadPanel data={cycleRead({ top_down_confluence: cycleTop({ fib_confluence_clusters: [] }) })} />);
    expect(screen.getByTestId("cycle-clusters").textContent).toContain("do not overlap");
  });

  it("separates the rollover box from the full extensions and marks the active tier", () => {
    const { unmount } = render(<ChartReadPanel data={cycleRead()} />);
    expect(screen.getByTestId("cycle-targets").getAttribute("data-active-tier")).toBe("rollover_target_box");
    const box = screen.getByTestId("cycle-rollover-box");
    const full = screen.getByTestId("cycle-full-extension");
    expect(box.getAttribute("data-active")).toBe("true");
    expect(box.textContent).toContain("Active expectation");
    expect(box.textContent).toContain("$2.03–$2.66");
    expect(box.textContent).toContain("Price is below the zone");
    expect(box.textContent).toContain("1.618 extension at $2.64");
    expect(full.getAttribute("data-active")).toBe("false");
    expect(full.textContent).toContain("Reference only");
    expect(full.textContent).toContain("$5.75");
    expect(full.textContent).toContain("$20.28");
    expect(full.querySelectorAll('[data-confluence="true"]')).toHaveLength(1);
    unmount();

    render(<ChartReadPanel data={cycleRead({
      top_down_confluence: cycleTop({ active_target_tier: "full_extension_targets", macro_regime_gate: "risk_on_aligned", liquidity_rotation_stage: "stage_3_alt_index_breakout" }),
      macro_industry_regime: cycleRegime({ macro_regime_gate: "risk_on_aligned", gate_label: "Risk-on aligned", stage_number: 3, stage_label: "Stage 3 · Alt index breakout" }),
    })} />);
    expect(screen.getByTestId("cycle-full-extension").getAttribute("data-active")).toBe("true");
    expect(screen.getByTestId("cycle-rollover-box").getAttribute("data-active")).toBe("false");
    expect(screen.getByTestId("cycle-gate-badge").className).toContain("cycle-read__badge--ok");
  });

  it("explains a tier the coin has no levels for instead of inventing them", () => {
    render(<ChartReadPanel data={cycleRead({ top_down_confluence: cycleTop({
      full_extension_targets: { available: false, reason: "no_secondary_range" }, fib_confluence_clusters: [],
    }) })} />);
    const full = screen.getByTestId("cycle-full-extension");
    expect(full.textContent).toContain("No counter-rally inside the decline to extend from.");
    expect(full.textContent).not.toContain("$");
  });

  it("keeps the momentum reads when the top-down read is unavailable", () => {
    render(<ChartReadPanel data={cycleRead({ top_down_confluence: { available: false, reason: "history_unavailable" } })} />);
    expect(screen.getByTestId("cycle-momentum")).toBeTruthy();
    expect(screen.getByTestId("cycle-top-unavailable")).toBeTruthy();
    expect(screen.queryByTestId("cycle-targets")).toBeNull();
    expect(screen.getByTestId("cycle-pivot").textContent).not.toContain("multi-year support");
  });

  it("renders nothing for the cycle read without a multi-year context", () => {
    render(<ChartReadPanel data={cycleRead({ multi_year_context: { available: false, reason: "no_daily_history" } })} />);
    expect(screen.queryByTestId("cycle-read")).toBeNull();
    expect(screen.getByText("Basic read.")).toBeTruthy();
  });
});
