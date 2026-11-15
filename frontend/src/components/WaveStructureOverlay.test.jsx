import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ChartReadPanel from "./ChartReadPanel.jsx";
import RiskLevelsChart from "./RiskLevelsChart.jsx";
import { waveIsDrawable, wavePrices } from "./WaveStructureOverlay.jsx";

const HOUR = 3600;
const candles = Array.from({ length: 30 }, (_, i) => {
  const open = 100 + Math.sin(i / 3) * 4;
  const close = 100 + Math.sin((i + 1) / 3) * 4;
  return [i * HOUR, Math.min(open, close) - 1, Math.max(open, close) + 1, open, close, 10 + i];
});

const point = (label, i, price, kind, confirmed = true) => ({ label, ts: i * HOUR, price, kind, index: i, confirmed });

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
    confluence_factors: [
      { name: "higher_tf_trend", state: "present" }, { name: "rsi_divergence", state: "absent" },
      { name: "volume_contraction", state: "present" },
    ],
    confluence_score: 0.45,
    confidence: 0.57,
    confidence_label: "medium",
    summary: "A three-swing pullback inside a larger advance (A-B-C) is unfolding.",
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

describe("wave structure overlay", () => {
  it("draws the swing polyline, labeled nodes, C zone and break line on the risk chart", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);

    const line = screen.getByTestId("wave-polyline");
    expect(line.getAttribute("points").trim().split(" ")).toHaveLength(4); // start, 0, A, B
    for (const label of ["0", "A", "B"]) {
      expect(screen.getByTestId(`wave-node-${label}`).querySelector("text").textContent).toBe(label);
    }
    // Wave C is still forming: dashed leg and a question mark on its node.
    expect(screen.getByTestId("wave-node-C").querySelector("text").textContent).toBe("C?");
    expect(screen.getByTestId("wave-open-leg").getAttribute("stroke-dasharray")).toBeTruthy();

    const zone = screen.getByTestId("wave-c-zone").querySelector("rect");
    expect(Number(zone.getAttribute("height"))).toBeGreaterThan(1);
    expect(screen.getByTestId("wave-c-zone").textContent).toContain("1.000");

    const broken = screen.getByTestId("wave-invalidation");
    expect(broken.querySelector("line").getAttribute("stroke-dasharray")).toBe("6 4");
    expect(broken.textContent).toContain("Wave count breaks below $93.06");
    expect(screen.getByTestId("risk-chart-wave-note").textContent).toContain("not outcome-validated");
  });

  it("keeps the overlay inside the plotted price range", () => {
    render(<RiskLevelsChart plan={plan} waveAnalysis={wave()} />);
    const ys = screen.getByTestId("wave-polyline").getAttribute("points").trim().split(" ").map((p) => Number(p.split(",")[1]));
    const breakY = Number(screen.getByTestId("wave-invalidation").querySelector("line").getAttribute("y1"));
    for (const y of [...ys, breakY]) {
      expect(y).toBeGreaterThanOrEqual(24);
      expect(y).toBeLessThanOrEqual(314);
    }
  });

  it("leaves the risk chart unchanged without a usable wave read", () => {
    const cases = [null, { available: false, active_pattern: "none" }, wave({ active_pattern: "none" }), wave({ bar_seconds: 900 })];
    for (const waveAnalysis of cases) {
      const { unmount } = render(<RiskLevelsChart plan={plan} waveAnalysis={waveAnalysis} />);
      expect(screen.queryByTestId("wave-overlay")).toBeNull();
      expect(screen.queryByTestId("risk-chart-wave-note")).toBeNull();
      expect(screen.getByText("Your levels on the chart")).toBeTruthy();
      unmount();
    }
  });

  it("skips swings that sit before the first plotted candle", () => {
    const late = { ...plan, chart: { ...plan.chart, candles: candles.slice(10) } };
    render(<RiskLevelsChart plan={late} waveAnalysis={wave()} />);
    expect(screen.queryByTestId("wave-node-0")).toBeNull();
    expect(screen.getByTestId("wave-node-A")).toBeTruthy();
    expect(wavePrices(wave(), 10 * HOUR)).not.toContain(110);
  });

  it("shows the completed count with a solid C node in the chart read panel", () => {
    const complete = wave({
      active_pattern: "abc_complete", status: "confirmed", invalidation_price: 97,
      wave_points: [point("start", 2, 92, "low"), point("0", 8, 110, "high"), point("A", 14, 102, "low"), point("B", 19, 106, "high"), point("C", 25, 97, "low")],
      fib_ratios: { b_retrace_of_a: 0.5, c_projection_of_a: 1.125 },
    });
    const data = { summary: "Basic read.", direction: { label: "up" }, trading_activity: { label: "normal" }, confidence: "medium", timeframe: "1h", window_hours: 50, wave_analysis: complete };
    render(<ChartReadPanel data={data} />);

    const section = screen.getByTestId("chart-read-wave");
    expect(section.textContent).toContain("A-B-C correction · complete");
    expect(section.textContent).toContain("C / A: 1.13");
    expect(section.textContent).toContain("Count breaks: $97");
    expect(section.textContent).toContain("Higher-timeframe trend");
    expect(section.textContent).not.toContain("RSI divergence"); // absent factors are not listed
    expect(screen.getByTestId("wave-node-C").querySelector("text").textContent).toBe("C");
    expect(screen.getByTestId("wave-polyline").getAttribute("points").trim().split(" ")).toHaveLength(5);
    expect(screen.queryByTestId("wave-open-leg")).toBeNull();
    expect(screen.getByText("Basic read.")).toBeTruthy();
  });

  it("omits the wave section when the read is unavailable", () => {
    const data = { summary: "Basic read.", direction: { label: "up" }, trading_activity: { label: "normal" }, confidence: "low", wave_analysis: { available: false, active_pattern: "none", wave_points: [] } };
    render(<ChartReadPanel data={data} />);
    expect(screen.queryByTestId("chart-read-wave")).toBeNull();
    expect(waveIsDrawable(data.wave_analysis)).toBe(false);
    expect(wavePrices(data.wave_analysis)).toEqual([]);
  });
});
