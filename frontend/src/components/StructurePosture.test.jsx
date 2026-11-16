import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TokenRowUnified } from "./TokenRowUnified.jsx";
import {
  clearStructurePostureCache, normalizeSymbols, postureFor, useStructurePosture,
} from "../hooks/useStructurePosture.js";

const token = {
  symbol: "SOL", price: 150, current_price: 150, change_3m: 1.8,
  live_score: 72, live_rank: 1, universe_size: 120, data_quality: 83,
  observed_inputs: 5, expected_inputs: 6, live_label: "Strong", live_reasons: [], live_risks: [],
};

const bounce = {
  key: "bounce_in_uptrend", tone: "constructive", label: "Bounce in 1h uptrend", short_label: "1h bounce",
  timeframe: "1h", detail: "On the 1-hour chart a pullback inside a larger advance looks finished. Context only.",
};
const extended = {
  key: "extended_run", tone: "risk", label: "Extended run · pullback risk", short_label: "Extended run",
  timeframe: "1h", detail: "A five-step run up looks finished on the 1h chart. Context only.",
};

describe("structure posture badge on a gainer row", () => {
  it("shows a constructive posture in plain words with the detail on hover", () => {
    render(<TokenRowUnified token={token} side="gainer" rank={1} changeField="change_3m" structurePosture={bounce} />);
    const badge = screen.getByTestId("structure-posture");
    expect(badge.querySelector(".bh-structure__full").textContent).toBe("Bounce in 1h uptrend");
    expect(badge.querySelector(".bh-structure__short").textContent).toBe("1h bounce"); // shown on narrower boards
    expect([...badge.classList]).toEqual(["bh-structure", "bh-structure--constructive"]);
    expect(badge.getAttribute("title")).toContain("Context only.");
    expect(badge.getAttribute("aria-label")).toBe("Chart structure: Bounce in 1h uptrend");
  });

  it("flags a finished run as a risk", () => {
    render(<TokenRowUnified token={token} side="gainer" rank={1} changeField="change_3m" structurePosture={extended} />);
    const badge = screen.getByTestId("structure-posture");
    expect(badge.textContent).toContain("Extended run · pullback risk");
    expect([...badge.classList]).toEqual(["bh-structure", "bh-structure--risk"]);
    expect(badge.getAttribute("data-posture")).toBe("extended_run");
  });

  it("changes nothing else about the row", () => {
    const { container: plain } = render(<TokenRowUnified token={token} side="gainer" rank={1} changeField="change_3m" />);
    expect(plain.querySelector(".bh-structure")).toBeNull();
    const { container: flagged } = render(<TokenRowUnified token={token} side="gainer" rank={1} changeField="change_3m" structurePosture={extended} />);
    // Same tape badge, same price and change: the posture is added context, not a gate.
    for (const selector of [".bh-live-rank", ".bh-price-current", ".bh-change"]) {
      expect(flagged.querySelector(selector).textContent).toBe(plain.querySelector(selector).textContent);
    }
    expect(flagged.querySelector(".bh-row").getAttribute("data-cue")).toBe(plain.querySelector(".bh-row").getAttribute("data-cue"));
  });
});

function Probe({ symbols }) {
  const postures = useStructurePosture(symbols);
  return <output data-testid="probe">{JSON.stringify(postures)}</output>;
}

const json = (body) => ({ ok: true, headers: { get: () => "application/json" }, json: async () => body });

describe("useStructurePosture", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearStructurePostureCache();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("normalizes board symbols", () => {
    expect(normalizeSymbols(["sol", "BTC-USD", "sol", "", null, "bad!sym"])).toEqual(["BTC", "SOL"]);
    expect(postureFor({ SOL: bounce }, { symbol: "sol" })).toBe(bounce);
    expect(postureFor({ SOL: bounce }, { product_id: "SOL-USD" })).toBe(bounce);
    expect(postureFor({ SOL: bounce }, { symbol: "ETH" })).toBeNull();
  });

  it("asks once for the symbols on the board and returns their postures", async () => {
    const fetchMock = vi.fn(async () => json({ postures: { SOL: { posture: bounce }, BTC: { posture: null } }, pending: [] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<Probe symbols={["SOL", "BTC"]} />);
    expect(screen.getByTestId("probe").textContent).toBe("{}");
    await act(async () => { await vi.advanceTimersByTimeAsync(1300); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/structure-posture?symbols=BTC%2CSOL");
    expect(JSON.parse(screen.getByTestId("probe").textContent)).toEqual({ SOL: bounce });
  });

  it("polls again sooner while the server is still reading symbols", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ postures: { SOL: { posture: bounce } }, pending: ["ETH"] }))
      .mockResolvedValue(json({ postures: { SOL: { posture: bounce }, ETH: { posture: extended } }, pending: [] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<Probe symbols={["SOL", "ETH"]} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1300); });
    expect(Object.keys(JSON.parse(screen.getByTestId("probe").textContent))).toEqual(["SOL"]);
    await act(async () => { await vi.advanceTimersByTimeAsync(6100); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(Object.keys(JSON.parse(screen.getByTestId("probe").textContent)).sort()).toEqual(["ETH", "SOL"]);
  });

  it("shows no badge when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    render(<Probe symbols={["SOL"]} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1300); });
    expect(screen.getByTestId("probe").textContent).toBe("{}");
  });
});
