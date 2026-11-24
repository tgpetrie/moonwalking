import { describe, expect, it } from "vitest";
import {
  concentrationLabel,
  deriveHoldingRead,
  describeEvidenceTier,
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

describe("Evidence tiers (graded 'proof' gate)", () => {
  it("returns a no-history tier for zero, null, or missing samples", () => {
    for (const n of [0, null, undefined, -3]) {
      const tier = describeEvidenceTier(n);
      expect(tier.key).toBe("none");
      expect(tier.quoteRate).toBe(false);
      expect(tier.label).toBe("No history yet");
    }
  });

  it("does not quote a rate for a thin sample", () => {
    const tier = describeEvidenceTier(4);
    expect(tier.key).toBe("emerging");
    expect(tier.quoteRate).toBe(false);
    expect(tier.label).toBe("Emerging · 4");
  });

  it("grades the sample size across band boundaries", () => {
    expect(describeEvidenceTier(9).key).toBe("emerging");
    expect(describeEvidenceTier(10).key).toBe("building");
    expect(describeEvidenceTier(29).key).toBe("building");
    expect(describeEvidenceTier(30).key).toBe("solid");
    expect(describeEvidenceTier(99).key).toBe("solid");
    expect(describeEvidenceTier(100).key).toBe("strong");
  });

  it("allows quoting a rate only from the building tier up", () => {
    expect(describeEvidenceTier(10).quoteRate).toBe(true);
    expect(describeEvidenceTier(250).quoteRate).toBe(true);
  });

  it("caps the displayed count at 100+", () => {
    expect(describeEvidenceTier(4200).label).toBe("Deep · 100+");
  });

  it("grades sample depth without borrowing live-strength vocabulary", () => {
    // These tiers co-render beside live reads (HOLD STRONG on the Portfolio
    // card) and event states (Building on the Scorecard card). Sharing a word
    // with either makes the tier read as a claim about the move.
    const forbidden = ["Strong", "Building", "Dominant", "Confirmed", "Leading"];
    for (const n of [0, 1, 9, 10, 29, 30, 99, 100, 4200]) {
      const { label } = describeEvidenceTier(n);
      for (const word of forbidden) {
        expect(label).not.toContain(word);
      }
    }
  });

  it("keeps machine keys and rate gating stable while the copy changes", () => {
    expect(describeEvidenceTier(100).key).toBe("strong");
    expect(describeEvidenceTier(10).key).toBe("building");
    expect(describeEvidenceTier(100).quoteRate).toBe(true);
    expect(describeEvidenceTier(9).quoteRate).toBe(false);
  });
});
