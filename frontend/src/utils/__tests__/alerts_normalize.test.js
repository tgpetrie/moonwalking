import assert from "node:assert";
import test from "node:test";
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
  assert.strictEqual(core.window, "1m");
  assert.strictEqual(core.pct, 10.94);
});

test("classifyByThreshold applies 1m moonshot band", () => {
  const out = classifyByThreshold({ window: "1m", pct: 10.94 });
  assert.strictEqual(out.type_key, "moonshot");
  assert.strictEqual(out.severity, "high");
});

test("classifyByThreshold applies 3m downside crater band", () => {
  const out = classifyByThreshold({ window: "3m", pct: -7.0 });
  assert.strictEqual(out.type_key, "crater");
  assert.strictEqual(out.severity, "high");
});

test("normalizeAlert keeps explicit whale/divergence families", () => {
  const whale = normalizeAlert({
    symbol: "BTC-USD",
    type: "whale_move",
    severity: "critical",
    message: "flow spike",
  });
  assert.strictEqual(whale.type_key, "whale");
  assert.strictEqual(typeKeyToUpper(whale.type_key), "WHALE");
});

test("normalizeAlert falls back to evidence pct fields", () => {
  const out = normalizeAlert({
    symbol: "SOL-USD",
    type: "impulse_3m",
    evidence: { pct_3m: 6.2 },
  });
  assert.strictEqual(out.window, "3m");
  assert.strictEqual(out.pct, 6.2);
  assert.strictEqual(out.type_key, "breakout");
});

test("normalizeAlert drops legacy long-horizon window labels", () => {
  const legacyWindow = "4" + "h";
  const out = normalizeAlert({
    symbol: "BTC-USD",
    type: "impulse",
    window: legacyWindow,
    pct: 2.1,
  });
  assert.strictEqual(out.window, "");
  assert.strictEqual(out.window_key, WINDOW_KEYS.UNKNOWN);
});
