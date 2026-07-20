import { describe, expect, it } from "vitest";
import { getMoveStatus } from "./moveStatus";

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
