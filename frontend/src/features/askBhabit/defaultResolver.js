// Default analysis resolver — fixture-backed until Codex freezes the backend
// contract. Swap this single function for a real fetch to /api/ask-bhabit/analyze
// and nothing in the UI changes: the adapter already normalizes the same shape.
//
// Signature: resolveAnalysis({ position, question, isSample }) -> Promise<rawPayload>
import {
  RICH_ANALYSIS,
  SPARSE_ANALYSIS,
  NO_PRIOR_ANALYSIS,
  SAMPLE_ANALYSIS_BY_POSITION,
} from "./fixtures/analyses.js";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function defaultResolveAnalysis({ position, question, isSample }, { delayMs = 450 } = {}) {
  if (delayMs) await wait(delayMs);

  if (isSample && position?.id && SAMPLE_ANALYSIS_BY_POSITION[position.id]) {
    return SAMPLE_ANALYSIS_BY_POSITION[position.id];
  }

  // Manual position: first-ask has no prior snapshot; asking "what changed"
  // returns the market-structure fixture; sparse assets get the sparse fixture.
  const asset = String(position?.asset || "").toUpperCase();
  if (asset === "SHDW") return SPARSE_ANALYSIS;
  if (question?.id === "what_changed") return RICH_ANALYSIS;
  return NO_PRIOR_ANALYSIS;
}
