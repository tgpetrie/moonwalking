// Adapter: raw analysis payload (backend or fixture) -> view model the UI trusts.
//
// The UI never reads a raw payload directly. This is where we:
//   • detect failure envelopes and classify them,
//   • coerce every enum through the contract's presenters (so an unknown value
//     degrades to a safe, non-neutral default instead of rendering blank),
//   • pre-format position numbers once,
//   • guarantee arrays are arrays.
//
// Missing data is the sharp edge of this product, so the adapter never invents a
// value and never lets a missing metric fall through as "neutral".

import {
  ANALYSIS_STATE,
  presentChangeKind,
  presentConfidence,
  presentMissingStatus,
  presentThesisCheck,
} from "./askBhabitContract.js";

const num = (value) => {
  // Guard the values Number() silently coerces to 0 (null / "" / booleans) so a
  // missing figure formats as "—" instead of a misleading zero.
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const arr = (value) => (Array.isArray(value) ? value : []);

export const fmtPrice = (value) => {
  const n = num(value);
  if (n === null) return "—";
  const digits = Math.abs(n) >= 100 ? 2 : Math.abs(n) >= 1 ? 3 : 4;
  return `$${n.toFixed(digits)}`;
};

export const fmtUsd = (value) => {
  const n = num(value);
  if (n === null) return "—";
  return `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
};

export const fmtPct = (value) => {
  const n = num(value);
  if (n === null) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};

/** Relative "3m ago" style label from an ISO timestamp, for source freshness. */
export const relativeTime = (iso, now = Date.now()) => {
  if (!iso) return "unknown time";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "unknown time";
  const diffMs = now - then;
  if (diffMs < 0) return "just now";
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
};

const buildPosition = (raw) => {
  const pnlPct = num(raw?.unrealized_pnl_pct);
  return {
    quantity: num(raw?.quantity),
    entryPrice: num(raw?.entry_price),
    costBasis: num(raw?.cost_basis),
    marketPrice: num(raw?.market_price),
    unrealizedPnl: num(raw?.unrealized_pnl),
    unrealizedPnlPct: pnlPct,
    allocationPct: num(raw?.allocation_pct),
    pnlTone: pnlPct === null ? "muted" : pnlPct >= 0 ? "positive" : "danger",
    display: {
      entryPrice: fmtPrice(raw?.entry_price),
      marketPrice: fmtPrice(raw?.market_price),
      costBasis: fmtUsd(raw?.cost_basis),
      unrealizedPnl: fmtUsd(raw?.unrealized_pnl),
      unrealizedPnlPct: fmtPct(raw?.unrealized_pnl_pct),
      allocationPct: raw?.allocation_pct == null ? "—" : `${num(raw.allocation_pct)?.toFixed(1)}%`,
    },
  };
};

/**
 * Classify a raw payload. Returns { state, ... } where state comes from
 * ANALYSIS_STATE. Callers switch on `.state` and only read `.view` when READY.
 */
export function buildAnalysisView(raw, { now = Date.now() } = {}) {
  if (!raw || typeof raw !== "object") {
    return { state: ANALYSIS_STATE.MODEL_FAILURE, message: "No analysis was returned." };
  }

  if (raw.error === "provider_error") {
    return { state: ANALYSIS_STATE.PROVIDER_ERROR, message: raw.message || "Market data provider unavailable." };
  }
  if (raw.error === "model_failure") {
    return { state: ANALYSIS_STATE.MODEL_FAILURE, message: raw.message || "The analysis engine failed." };
  }
  if (raw.error) {
    // Unknown error kind — never render it as a normal answer.
    return { state: ANALYSIS_STATE.MODEL_FAILURE, message: raw.message || String(raw.error) };
  }

  const change = raw.what_changed || {};
  const changePresentation = presentChangeKind(change.kind);
  const hasPrior = Boolean(change.since) && change.kind !== "insufficient_history";

  const thesisRaw = raw.thesis_check;
  const thesis = thesisRaw
    ? { ...presentThesisCheck(thesisRaw.state), state: thesisRaw.state, reasons: arr(thesisRaw.reasons) }
    : null;

  const confidenceRaw = raw.confidence || {};
  const confidence = {
    ...presentConfidence(confidenceRaw.level),
    level: confidenceRaw.level,
    reasons: arr(confidenceRaw.reasons),
  };

  const view = {
    request: raw.request || {},
    generatedAt: raw.generated_at || null,
    directRead: {
      headline: raw.direct_read?.headline || "No direct read available",
      tone: raw.direct_read?.tone || "muted",
      detail: raw.direct_read?.detail || "",
    },
    whatChanged: {
      ...changePresentation,
      kind: change.kind || "insufficient_history",
      since: change.since || null,
      sinceLabel: change.since ? relativeTime(change.since, now) : null,
      hasPrior,
      items: arr(change.items).map((item) => ({
        label: item?.label || "",
        detail: item?.detail || "",
        tone: item?.tone || "muted",
      })),
    },
    position: buildPosition(raw.position || {}),
    thesisCheck: thesis,
    evidence: arr(raw.evidence).map((item) => ({
      claim: item?.claim || "",
      detail: item?.detail || "",
      tone: item?.tone || "muted",
    })),
    missing: arr(raw.missing).map((item) => ({
      metric: item?.metric || "Unknown metric",
      status: item?.status,
      detail: item?.detail || "",
      ...presentMissingStatus(item?.status),
    })),
    confidence,
    sources: arr(raw.sources).map((item) => ({
      provider: item?.provider || "Unknown source",
      claim: item?.claim || "",
      retrievedAt: item?.retrieved_at || null,
      retrievedLabel: relativeTime(item?.retrieved_at, now),
      freshness: item?.freshness || "unknown",
      url: item?.url || null,
    })),
    meta: raw.meta || {},
  };

  return { state: ANALYSIS_STATE.READY, view };
}

/**
 * Validate a manual position draft. Required: asset, quantity, and one of
 * entryPrice or costBasis. Returns { valid, errors, normalized }.
 */
export function validatePositionDraft(draft = {}) {
  const errors = {};
  const asset = String(draft.asset || "").trim().toUpperCase();
  if (!asset) errors.asset = "Asset is required.";
  else if (!/^[A-Z0-9]{2,10}$/.test(asset)) errors.asset = "Use a ticker like SOL or BTC.";

  const quantity = num(draft.quantity);
  if (draft.quantity === "" || draft.quantity == null) errors.quantity = "Quantity is required.";
  else if (quantity === null || quantity <= 0) errors.quantity = "Quantity must be a positive number.";

  const entryPrice = num(draft.entryPrice);
  const costBasis = num(draft.costBasis);
  const hasEntry = entryPrice !== null && entryPrice > 0;
  const hasCost = costBasis !== null && costBasis > 0;
  if (!hasEntry && !hasCost) {
    errors.basis = "Enter an entry price or a total cost basis.";
  }

  const valid = Object.keys(errors).length === 0;

  // Derive whichever basis figure is missing so downstream always has both.
  let derivedEntry = hasEntry ? entryPrice : null;
  let derivedCost = hasCost ? costBasis : null;
  if (valid && quantity) {
    if (derivedEntry === null && derivedCost !== null) derivedEntry = derivedCost / quantity;
    if (derivedCost === null && derivedEntry !== null) derivedCost = derivedEntry * quantity;
  }

  return {
    valid,
    errors,
    normalized: valid
      ? {
          asset,
          quantity,
          entryPrice: derivedEntry,
          costBasis: derivedCost,
          acquiredAt: draft.acquiredAt ? String(draft.acquiredAt) : null,
          note: draft.note ? String(draft.note).trim() : "",
        }
      : null,
  };
}
