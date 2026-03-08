import { normalizeAlert } from "./alerts_normalize";

const toNum = (value) => {
  if (value == null) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const cleaned = String(value).replace(/[%+,]/g, "").trim();
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const THRESHOLDS = {
  change_1m: { moonwalking: 8, heating: 3.5, building: 1.1, cooling: -1.1, risk: -3.5, critical: -8 },
  change_3m: { moonwalking: 12, heating: 6, building: 2.2, cooling: -2.2, risk: -6, critical: -12 },
  change_watch: { moonwalking: 14, heating: 6, building: 2.5, cooling: -2.5, risk: -6, critical: -12 },
  default: { moonwalking: 10, heating: 4, building: 1.5, cooling: -1.5, risk: -4, critical: -9 },
};

const ALERT_STATE_MAP = {
  moonshot: { key: "moonwalking", label: "Moonwalking", tone: "positive", emoji: "🚀", alertOnly: true },
  breakout: { key: "breakout", label: "Breakout", tone: "positive", emoji: "📈", alertOnly: true },
  whale: { key: "whale", label: "Whale", tone: "positive", emoji: "🐋", alertOnly: true },
  stealth: { key: "stealth", label: "Stealth", tone: "neutral", emoji: "🕵️", alertOnly: true },
  divergence: { key: "reversal-risk", label: "Reversal Risk", tone: "warning", emoji: "⚖️", alertOnly: true },
  dump: { key: "cooling", label: "Cooling", tone: "negative", emoji: "📉", alertOnly: true },
  crater: { key: "critical", label: "Critical", tone: "negative", emoji: "🕳️", alertOnly: true },
  fear: { key: "reversal-risk", label: "Risk", tone: "negative", emoji: "🧊", alertOnly: true },
  fomo: { key: "heating", label: "Heating", tone: "positive", emoji: "🔥", alertOnly: true },
  volume: { key: "whale", label: "Volume Event", tone: "neutral", emoji: "📊", alertOnly: true },
  sentiment: { key: "heating", label: "Sentiment", tone: "neutral", emoji: "🌊", alertOnly: true },
  move: { key: "heating", label: "Heating", tone: "neutral", emoji: "⚡", alertOnly: true },
  unknown: { key: "alert", label: "Alert", tone: "neutral", emoji: "🔔", alertOnly: true },
};

const STATE_EMOJI_MAP = {
  moonwalking: "🚀",
  breakout: "📈",
  whale: "🐋",
  stealth: "🕵️",
  heating: "⚡",
  building: "↗",
  cooling: "📉",
  critical: "🕳️",
  "reversal-risk": "⚠️",
  alert: "🔔",
  normal: "",
};

const ageLabel = (ms) => {
  if (!Number.isFinite(ms) || ms < 0) return null;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
};

const alertTsMs = (alert) => {
  if (!alert || typeof alert !== "object") return null;
  const fields = [
    alert.event_ts_ms,
    alert.ts_ms,
    alert.timestamp_ms,
    alert.event_ts,
    alert.ts,
    alert.timestamp,
    alert.created_at,
    alert.createdAt,
  ];
  for (const value of fields) {
    const direct = toNum(value);
    if (Number.isFinite(direct)) {
      return direct < 1e12 ? direct * 1000 : direct;
    }
    const parsed = Date.parse(String(value || ""));
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
};

const heuristicState = ({ pct, changeField, volumePct }) => {
  const thresholds = THRESHOLDS[changeField] || THRESHOLDS.default;

  if (Number.isFinite(volumePct) && Math.abs(volumePct) >= 125 && Math.abs(pct || 0) < thresholds.heating) {
    return { key: "whale", label: "Volume", tone: "neutral" };
  }
  if (Number.isFinite(volumePct) && Math.abs(volumePct) >= 70 && Math.abs(pct || 0) < thresholds.building) {
    return { key: "stealth", label: "Stealth", tone: "neutral" };
  }
  if (!Number.isFinite(pct)) {
    return { key: "normal", label: "Waiting", tone: "neutral" };
  }
  if (pct >= thresholds.moonwalking) {
    return { key: "moonwalking", label: "Moonwalking", tone: "positive" };
  }
  if (pct >= thresholds.heating) {
    return { key: "heating", label: "Heating", tone: "positive" };
  }
  if (pct >= thresholds.building) {
    return { key: "building", label: "Building", tone: "positive" };
  }
  if (pct <= thresholds.critical) {
    return { key: "critical", label: "Critical", tone: "negative" };
  }
  if (pct <= thresholds.risk) {
    return { key: "reversal-risk", label: "Fragile", tone: "warning" };
  }
  if (pct <= thresholds.cooling) {
    return { key: "cooling", label: "Cooling", tone: "negative" };
  }
  return { key: "normal", label: "Watching", tone: "neutral" };
};

export function deriveRowCue({
  token = {},
  changeField = "change_1m",
  activeAlert = null,
  rankDelta = 0,
  isWatchlisted = false,
}) {
  const pct = toNum(
    token?.[changeField] ??
      token?.change_1m ??
      token?.change_3m ??
      token?.change_watch ??
      token?.price_change_percentage_1min ??
      token?.price_change_percentage_3min
  );
  const volumePct = toNum(
    token?.volume_change_1h_pct ??
      token?.volume_change_percentage_1h ??
      token?.volumeChangePct ??
      token?.volume_change_pct
  );

  const normalizedAlert = activeAlert ? normalizeAlert(activeAlert) : null;
  const alertType = String(normalizedAlert?.type_key || "").toLowerCase();
  const mappedAlert = ALERT_STATE_MAP[alertType] || null;
  const fallbackState = heuristicState({ pct, changeField, volumePct });
  const state = mappedAlert || fallbackState;
  const severity = String(normalizedAlert?.severity || "").toLowerCase();

  const timeSinceAlert = (() => {
    const ts = alertTsMs(normalizedAlert);
    if (!Number.isFinite(ts)) return null;
    return ageLabel(Date.now() - ts);
  })();
  const alertTimestamp = alertTsMs(normalizedAlert);

  const rankShiftTone = rankDelta > 0 ? "up" : rankDelta < 0 ? "down" : "flat";
  const rankShiftLabel = rankDelta > 0 ? `+${rankDelta}` : rankDelta < 0 ? `${rankDelta}` : "";
  const intensity =
    state.key === "moonwalking" || state.key === "critical"
      ? "high"
      : state.key === "whale" || state.key === "breakout" || state.key === "reversal-risk" || state.key === "heating"
        ? "medium"
        : "low";

  return {
    key: state.key,
    label: state.label,
    emoji: mappedAlert?.emoji ?? STATE_EMOJI_MAP[state.key] ?? "",
    title: timeSinceAlert ? `${state.label} - fresh ${timeSinceAlert}` : state.label,
    tone: state.tone,
    severity,
    intensity,
    rankShiftTone,
    rankShiftLabel,
    triggerKey: [
      state.key,
      alertType,
      severity,
      clamp(rankDelta, -9, 9),
      alertTimestamp || "",
      Number.isFinite(pct) ? clamp(Math.round(pct), -99, 99) : "na",
    ].join(":"),
  };
}
