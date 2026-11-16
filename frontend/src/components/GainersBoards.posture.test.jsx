import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../hooks/useDataFeed", () => ({
  useDataFeed: () => ({ data: {}, isLoading: false, getActiveAlert: () => null, getRecentAlerts: () => [] }),
}));
vi.mock("../hooks/useHybridLive", () => ({ useHybridLive: () => ({ data: {} }) }));

import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import { clearStructurePostureCache } from "../hooks/useStructurePosture.js";

const row = (symbol, pct) => ({
  symbol, price: 10, current_price: 10, change_1m: pct, change_3m: pct, previous_price_1m: 9.9, previous_price_3m: 9.9,
});
const tokens = [row("SOL", 2.4), row("ARB", 1.9), row("LINK", 1.2)];

const posture = (key, tone, label, short_label) => ({ posture: { key, tone, label, short_label, detail: "Context only." } });
const body = {
  postures: {
    SOL: posture("bounce_in_uptrend", "constructive", "Bounce in 1h uptrend", "1h bounce"),
    ARB: { posture: null },
    LINK: posture("extended_run", "risk", "Extended run · pullback risk", "Extended run"),
  },
  pending: [],
};

const symbolsShown = (container) => [...container.querySelectorAll(".bh-symbol")].map((node) => node.textContent);

describe("structure posture on the gainers boards", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearStructurePostureCache();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, headers: { get: () => "application/json" }, json: async () => body })));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("adds badges to the 3m gainers without hiding or reordering a row", async () => {
    const { container } = render(<GainersTable3Min tokens={tokens} loading={false} />);
    const before = symbolsShown(container);
    expect(before).toEqual(["SOL", "ARB", "LINK"]);
    expect(screen.queryByTestId("structure-posture")).toBeNull();

    await act(async () => { await vi.advanceTimersByTimeAsync(1300); });

    expect(symbolsShown(container)).toEqual(before); // the risk flag does not drop LINK
    const badges = screen.getAllByTestId("structure-posture");
    expect(badges.map((b) => b.getAttribute("data-posture"))).toEqual(["bounce_in_uptrend", "extended_run"]);
    expect(badges[1].closest(".bh-row").querySelector(".bh-symbol").textContent).toBe("LINK");
  });

  it("survives the 1m board going from loading to rows", async () => {
    // The posture hook must run before the board's early returns; if it does
    // not, React throws when the first rows arrive and the board goes blank.
    const { container, rerender } = render(<GainersTable1Min tokens={[]} loading />);
    expect(container.querySelector(".bh-row")).toBeNull();
    rerender(<GainersTable1Min tokens={tokens} loading={false} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(symbolsShown(container)).toEqual(["SOL", "ARB", "LINK"]);
    expect(screen.getAllByTestId("structure-posture")).toHaveLength(2);
    rerender(<GainersTable1Min tokens={[]} loading={false} />);
    expect(screen.getByText("No 1-minute movers to show right now.")).toBeTruthy();
  });
});
