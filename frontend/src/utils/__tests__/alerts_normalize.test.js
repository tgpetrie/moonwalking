import { expect, test } from "vitest";
import {
  parseAlertCore,
  classifyByThreshold,
  normalizeAlert,
  typeKeyToUpper,
  normalizeEventType,
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

// --- normalizeEventType ---

test("normalizeEventType: display strings with spaces → canonical IDs", () => {
  expect(normalizeEventType("COIN FOMO")).toBe("COIN_FOMO");
  expect(normalizeEventType("REVERSAL UP")).toBe("REVERSAL_UP");
  expect(normalizeEventType("BREADTH THRUST")).toBe("BREADTH_THRUST");
  expect(normalizeEventType("PERSIST GAINER")).toBe("PERSIST_GAINER");
});

test("normalizeEventType: display strings with slash → canonical ID", () => {
  expect(normalizeEventType("HACK / EXPLOIT")).toBe("HACK_EXPLOIT");
});

test("normalizeEventType: already-canonical IDs pass through unchanged", () => {
  expect(normalizeEventType("MOONSHOT")).toBe("MOONSHOT");
  expect(normalizeEventType("CRATER")).toBe("CRATER");
  expect(normalizeEventType("COIN_FOMO")).toBe("COIN_FOMO");
  expect(normalizeEventType("REVERSAL_UP")).toBe("REVERSAL_UP");
});

test("normalizeEventType: backend type values (lowercase snake_case) → canonical IDs", () => {
  expect(normalizeEventType("coin_fomo")).toBe("COIN_FOMO");
  expect(normalizeEventType("coin_reversal_up")).toBe("REVERSAL_UP");
  expect(normalizeEventType("whale_move")).toBe("WHALE");
  expect(normalizeEventType("stealth_move")).toBe("STEALTH");
  expect(normalizeEventType("hack_or_exploit")).toBe("HACK_EXPLOIT");
  expect(normalizeEventType("governance_vote")).toBe("GOVERNANCE");
  expect(normalizeEventType("social_spike_1h")).toBe("SOCIAL_SPIKE");
  expect(normalizeEventType("engagement_surge_1h")).toBe("ENGAGEMENT_SURGE");
  expect(normalizeEventType("fomo_alert")).toBe("FOMO");
  expect(normalizeEventType("fear_alert")).toBe("FEAR");
});

test("normalizeEventType: backend enum .name values (SCREAMING_SNAKE_CASE) → canonical IDs", () => {
  expect(normalizeEventType("COIN_REVERSAL_UP")).toBe("REVERSAL_UP");
  expect(normalizeEventType("WHALE_MOVE")).toBe("WHALE");
  expect(normalizeEventType("HACK_OR_EXPLOIT")).toBe("HACK_EXPLOIT");
  expect(normalizeEventType("COIN_BREADTH_THRUST")).toBe("BREADTH_THRUST");
});

test("normalizeEventType: nullish / empty input returns empty string", () => {
  expect(normalizeEventType("")).toBe("");
  expect(normalizeEventType(null)).toBe("");
  expect(normalizeEventType(undefined)).toBe("");
});
