import { describe, expect, it } from "vitest";
import {
  concentrationLabel,
  deriveHoldingRead,
  indexLiveRankings,
} from "./portfolioSignals.js";

const holding = {
  is_cash: false,
  unrealized_pnl_pct: 8.2,
};

describe("Portfolio Mode holding reads", () => {
  it("requires adequate live evidence", () => {
    expect(deriveHoldingRead(holding, null).label).toBe("NOT ENOUGH PROOF");
    expect(
      deriveHoldingRead(holding, { live_score: null, data_quality: null }).label
    ).toBe("NOT ENOUGH PROOF");
    expect(
      deriveHoldingRead(holding, { live_score: 80, data_quality: 20 }).label
    ).toBe("NOT ENOUGH PROOF");
  });

  it("maps strong confirmed evidence to HOLD STRONG", () => {
    const read = deriveHoldingRead(holding, {
      live_score: 82,
      data_quality: 84,
      live_reasons: ["3m +1.20%", "spot buying"],
      live_risks: [],
    });

    expect(read.label).toBe("HOLD STRONG");
    expect(read.score).toBe(82);
    expect(read.explanation).toContain("spot buying");
  });

  it("prioritizes exit watch when selling risk appears", () => {
    expect(
      deriveHoldingRead(holding, {
        live_score: 70,
        data_quality: 80,
        live_reasons: ["3m +0.20%"],
        live_risks: ["spot selling"],
      }).label
    ).toBe("EXIT WATCH");
  });

  it("describes concentration without implying a recommendation", () => {
    expect(concentrationLabel(18)).toBe("Moderately concentrated");
    expect(concentrationLabel(40)).toBe("Highly concentrated");
  });

  it("indexes live rankings by display symbol", () => {
    const index = indexLiveRankings({
      live_rankings: [{ product_id: "SOL-USD", live_score: 75 }],
    });
    expect(index.SOL.live_score).toBe(75);
  });
});
