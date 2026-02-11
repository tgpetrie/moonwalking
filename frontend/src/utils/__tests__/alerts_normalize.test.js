import { expect, test } from "vitest";
import {
  parseAlertCore,
  classifyByThreshold,
  normalizeAlert,
  typeKeyToUpper,
} from "../alerts_normalize.js";
import { WINDOW_KEYS } from "../windows.js";

test("parseAlertCore extracts pct/window from message", () => {
  const core = parseAlertCore({
    symbol: "TROLL-USD",
    message: "TROLL-USD moved +10.94% in 1m",
  });
  expect(core.window).toBe("1m");
  expect(core.pct).toBe(10.94);
});

test("classifyByThreshold applies 1m moonshot band", () => {
  const out = classifyByThreshold({ window: "1m", pct: 10.94 });
  expect(out.type_key).toBe("moonshot");
  expect(out.severity).toBe("high");
});

test("classifyByThreshold applies 3m downside crater band", () => {
  const out = classifyByThreshold({ window: "3m", pct: -7.0 });
  expect(out.type_key).toBe("crater");
  expect(out.severity).toBe("high");
});

test("normalizeAlert keeps explicit whale/divergence families", () => {
  const whale = normalizeAlert({
    symbol: "BTC-USD",
    type: "whale_move",
    severity: "critical",
    message: "flow spike",
  });
  expect(whale.type_key).toBe("whale");
  expect(typeKeyToUpper(whale.type_key)).toBe("WHALE");
});

test("normalizeAlert falls back to evidence pct fields", () => {
  const out = normalizeAlert({
    symbol: "SOL-USD",
    type: "impulse_3m",
    evidence: { pct_3m: 6.2 },
  });
  expect(out.window).toBe("3m");
  expect(out.pct).toBe(6.2);
  expect(out.type_key).toBe("breakout");
});

test("normalizeAlert drops legacy long-horizon window labels", () => {
  const legacyWindow = "4" + "h";
  const out = normalizeAlert({
    symbol: "BTC-USD",
    type: "impulse",
    window: legacyWindow,
    pct: 2.1,
  });
  expect(out.window).toBe("");
  expect(out.window_key).toBe(WINDOW_KEYS.UNKNOWN);
});
