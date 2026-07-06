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
      token: { symbol: "XRP", change_3m: 2.8 },
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
});
