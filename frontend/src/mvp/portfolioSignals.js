function finite(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function includesRisk(row, phrase) {
  return (Array.isArray(row?.live_risks) ? row.live_risks : []).some((risk) =>
    String(risk || "").toLowerCase().includes(phrase)
  );
}

// Evidence tiers replace the old binary "not enough proof" gate. They grade how
// much comparable forward-outcome history BHABIT has for a signal, so the UI can
// say *how sure* it is instead of a flat yes/no. Thresholds are deliberately
// conservative: a rate is only quoted once the sample is large enough to mean
// something (>=10). Tune the band edges here — everything downstream reads them.
const EVIDENCE_TIERS = [
  { min: 100, key: "strong", label: "Strong", tone: "positive", quoteRate: true },
  { min: 30, key: "solid", label: "Solid", tone: "info", quoteRate: true },
  { min: 10, key: "building", label: "Building", tone: "info", quoteRate: true },
  { min: 1, key: "emerging", label: "Emerging", tone: "muted", quoteRate: false },
  { min: 0, key: "none", label: "No history yet", tone: "muted", quoteRate: false },
];

export function describeEvidenceTier(sampleSize) {
  const n = finite(sampleSize);
  const count = n === null || n < 0 ? 0 : Math.floor(n);
  const tier = EVIDENCE_TIERS.find((t) => count >= t.min) || EVIDENCE_TIERS[EVIDENCE_TIERS.length - 1];
  const shown = count >= 100 ? "100+" : String(count);
  const label = count > 0 ? `${tier.label} · ${shown}` : tier.label;

  let blurb;
  if (count <= 0) {
    blurb = "No comparable-signal outcomes recorded yet.";
  } else if (!tier.quoteRate) {
    blurb = `Emerging — ${count} comparable outcome${count === 1 ? "" : "s"} so far, too few to quote a rate.`;
  } else if (tier.key === "building") {
    blurb = `${count} comparable outcomes — a trend is forming, not yet conclusive.`;
  } else if (tier.key === "solid") {
    blurb = `${count} comparable outcomes — a usable base rate.`;
  } else {
    blurb = `${shown} comparable outcomes — a statistically meaningful base rate.`;
  }

  return { key: tier.key, label, tone: tier.tone, quoteRate: tier.quoteRate, count, blurb };
}

export function concentrationLabel(allocationValue) {
  const allocation = finite(allocationValue);
  if (allocation === null) return "Concentration unavailable";
  if (allocation >= 35) return "Highly concentrated";
  if (allocation >= 20) return "Elevated concentration";
  if (allocation >= 10) return "Moderately concentrated";
  return "Balanced allocation";
}

export function deriveHoldingRead(holding, liveRow) {
  if (holding?.is_cash) {
    return {
      label: "CASH",
      tone: "neutral",
      score: null,
      explanation: "Available cash is shown for allocation context and is not scored.",
    };
  }

  const score = finite(liveRow?.live_score);
  const dataQuality = finite(liveRow?.data_quality);
  if (score === null || dataQuality === null || dataQuality < 35) {
    return {
      label: "NOT ENOUGH PROOF",
      tone: "muted",
      score,
      explanation: "BHABIT does not have enough current independent evidence to grade this holding responsibly.",
    };
  }

  const pnlPct = finite(holding?.unrealized_pnl_pct);
  const sellingPressure = includesRisk(liveRow, "selling") || includesRisk(liveRow, "failure");
  const risks = Array.isArray(liveRow?.live_risks) ? liveRow.live_risks : [];
  const reasons = Array.isArray(liveRow?.live_reasons) ? liveRow.live_reasons : [];

  let label = "NOT ENOUGH PROOF";
  let tone = "muted";
  if (score <= 30) {
    label = "STAY CLEAR";
    tone = "danger";
  } else if (score < 48 || sellingPressure) {
    label = "EXIT WATCH";
    tone = "danger";
  } else if (pnlPct !== null && pnlPct > 0 && score < 65) {
    label = "PROTECT GAIN";
    tone = "warning";
  } else if (score >= 65) {
    label = "HOLD STRONG";
    tone = "positive";
  }

  const evidence = [...reasons.slice(0, 2), ...risks.slice(0, 1)];
  const fallback =
    label === "HOLD STRONG"
      ? "Current momentum and confirmation remain aligned."
      : label === "PROTECT GAIN"
        ? "The position is positive, but current confirmation is no longer strong."
        : label === "EXIT WATCH"
          ? "Current confirmation is weakening or an execution risk is present."
          : label === "STAY CLEAR"
            ? "Current evidence is negative and does not support adding risk."
            : "Current evidence is mixed and not strong enough for a responsible answer.";

  return {
    label,
    tone,
    score: Math.round(score),
    explanation: evidence.length ? evidence.join("; ") : fallback,
  };
}

// Maps a holding.intel.posture (from /api/portfolio/intel) to display text and a
// tone that reuses the existing card tone classes (positive/warning/danger/muted).
const POSTURE_PRESENTATION = {
  momentum_favorable: { label: "Momentum favorable", tone: "positive" },
  pressure_adverse: { label: "Pressure adverse", tone: "danger" },
  momentum_fading: { label: "Momentum fading", tone: "warning" },
  developing: { label: "Developing", tone: "info" },
  neutral: { label: "Neutral", tone: "muted" },
  no_signal: { label: "No live signal", tone: "muted" },
  // Descriptive 24h reads (no live signal) — labels/tones come from the backend
  // _descriptive_read bands, but keep presentation here so the UI degrades
  // gracefully if the payload only carries the posture key.
  descriptive_up_strong: { label: "Up big today", tone: "positive" },
  descriptive_up: { label: "Up today", tone: "positive" },
  descriptive_flat: { label: "Quiet today", tone: "muted" },
  descriptive_down: { label: "Down today", tone: "warning" },
  descriptive_down_strong: { label: "Down big today", tone: "danger" },
};

export function describePosture(intel) {
  const posture = intel?.posture || "no_signal";
  const base = POSTURE_PRESENTATION[posture] || POSTURE_PRESENTATION.no_signal;
  const confidence = finite(intel?.signal?.confidence);
  const isDescriptive = intel?.read_source === "descriptive";
  // Prefer a live signal's read; fall back to the descriptive 24h read so
  // board non-movers still get a short line under the chip.
  const shortRead =
    intel?.signal?.short_read ||
    intel?.signal?.label ||
    intel?.read?.short ||
    null;
  return {
    ...base,
    posture,
    confidence,
    shortRead,
    isDescriptive,
  };
}

export function indexLiveRankings(payload) {
  const rows = Array.isArray(payload?.live_rankings) ? payload.live_rankings : [];
  return rows.reduce((index, row) => {
    const symbol = String(row?.symbol || row?.product_id || "")
      .toUpperCase()
      .replace(/-(USD|USDC|USDT)$/, "");
    if (symbol) index[symbol] = row;
    return index;
  }, {});
}
