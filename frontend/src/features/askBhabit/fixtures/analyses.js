// Raw analysis payloads in the shape the backend is expected to return. The
// adapter (askBhabitAdapter.js) is the only thing that reads this shape — the UI
// consumes the normalized view model. Keeping the fixtures in backend shape means
// they double as the contract example Codex can freeze against.
//
// Each fixture is intentionally chosen to exercise a required UI state:
//   RICH_ANALYSIS      — well-supported, high confidence, prior snapshot present.
//   SPARSE_ANALYSIS    — thin coverage: unsupported derivatives, not-configured
//                        social, stale + conflicting data, insufficient evidence.
//   NO_PRIOR_ANALYSIS  — first analysis, no snapshot to diff against.
//   PROVIDER_ERROR / MODEL_FAILURE — failure envelopes.

export const RICH_ANALYSIS = Object.freeze({
  request: { asset: "SOL", question_id: "what_changed", question_text: "What changed?", has_thesis: true },
  generated_at: "2026-07-24T14:05:00Z",
  direct_read: {
    headline: "Structure improved, thesis intact",
    tone: "positive",
    detail:
      "Momentum and derivatives positioning both firmed since your last read. Nothing in the entry thesis has broken.",
  },
  what_changed: {
    kind: "market_structure",
    since: "2026-07-22T14:00:00Z",
    items: [
      { label: "Funding flipped positive", detail: "OKX + Hyperliquid funding turned positive over 48h.", tone: "positive" },
      { label: "Open interest rising", detail: "OI up ~12% without a price blow-off.", tone: "info" },
    ],
  },
  position: {
    quantity: 42,
    entry_price: 118.4,
    cost_basis: 4972.8,
    market_price: 141.2,
    unrealized_pnl: 957.6,
    unrealized_pnl_pct: 19.26,
    allocation_pct: 18.4,
  },
  thesis_check: {
    state: "strengthened",
    reasons: [
      "On-chain activity up week-over-week, matching your ecosystem-growth thesis.",
      "No sign of the failed-upgrade invalidation you flagged.",
    ],
  },
  evidence: [
    { claim: "Spot buying pressure", detail: "Net taker buy volume positive 3 sessions running.", tone: "positive" },
    { claim: "Positive funding", detail: "Perp funding positive but not extreme.", tone: "positive" },
    { claim: "Rising open interest", detail: "OI expanding alongside price.", tone: "info" },
  ],
  missing: [
    { metric: "Social sentiment", status: "not_configured", detail: "Social provider is not connected for your account." },
  ],
  confidence: {
    level: "high",
    reasons: [
      "Multiple independent venues agree (spot + 2 perp venues).",
      "Strong comparable-outcome history for this signal shape.",
    ],
  },
  sources: [
    { provider: "Coinalyze", claim: "Perp funding + OI", retrieved_at: "2026-07-24T14:03:10Z", freshness: "fresh", url: "https://coinalyze.net" },
    { provider: "Hyperliquid", claim: "Funding rate", retrieved_at: "2026-07-24T14:03:12Z", freshness: "fresh", url: "https://app.hyperliquid.xyz" },
    { provider: "Coinbase", claim: "Spot price + taker volume", retrieved_at: "2026-07-24T14:04:00Z", freshness: "fresh", url: null },
  ],
  meta: { mode: "deterministic", model: "fixture" },
});

export const SPARSE_ANALYSIS = Object.freeze({
  request: { asset: "SHDW", question_id: "how_doing", question_text: "How is this position doing?", has_thesis: true },
  generated_at: "2026-07-24T14:06:00Z",
  direct_read: {
    headline: "Not enough independent evidence",
    tone: "muted",
    detail:
      "SHDW has thin coverage. Price is down since entry, but there is not enough dependable data to grade the position responsibly.",
  },
  what_changed: {
    kind: "price_only",
    since: "2026-07-23T14:00:00Z",
    items: [{ label: "Price drifted lower", detail: "Down ~6% with no structural change detected.", tone: "warning" }],
  },
  position: {
    quantity: 5200,
    entry_price: 0.412,
    cost_basis: 2142.4,
    market_price: 0.361,
    unrealized_pnl: -265.2,
    unrealized_pnl_pct: -12.38,
    allocation_pct: 7.9,
  },
  thesis_check: {
    state: "cannot_determine",
    reasons: ["No adoption or activity data available to test the storage-network thesis."],
  },
  evidence: [
    { claim: "Spot price", detail: "Single-venue spot price only.", tone: "muted" },
  ],
  missing: [
    { metric: "Derivatives / funding", status: "unsupported", detail: "No perp market lists SHDW — funding and OI cannot exist." },
    { metric: "Social sentiment", status: "not_configured", detail: "Social provider is not connected for your account." },
    { metric: "On-chain activity", status: "provider_error", detail: "Indexer returned 502 — may clear on retry." },
    { metric: "Order-book depth", status: "stale", detail: "Last snapshot is 41 minutes old." },
    { metric: "Reference price", status: "conflicting", detail: "Two venues disagree by 4.2% — no trustworthy mid." },
  ],
  confidence: {
    level: "insufficient",
    reasons: ["Only one independent source.", "No comparable-outcome history for this signal."],
  },
  sources: [
    { provider: "Coinbase", claim: "Spot price", retrieved_at: "2026-07-24T14:05:40Z", freshness: "fresh", url: null },
    { provider: "On-chain indexer", claim: "Activity (failed)", retrieved_at: "2026-07-24T13:25:00Z", freshness: "error", url: null },
  ],
  meta: { mode: "deterministic", model: "fixture" },
});

// First analysis for a position: no prior snapshot to compare against.
export const NO_PRIOR_ANALYSIS = Object.freeze({
  ...RICH_ANALYSIS,
  request: { asset: "SOL", question_id: "how_doing", question_text: "How is this position doing?", has_thesis: false },
  thesis_check: null,
  what_changed: { kind: "insufficient_history", since: null, items: [] },
});

export const PROVIDER_ERROR_ENVELOPE = Object.freeze({
  error: "provider_error",
  message: "Upstream market data provider is unavailable. This usually clears on retry.",
});

export const MODEL_FAILURE_ENVELOPE = Object.freeze({
  error: "model_failure",
  message: "The analysis engine failed to produce a structured answer. No partial result is shown.",
});

// Keyed lookup for the sample first-value flow (position id -> raw payload).
export const SAMPLE_ANALYSIS_BY_POSITION = Object.freeze({
  "sample-sol": RICH_ANALYSIS,
  "sample-shdw": SPARSE_ANALYSIS,
});
