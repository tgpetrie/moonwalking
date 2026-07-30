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
const text = (value, fallback = "") =>
  value === null || value === undefined || value === "" ? fallback : String(value);

const hasStatus = (item) => item && typeof item === "object" && typeof item.status === "string";
const SHDW_MINT = "SHDWyBxihqiC1b7C5hGaqRpzUT6XQv8x9xqvnYgKPump"; // pragma: allowlist secret

function collectEvidenceStates(value, path = [], out = []) {
  if (hasStatus(value)) {
    out.push({ path, state: value });
  }
  if (Array.isArray(value)) {
    value.forEach((child, index) => collectEvidenceStates(child, [...path, String(index)], out));
  } else if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, child]) => collectEvidenceStates(child, [...path, key], out));
  }
  return out;
}

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
  if (diffMs < 0) return "timestamp in future";
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  const remHours = hrs % 24;
  return remHours ? `${days}d ${remHours}h ago` : `${days}d ago`;
};

const referenceTime = (generatedAt, fallbackNow) => {
  const parsed = Date.parse(generatedAt || "");
  return Number.isNaN(parsed) ? fallbackNow : parsed;
};

const shortenIdentifier = (value) => {
  const raw = text(value);
  if (raw.length <= 16) return raw;
  return `${raw.slice(0, 6)}…${raw.slice(-4)}`;
};

const normalizeAssetIdentity = (raw, fallbackAsset) => {
  const identity = raw || {};
  const symbol = text(identity.symbol || fallbackAsset).toUpperCase();
  const contract =
    identity.contract_address ||
    identity.contractAddress ||
    identity.contract ||
    (symbol === "SHDW" ? SHDW_MINT : null);
  const chain = identity.chain || (symbol === "SHDW" ? "Solana" : null);
  const ambiguous = Boolean(identity.ambiguous || contract || chain);
  if (!ambiguous) return null;
  return {
    symbol,
    name: identity.name || (symbol === "SHDW" ? "Shadow Token" : symbol),
    chain,
    contractAddress: contract || null,
    shortIdentifier: contract ? shortenIdentifier(contract) : null,
    fullIdentifier: contract || null,
  };
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

const changeKindFromCategories = (categories = []) => {
  if (categories.includes("market_structure_changed")) return "market_structure_changed";
  if (categories.includes("thesis_evidence_changed")) return "thesis_evidence_changed";
  if (categories.includes("evidence_quality_changed")) return "evidence_quality_changed";
  if (categories.includes("only_price_changed")) return "only_price_changed";
  return categories[0] || "insufficient_evidence";
};

const metricLabel = (path) =>
  path
    .filter((part) => !/^\d+$/.test(part))
    .slice(-3)
    .join(" / ")
    .replaceAll("_", " ") || "Unknown metric";

const stateDetail = (state) => {
  const parts = [
    state?.missing_data_reason,
    state?.provider_error,
    arr(state?.conflicts).join("; "),
  ].filter(Boolean);
  return parts.join(" · ");
};

const stateSource = (state, path) => ({
  provider: state?.provider || state?.source || metricLabel(path),
  claim: metricLabel(path),
  retrieved_at: state?.retrieved_at || null,
  freshness: state?.freshness || state?.status || "unknown",
  url: state?.url || null,
});

const savedThesisReasons = (thesisValue) => {
  if (!thesisValue || typeof thesisValue !== "object") return [];
  return [
    thesisValue.why_entered ? `Saved thesis: ${thesisValue.why_entered}` : null,
    thesisValue.reconsider_if ? `Reconsider if: ${thesisValue.reconsider_if}` : null,
    thesisValue.time_horizon ? `Time horizon: ${thesisValue.time_horizon}` : null,
  ].filter(Boolean);
};

export function normalizeBackendSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object" || !snapshot.evidence_packet) return snapshot;

  const packet = snapshot.evidence_packet || {};
  const publicEvidence = packet.public_market_evidence || {};
  const privateContext = packet.private_context || {};
  const positionValue = privateContext.position?.value || {};
  const comparison = snapshot.comparison || {};
  const analysis = snapshot.analysis || {};
  const sections = analysis.sections || {};
  const states = collectEvidenceStates(packet);
  const missing = states
    .filter(({ state }) => state.status !== "available")
    .map(({ path, state }) => ({
      metric: metricLabel(path),
      status: state.status,
      detail: stateDetail(state),
      source: state.source || null,
      provider: state.provider || state.source || null,
      retrieved_at: state.retrieved_at || null,
      freshness: state.freshness || state.status,
      conflicts: arr(state.conflicts),
      provider_error: state.provider_error || null,
      missing_data_reason: state.missing_data_reason || null,
    }));

  const directText = sections.direct_assessment || "Ask Bhabit could not generate a model narrative yet.";
  const modelNotConfigured = analysis.status === "not_configured";
  const categories = arr(comparison.categories);
  const thesisSupport = comparison.thesis_support || {};
  const asset = packet.asset_symbol || privateContext.position?.asset_symbol || "";
  const backendIdentity = publicEvidence.asset_identity?.value || {};
  const thesisAvailable = privateContext.thesis?.status === "available";
  const thesisValue = privateContext.thesis?.value || {};
  const positionAvailable = privateContext.position?.status === "available";
  const savedThesis = savedThesisReasons(thesisValue);
  const thesisReasons = thesisAvailable
    ? [...savedThesis, ...arr(thesisSupport.reasons).filter((reason) => !/no thesis supplied/i.test(reason))]
    : [];

  return {
    request: { asset, has_thesis: thesisAvailable },
    asset_identity: normalizeAssetIdentity(backendIdentity, asset),
    generated_at: analysis.created_at || snapshot.created_at || packet.retrieved_at || null,
    direct_read: {
      headline: modelNotConfigured ? "Model analysis is not configured" : "Ask Bhabit assessment",
      tone: modelNotConfigured ? "warning" : "info",
      detail: directText,
    },
    what_changed: {
      kind: comparison.status === "no_previous_snapshot" ? "insufficient_history" : changeKindFromCategories(categories),
      since: null,
      items: arr(comparison.changes).map((change) => ({
        label: text(change.field, "Evidence field changed").replaceAll("_", " "),
        detail:
          change.type === "numeric_change"
            ? `${change.from} → ${change.to}`
            : `${change.from || "unknown"} → ${change.to || "unknown"}`,
        tone: change.type === "status_change" ? "info" : "warning",
      })),
    },
    position: {
      quantity: positionValue.quantity,
      entry_price: positionValue.entry_price,
      cost_basis: positionValue.total_cost_basis,
      market_price: publicEvidence.price?.value ?? null,
      unrealized_pnl: positionValue.unrealized_pnl,
      unrealized_pnl_pct: positionValue.unrealized_pnl_pct,
      allocation_pct: null,
    },
    thesis_check:
      thesisAvailable
        ? {
            state:
              thesisSupport.direction === "strengthening"
                ? "strengthened"
                : thesisSupport.direction === "weakening"
                  ? "weakened"
                  : thesisSupport.direction === "unchanged"
                    ? "unchanged"
                    : "cannot_determine",
            reasons: thesisReasons,
          }
        : null,
    evidence: [
      publicEvidence.asset_identity?.status === "available"
        ? {
            claim: "Asset identity",
            detail: `${asset} resolved as ${publicEvidence.asset_identity?.value?.name || "known asset"}`,
            tone: "info",
          }
        : null,
      publicEvidence.price?.status === "available"
        ? { claim: "Current price", detail: fmtPrice(publicEvidence.price.value), tone: "info" }
        : null,
      positionAvailable
        ? {
            claim: "Position context",
            detail: `Quantity ${text(positionValue.quantity, "—")} at ${fmtPrice(positionValue.entry_price)}`,
            tone: "info",
          }
        : null,
      thesisAvailable
        ? {
            claim: "Saved thesis",
            detail: thesisValue.why_entered || "Saved thesis context is available.",
            tone: "info",
          }
        : null,
    ].filter(Boolean),
    missing,
    confidence: packet.confidence || { level: "insufficient_evidence", reasons: [] },
    sources: states.filter(({ state }) => state.source || state.provider).map(({ state, path }) => stateSource(state, path)),
    meta: { mode: "live_backend", provenance: "live", backend_status: analysis.status || "unknown", snapshot_id: snapshot.snapshot_id },
  };
}

/**
 * Classify a raw payload. Returns { state, ... } where state comes from
 * ANALYSIS_STATE. Callers switch on `.state` and only read `.view` when READY.
 */
export function buildAnalysisView(raw, { now = Date.now() } = {}) {
  raw = normalizeBackendSnapshot(raw);
  if (!raw || typeof raw !== "object") {
    return { state: ANALYSIS_STATE.MODEL_FAILURE, message: "No analysis was returned." };
  }

  if (raw.error === "network_failure") {
    return { state: ANALYSIS_STATE.NETWORK_FAILURE, message: raw.message || "Network request failed." };
  }
  if (raw.error === "backend_validation_failure") {
    return {
      state: ANALYSIS_STATE.BACKEND_VALIDATION_FAILURE,
      message: raw.message || "The backend rejected this position or thesis.",
    };
  }
  if (raw.error === "model_not_configured") {
    return { state: ANALYSIS_STATE.MODEL_NOT_CONFIGURED, message: raw.message || "Model analysis is not configured." };
  }
  if (raw.error === "provider_not_configured") {
    return {
      state: ANALYSIS_STATE.PROVIDER_NOT_CONFIGURED,
      message: raw.message || "Evidence provider is not configured.",
    };
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

  const generatedAt = raw.generated_at || null;
  const nowRef = referenceTime(generatedAt, now);
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
    generatedAt,
    assetIdentity: normalizeAssetIdentity(raw.asset_identity || raw.request?.asset_identity, raw.request?.asset),
    directRead: {
      headline: raw.direct_read?.headline || "No direct read available",
      tone: raw.direct_read?.tone || "muted",
      detail: raw.direct_read?.detail || "",
    },
    whatChanged: {
      ...changePresentation,
      kind: change.kind || "insufficient_history",
      since: change.since || null,
      sinceLabel: change.since ? relativeTime(change.since, nowRef) : null,
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
      retrievedLabel: relativeTime(item?.retrieved_at, nowRef),
      freshness: item?.freshness || "unknown",
      url: item?.url || null,
    })),
    meta: {
      ...(raw.meta || {}),
      provenance: raw.meta?.provenance || (raw.meta?.model === "fixture" || raw.meta?.mode === "demo_fixture" || raw.meta?.mode === "deterministic" ? "demo" : raw.meta?.mode === "live_backend" ? "live" : "unknown"),
    },
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
