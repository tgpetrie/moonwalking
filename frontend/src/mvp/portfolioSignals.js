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
