import { describe, expect, it } from "vitest";
import { buildDeskTape, filterTape, isTrivialNoise, scanIsReady } from "./deskTape.js";

const classify = (log) => ({ label: log.label, chipTone: "gain" });
const log = (over) => ({ ts: 1_000_000, severity: "medium", window: "3m", pct: 3, ...over });

const SCAN = {
  status: "ready",
  coins: [
    { symbol: "ATOM", bucket: "deep_accumulation_exhaustion", monthly_bearish_streak: 23 },
    { symbol: "SOL", bucket: "growth_expansion_ride", rollover_target_box: { low: 180, high: 200 } },
    { symbol: "FET", bucket: "low_confirmation_breakout", above_50w_sma: true },
  ],
  buckets: {},
};

describe("desk tape contradictions", () => {
  it("keeps only the stronger side of a same-coin breakout/breakdown pair", () => {
    const tape = buildDeskTape([
      log({ symbol: "BTC", label: "BREAKOUT", severity: "medium" }),
      log({ symbol: "BTC", label: "BREAKDOWN", severity: "high", ts: 1_030_000 }),
    ], classify);
    expect(tape.map((e) => e.label)).toEqual(["BREAKDOWN"]);
  });

  it("keeps both sides once they are more than 60s apart, and never collapses different coins", () => {
    const tape = buildDeskTape([
      log({ symbol: "BTC", label: "BREAKOUT" }),
      log({ symbol: "BTC", label: "BREAKDOWN", ts: 1_090_000 }),
      log({ symbol: "ETH", label: "BREAKDOWN" }),
    ], classify);
    expect(tape).toHaveLength(3);
  });

  it("matches aliases and lets the newer event break a severity tie", () => {
    const tape = buildDeskTape([
      log({ symbol: "BTC", label: "BREAKOUT", eventTs: 1_000_000 }),
      log({ symbol: "BTC-USDC", label: "BREAKDOWN", eventTs: 1_060_000 }),
    ], classify);
    expect(tape.map((e) => e.label)).toEqual(["BREAKDOWN"]);
  });
});

describe("desk tape noise", () => {
  it("drops sub-1% 1m moves unless volume expands or it is STEALTH", () => {
    expect(isTrivialNoise(log({ window: "1m", pct: 0.5 }), "MOVE")).toBe(true);
    expect(isTrivialNoise(log({ window: "1m", pct: 0.5, vol_change_pct: 80 }), "MOVE")).toBe(false);
    expect(isTrivialNoise(log({ window: "1m", pct: 0.5 }), "STEALTH")).toBe(false);
    expect(isTrivialNoise(log({ window: "3m", pct: 0.5 }), "MOVE")).toBe(false);
  });
});

describe("desk tape cycle context", () => {
  it("badges and calls confluence from the cycle scan and watchlist", () => {
    const tape = buildDeskTape([
      log({ symbol: "ATOM", label: "BREAKOUT" }),
      log({ symbol: "SOL", label: "BREAKDOWN", ref_price: 190 }),
      log({ symbol: "FET", label: "MOVE", direction: "up" }),
      log({ symbol: "DOGE", label: "MOVE", direction: "up" }),
    ], classify, { scan: SCAN, watchSymbols: ["DOGE-USD"] });
    const by = Object.fromEntries(tape.map((e) => [e.log.symbol, e]));
    expect(by.ATOM.badges.map((b) => b.label)).toContain("DEEP ACCUM · 23m");
    expect(by.ATOM.call.label).toBe("EXHAUSTION BREAKOUT");
    expect(by.SOL.badges.map((b) => b.label)).toContain("ROLLOVER BOX");
    expect(by.SOL.call.label).toBe("ROLLOVER DISTRIBUTION");
    expect(by.FET.badges.map((b) => b.label)).toEqual(["PIVOT BREAK", "ABOVE 50W"]);
    expect(by.DOGE.badges.map((b) => b.label)).toEqual(["WATCHLIST"]);
  });

  it("bounds stage badges and limits rollover distribution to the box", () => {
    const scan = {
      status: "ready", industry: { available: true, stage_number: 9 },
      coins: [{ symbol: "SOL", bucket: "rollover_profit_zone", price: 190, rollover_target_box: { low: 180, high: 200 } }],
    };
    const [inside, above] = buildDeskTape([
      log({ symbol: "SOL", label: "BREAKDOWN", ref_price: null }),
      log({ symbol: "SOL", label: "BREAKDOWN", ref_price: 205 }),
    ], classify, { scan, heldSymbols: ["SOL"] });
    expect(inside.call?.label).toBe("ROLLOVER DISTRIBUTION");
    expect(above.call).toBeNull();
    expect(above.badges.map((b) => b.label)).toEqual(["HELD"]);
    expect(scanIsReady({ ...scan, status: "refreshing" })).toBe(false);
  });

  it("filters desk to confluence, watchlist to members and raw to everything", () => {
    const tape = buildDeskTape([
      log({ symbol: "ATOM", label: "BREAKOUT" }),
      log({ symbol: "XRP", label: "BREAKOUT" }),
      log({ symbol: "DOGE", label: "MOVE", direction: "up" }),
    ], classify, { scan: SCAN, watchSymbols: ["DOGE"] });
    const ready = scanIsReady(SCAN);
    expect(ready).toBe(true);
    expect(filterTape(tape, "desk", { scanReady: ready }).rows.map((e) => e.log.symbol)).toEqual(["ATOM", "DOGE"]);
    expect(filterTape(tape, "watchlist").rows.map((e) => e.log.symbol)).toEqual(["DOGE"]);
    expect(filterTape(tape, "raw").rows).toHaveLength(3);
  });

  it("falls back to top anomalies while the scan is warming", () => {
    const tape = buildDeskTape([log({ symbol: "XRP", label: "BREAKOUT" })], classify, {
      scan: { status: "warming", coins: [] },
    });
    const result = filterTape(tape, "desk", { scanReady: scanIsReady({ status: "warming" }) });
    expect(result.fallback).toBe(true);
    expect(result.rows).toHaveLength(1);
  });
});
