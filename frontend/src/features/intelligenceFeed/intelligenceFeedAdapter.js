// Intelligence Feed — backend payload -> view model.
//
// One place where a drifting backend payload is caught, matching the Ask Bhabit
// convention. The rules that matter here:
//
//   - Missing data must never render as a confident zero. A null percentage is
//     "unknown", not "0.00%".
//   - The feed states facts. Nothing in this file infers, predicts, or advises.
//   - An event whose evidence packet is unavailable still renders, flagged, so
//     the user is never shown a claim we cannot back up.

export const EVENT_STATUS = Object.freeze({
  DETECTED: "detected",
  SEEN: "seen",
  DISMISSED: "dismissed",
});

export const CONFIDENCE_PRESENTATION = Object.freeze({
  deterministic: {
    label: "Measured",
    tone: "factual",
    blurb: "Computed directly from your stored portfolio snapshots.",
  },
  unknown: {
    label: "Unverified",
    tone: "muted",
    blurb: "Supporting evidence for this event is unavailable.",
  },
});

const isNumber = (value) => typeof value === "number" && Number.isFinite(value);

export function formatPct(value) {
  if (!isNumber(value)) return null;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatUsd(value) {
  if (!isNumber(value)) return null;
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatTimestamp(iso) {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Describe *why* the event fired, in the engine's own terms. */
export function describeReason(reason) {
  if (!reason || typeof reason !== "object") return null;
  const magnitude = isNumber(reason.magnitude_pct)
    ? `${reason.magnitude_pct.toFixed(2)}%`
    : "an unrecorded amount";
  if (reason.type === "asset_contribution") {
    return `${reason.asset_symbol || "An asset"} moved ${magnitude} of your portfolio value ${
      reason.direction === "down" ? "down" : "up"
    }`;
  }
  if (reason.type === "portfolio_move") {
    return `Total portfolio moved ${magnitude} ${
      reason.direction === "down" ? "down" : "up"
    }`;
  }
  return null;
}

export function buildEventView(event) {
  if (!event || typeof event !== "object") return null;

  const impact = event.portfolio_impact || {};
  const changePct = impact.change_pct ?? event.what_changed?.total_change_pct ?? null;
  const changeUsd = impact.change_usd ?? event.what_changed?.total_change_usd ?? null;
  const evidenceAvailable = Boolean(event.evidence?.available);
  const confidenceLevel = event.confidence?.level || "unknown";

  return {
    id: event.event_id,
    type: event.event_type,
    status: event.status || EVENT_STATUS.DETECTED,
    headline: event.headline || "Something changed in your portfolio",
    observedAt: event.observed_at || null,
    observedAtLabel: formatTimestamp(event.observed_at),
    affectedAssets: Array.isArray(event.affected_assets) ? event.affected_assets : [],
    reasons: (event.what_changed?.reasons || [])
      .map(describeReason)
      .filter(Boolean),
    impact: {
      changePct,
      changeUsd,
      // null (unknown) is preserved distinctly from a real zero.
      changePctLabel: formatPct(changePct),
      changeUsdLabel: formatUsd(changeUsd),
      previousTotalLabel: formatUsd(impact.previous_total_usd),
      currentTotalLabel: formatUsd(impact.current_total_usd),
      direction: isNumber(changePct) ? (changePct > 0 ? "up" : changePct < 0 ? "down" : "flat") : "unknown",
    },
    movers: (event.supporting_metrics?.biggest_movers || []).map((mover) => ({
      symbol: mover.asset_symbol,
      valueDeltaLabel: formatUsd(mover.value_delta_usd),
      contributionLabel: formatPct(mover.contribution_pct),
    })),
    allocationChanges: (event.supporting_metrics?.allocation_changes || []).map((row) => ({
      symbol: row.asset_symbol,
      fromLabel: formatPct(row.from_pct),
      toLabel: formatPct(row.to_pct),
      deltaLabel: formatPct(row.delta_pct),
    })),
    confidence: {
      level: confidenceLevel,
      source: event.confidence?.source || null,
      ...(CONFIDENCE_PRESENTATION[confidenceLevel] || CONFIDENCE_PRESENTATION.unknown),
    },
    evidenceAvailable,
    // Reserved: the LLM explanation layer is not built yet.
    explanation: event.explanation ?? null,
  };
}

export function buildFeedView(data) {
  const events = Array.isArray(data?.events) ? data.events : [];
  const views = events.map(buildEventView).filter(Boolean);
  return {
    events: views,
    count: views.length,
    isEmpty: views.length === 0,
  };
}
