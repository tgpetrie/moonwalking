import { describe, expect, it } from "vitest";
import { deriveRowCue } from "../rowCue";

const NOW_MS = Date.UTC(2026, 2, 11, 18, 0, 0);

const makeAlert = (type_key, ageMinutes, extra = {}) => ({
  symbol: "APE",
  type_key,
  event_ts_ms: NOW_MS - ageMinutes * 60 * 1000,
  severity: "medium",
  ...extra,
});

describe("deriveRowCue", () => {
  it("keeps the current board reason primary and demotes weaker active alerts to recent context", () => {
    const cue = deriveRowCue({
      token: { symbol: "APE", change_3m: 13.4 },
      changeField: "change_3m",
      activeAlert: makeAlert("fomo", 1),
      nowMs: NOW_MS,
    });

    expect(cue.primary?.key).toBe("moonwalking");
    expect(cue.secondary?.key).toBe("heating");
  });

  it("retains whale-style recent memory inside its longer ttl window", () => {
    const cue = deriveRowCue({
      token: { symbol: "XRP", change_3m: 1.2 },
      changeField: "change_3m",
      recentAlerts: [
        makeAlert("whale", 6),
        makeAlert("fomo", 6),
      ],
      nowMs: NOW_MS,
    });

    expect(cue.primary?.key).toBe("building");
    expect(cue.secondary?.key).toBe("whale");
  });

  it("builds a persistence marker from repeat board presence context", () => {
    const cue = deriveRowCue({
      token: { symbol: "XRP", change_1m: 0.8, trend_streak: 4 },
      changeField: "change_1m",
      nowMs: NOW_MS,
    });

    expect(cue.persistence).toMatchObject({
      count: 4,
      compactCount: "4x",
    });
  });

  it("uses the alert-engine thresholds for board fallback cues", () => {
    const breakout = deriveRowCue({
      token: { symbol: "APE", change_1m: 0.55 },
      changeField: "change_1m",
      nowMs: NOW_MS,
    });
    const moonwalking = deriveRowCue({
      token: { symbol: "APE", change_3m: 2.6 },
      changeField: "change_3m",
      nowMs: NOW_MS,
    });

    expect(breakout.primary).toMatchObject({ key: "breakout", emoji: "↗" });
    expect(moonwalking.primary).toMatchObject({ key: "moonwalking", emoji: "☾" });
  });

  it("uses the whale symbol for aggregate volume events", () => {
    const cue = deriveRowCue({
      token: {
        symbol: "XRP",
        change_1m: 0.1,
        change_3m: 0.2,
        volume_change_1h_pct: 151,
        quote_volume_1h_now: 250001,
        baseline_ready: true,
      },
      changeField: "change_1m",
      nowMs: NOW_MS,
    });

    expect(cue.primary).toMatchObject({ key: "whale", emoji: "🐋" });
  });
});
