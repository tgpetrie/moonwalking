import { describe, expect, it } from "vitest";
import { MOVE_STATUS_LABELS, getMoveStatus, getMoveStatusLabel } from "./moveStatus";

describe("getMoveStatus", () => {
  it("confirms aligned gainers and losers with sufficient evidence", () => {
    expect(getMoveStatus({ live_score: 72, data_quality: 83 }, "gainer")).toBe("Confirmed");
    expect(getMoveStatus({ live_score: 28, data_quality: 83 }, "loser")).toBe("Confirmed");
  });

  it("prioritizes thin and extended risk labels", () => {
    expect(getMoveStatus({ live_score: 90, data_quality: 33 }, "gainer")).toBe("Thin");
    expect(getMoveStatus({ live_score: 90, data_quality: 100, live_risks: ["extended move"] }, "gainer")).toBe("Extended");
  });

  it("does not call incomplete evidence confirmed", () => {
    expect(getMoveStatus({ live_score: 58, data_quality: 100 }, "gainer")).toBe("Unconfirmed");
  });
});

describe("getMoveStatusLabel", () => {
  it("narrows the confirmed badge to tape strength only", () => {
    expect(getMoveStatusLabel("Confirmed")).toBe("Tape confirmed");
  });

  it("leaves the other statuses alone", () => {
    expect(getMoveStatusLabel("Unconfirmed")).toBe("Unconfirmed");
    expect(getMoveStatusLabel("Extended")).toBe("Extended");
    expect(getMoveStatusLabel("Thin")).toBe("Thin");
  });

  it("falls back to the raw status when unmapped", () => {
    expect(getMoveStatusLabel("Something New")).toBe("Something New");
  });

  it("keeps status keys usable as CSS class suffixes", () => {
    // TokenRowUnified builds `bh-live-rank--${status.toLowerCase()}`. A key
    // containing whitespace would split into two classes and silently drop the
    // badge styling, which is why the display label is kept separate.
    for (const key of Object.keys(MOVE_STATUS_LABELS)) {
      expect(key).toMatch(/^[A-Za-z]+$/);
    }
  });

  it("has a label for every status getMoveStatus can return", () => {
    const produced = new Set([
      getMoveStatus({ live_score: 72, data_quality: 83 }, "gainer"),
      getMoveStatus({ live_score: 58, data_quality: 100 }, "gainer"),
      getMoveStatus({ live_score: 90, data_quality: 33 }, "gainer"),
      getMoveStatus({ live_score: 90, data_quality: 100, live_risks: ["extended move"] }, "gainer"),
    ]);
    for (const status of produced) {
      expect(MOVE_STATUS_LABELS).toHaveProperty(status);
    }
  });
});
