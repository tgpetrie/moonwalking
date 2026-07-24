// Sample positions used for the first-value experience. The first screen must
// never be an empty chat box — these two positions demonstrate the two ends of
// the data spectrum the product has to be honest about:
//
//   • SOL  — a well-supported case: derivatives, funding, deep history.
//   • SHDW — a sparse-data case: thin coverage, unsupported derivatives, so the
//            answer leans on "missing / uncertain" rather than fake confidence.
//
// These are frozen fixtures, not live data. The adapter treats them the same
// way it treats a real payload, so the sample path exercises the same code.

export const SAMPLE_POSITIONS = Object.freeze([
  {
    id: "sample-sol",
    isSample: true,
    coverage: "rich",
    asset: "SOL",
    name: "Solana",
    quantity: 42,
    entryPrice: 118.4,
    costBasis: 4972.8,
    acquiredAt: "2025-11-02",
    note: "Scaling into ecosystem strength.",
    thesis: {
      reason: "Ecosystem activity and app revenue trending up.",
      invalidation: "Sustained drop in on-chain activity or a failed network upgrade.",
      horizon: "swing",
      tags: ["Ecosystem growth", "Momentum"],
    },
  },
  {
    id: "sample-shdw",
    isSample: true,
    coverage: "sparse",
    asset: "SHDW",
    name: "Shadow Token",
    quantity: 5200,
    entryPrice: 0.412,
    costBasis: 2142.4,
    acquiredAt: "2025-12-18",
    note: "Small speculative position.",
    thesis: {
      reason: "Storage-network adoption narrative.",
      invalidation: "Adoption stalls or team goes quiet.",
      horizon: "long",
      tags: ["Narrative", "Speculation"],
    },
  },
]);

export const getSamplePosition = (id) =>
  SAMPLE_POSITIONS.find((position) => position.id === id) || null;
