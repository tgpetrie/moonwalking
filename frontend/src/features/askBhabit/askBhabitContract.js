// Ask Bhabit — shared vocabulary and view-model contract.
//
// This file is the single source of truth for the enumerations the feature is
// built around. Keeping them here (rather than as loose strings in components)
// means the adapter, the UI, and the tests all agree on the exact set of states,
// and a backend payload that drifts is caught in one place — the adapter.
//
// None of these values are cosmetic: each maps to a *different meaning* the user
// must be able to distinguish. Missing data must never look neutral, "what
// changed" must never collapse "price moved" into "your thesis broke", and
// confidence must never render as a fake precise score.

/** How much *materially* changed since the prior snapshot. */
export const CHANGE_KIND = Object.freeze({
  PRICE_ONLY: "price_only",
  ONLY_PRICE_CHANGED: "only_price_changed",
  MARKET_STRUCTURE: "market_structure",
  MARKET_STRUCTURE_CHANGED: "market_structure_changed",
  EVIDENCE_QUALITY: "evidence_quality",
  EVIDENCE_QUALITY_CHANGED: "evidence_quality_changed",
  THESIS_EVIDENCE: "thesis_evidence",
  THESIS_EVIDENCE_CHANGED: "thesis_evidence_changed",
  INSUFFICIENT_HISTORY: "insufficient_history",
  INSUFFICIENT_EVIDENCE: "insufficient_evidence",
});

export const CHANGE_KIND_PRESENTATION = Object.freeze({
  [CHANGE_KIND.PRICE_ONLY]: {
    label: "Only price moved",
    tone: "muted",
    blurb: "Price changed, but the underlying signal structure did not.",
  },
  [CHANGE_KIND.ONLY_PRICE_CHANGED]: {
    label: "Only price moved",
    tone: "muted",
    blurb: "Price changed, but the underlying signal structure did not.",
  },
  [CHANGE_KIND.MARKET_STRUCTURE]: {
    label: "Market structure changed",
    tone: "warning",
    blurb: "Positioning, funding, or liquidity structure shifted — not just price.",
  },
  [CHANGE_KIND.MARKET_STRUCTURE_CHANGED]: {
    label: "Market structure changed",
    tone: "warning",
    blurb: "Positioning, funding, or liquidity structure shifted — not just price.",
  },
  [CHANGE_KIND.EVIDENCE_QUALITY]: {
    label: "Evidence quality changed",
    tone: "info",
    blurb: "How much dependable data backs this read has changed.",
  },
  [CHANGE_KIND.EVIDENCE_QUALITY_CHANGED]: {
    label: "Evidence quality changed",
    tone: "info",
    blurb: "How much dependable data backs this read has changed.",
  },
  [CHANGE_KIND.THESIS_EVIDENCE]: {
    label: "Thesis evidence changed",
    tone: "danger",
    blurb: "Evidence tied to why you entered has moved.",
  },
  [CHANGE_KIND.THESIS_EVIDENCE_CHANGED]: {
    label: "Thesis evidence changed",
    tone: "danger",
    blurb: "Evidence tied to why you entered has moved.",
  },
  [CHANGE_KIND.INSUFFICIENT_HISTORY]: {
    label: "Not enough history",
    tone: "muted",
    blurb: "There is no comparable prior snapshot to measure change against.",
  },
  [CHANGE_KIND.INSUFFICIENT_EVIDENCE]: {
    label: "Not enough evidence",
    tone: "muted",
    blurb: "There is not enough evidence to compare safely.",
  },
});

/** Whether the entry thesis is holding up. */
export const THESIS_CHECK = Object.freeze({
  STRENGTHENED: "strengthened",
  UNCHANGED: "unchanged",
  WEAKENED: "weakened",
  CANNOT_DETERMINE: "cannot_determine",
});

export const THESIS_CHECK_PRESENTATION = Object.freeze({
  [THESIS_CHECK.STRENGTHENED]: { label: "Strengthened", tone: "positive" },
  [THESIS_CHECK.UNCHANGED]: { label: "Unchanged", tone: "info" },
  [THESIS_CHECK.WEAKENED]: { label: "Weakened", tone: "danger" },
  [THESIS_CHECK.CANNOT_DETERMINE]: { label: "Cannot determine", tone: "muted" },
});

/** Qualitative confidence — never a fake precise score. */
export const CONFIDENCE = Object.freeze({
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
  INSUFFICIENT: "insufficient",
  INSUFFICIENT_EVIDENCE: "insufficient_evidence",
});

export const CONFIDENCE_PRESENTATION = Object.freeze({
  [CONFIDENCE.HIGH]: { label: "High", tone: "positive" },
  [CONFIDENCE.MEDIUM]: { label: "Medium", tone: "info" },
  [CONFIDENCE.LOW]: { label: "Low", tone: "warning" },
  [CONFIDENCE.INSUFFICIENT]: { label: "Insufficient evidence", tone: "muted" },
  [CONFIDENCE.INSUFFICIENT_EVIDENCE]: { label: "Insufficient evidence", tone: "muted" },
});

/**
 * Why a piece of data is absent. These are deliberately distinct — a provider
 * outage (transient, retry) is a different user story from an unsupported
 * derivative (never coming) or a stale cache (was live, now old). The UI must
 * make each visually non-neutral.
 */
export const MISSING_STATUS = Object.freeze({
  UNAVAILABLE: "unavailable",
  UNSUPPORTED: "unsupported",
  NOT_CONFIGURED: "not_configured",
  STALE: "stale",
  PROVIDER_ERROR: "provider_error",
  CONFLICTING: "conflicting",
});

export const MISSING_STATUS_PRESENTATION = Object.freeze({
  [MISSING_STATUS.UNAVAILABLE]: {
    label: "Unavailable",
    tone: "muted",
    blurb: "No data returned for this metric right now.",
  },
  [MISSING_STATUS.UNSUPPORTED]: {
    label: "Unsupported",
    tone: "muted",
    blurb: "This market is not covered by the provider (e.g. no derivatives listed).",
  },
  [MISSING_STATUS.NOT_CONFIGURED]: {
    label: "Not configured",
    tone: "info",
    blurb: "This source is not connected for your account yet.",
  },
  [MISSING_STATUS.STALE]: {
    label: "Stale",
    tone: "warning",
    blurb: "Last value is older than the freshness threshold — treat with caution.",
  },
  [MISSING_STATUS.PROVIDER_ERROR]: {
    label: "Provider error",
    tone: "danger",
    blurb: "The provider returned an error — this may clear on retry.",
  },
  [MISSING_STATUS.CONFLICTING]: {
    label: "Conflicting",
    tone: "danger",
    blurb: "Sources disagree — no single value can be trusted.",
  },
});

/** Time-horizon options for the optional thesis. */
export const TIME_HORIZON = Object.freeze({
  SHORT: "short",
  SWING: "swing",
  LONG: "long",
});

export const TIME_HORIZON_LABEL = Object.freeze({
  [TIME_HORIZON.SHORT]: "Short-term",
  [TIME_HORIZON.SWING]: "Swing",
  [TIME_HORIZON.LONG]: "Long-term",
});

export const THESIS_TAGS = Object.freeze([
  "Momentum",
  "Ecosystem growth",
  "Product adoption",
  "Airdrop",
  "Yield",
  "Undervalued",
  "Narrative",
  "Speculation",
]);

/** Guided starter questions shown before the free-text box. */
export const GUIDED_QUESTIONS = Object.freeze([
  { id: "how_doing", label: "How is this position doing?" },
  { id: "what_changed", label: "What changed?" },
  { id: "thesis_weakening", label: "Is my thesis weakening?" },
  { id: "missing_risks", label: "What risks am I missing?" },
]);

/** Feedback verdicts on an answer. */
export const FEEDBACK_KIND = Object.freeze({
  HELPFUL: "helpful",
  NOT_HELPFUL: "not_helpful",
  INCORRECT_DATA: "incorrect_data",
  MISSING_CONTEXT: "missing_context",
});

export const FEEDBACK_PRESENTATION = Object.freeze({
  [FEEDBACK_KIND.HELPFUL]: { label: "Helpful", tone: "positive" },
  [FEEDBACK_KIND.NOT_HELPFUL]: { label: "Not helpful", tone: "muted" },
  [FEEDBACK_KIND.INCORRECT_DATA]: { label: "Incorrect data", tone: "danger" },
  [FEEDBACK_KIND.MISSING_CONTEXT]: { label: "Missing context", tone: "warning" },
});

/** Analysis lifecycle / render states the experience can be in. */
export const ANALYSIS_STATE = Object.freeze({
  IDLE: "idle",
  LOADING: "loading",
  READY: "ready",
  PROVIDER_ERROR: "provider_error",
  PROVIDER_NOT_CONFIGURED: "provider_not_configured",
  MODEL_FAILURE: "model_failure",
  MODEL_NOT_CONFIGURED: "model_not_configured",
  NETWORK_FAILURE: "network_failure",
  BACKEND_VALIDATION_FAILURE: "backend_validation_failure",
  TRIAL_EXHAUSTED: "trial_exhausted",
});

// Small helpers so components never hand-roll a lookup-with-fallback.
export const presentChangeKind = (kind) =>
  CHANGE_KIND_PRESENTATION[kind] || CHANGE_KIND_PRESENTATION[CHANGE_KIND.INSUFFICIENT_HISTORY];
export const presentThesisCheck = (state) =>
  THESIS_CHECK_PRESENTATION[state] || THESIS_CHECK_PRESENTATION[THESIS_CHECK.CANNOT_DETERMINE];
export const presentConfidence = (level) =>
  CONFIDENCE_PRESENTATION[level] || CONFIDENCE_PRESENTATION[CONFIDENCE.INSUFFICIENT];
export const presentMissingStatus = (status) =>
  MISSING_STATUS_PRESENTATION[status] || MISSING_STATUS_PRESENTATION[MISSING_STATUS.UNAVAILABLE];
