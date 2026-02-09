import {
  extractWindow,
  extractPct,
  normalizeAlert,
  typeKeyToUpper,
  TYPE_EMOJI,
} from "./alerts_normalize";

export { extractWindow, extractPct };

export const windowLabelFromType = (raw) => {
  const fromRaw = extractWindow(raw);
  if (fromRaw) return fromRaw;
  const t = String(raw || "").toUpperCase();
  if (t.includes("_1M")) return "1m";
  if (t.includes("_3M")) return "3m";
  if (t.includes("_5M")) return "5m";
  if (t.includes("_15M")) return "15m";
  if (t.includes("_1H")) return "1h";
  return "";
};

export const parseImpulseMessage = (a) => {
  const msg = String(a?.message || "");
  const title = String(a?.title || "");
  const parsed_pct =
    typeof a?.pct === "number" && Number.isFinite(a.pct)
      ? a.pct
      : extractPct(msg) ?? extractPct(title);

  const parsed_window_label =
    String(a?.window || "").toLowerCase() ||
    windowLabelFromType(a?.type) ||
    extractWindow(msg) ||
    extractWindow(title) ||
    "";

  const directionRaw = String(a?.direction || "").toLowerCase();
  let parsed_direction = null;

  if (["up", "down", "flat"].includes(directionRaw)) {
    parsed_direction = directionRaw;
  } else if (Number.isFinite(parsed_pct)) {
    parsed_direction = parsed_pct > 0 ? "up" : parsed_pct < 0 ? "down" : "flat";
  }

  return {
    parsed_pct: Number.isFinite(parsed_pct) ? parsed_pct : null,
    parsed_window_label,
    parsed_direction: parsed_direction || "flat",
  };
};

export const ALERT_TYPE_LABELS = {
  MOONSHOT: `${TYPE_EMOJI.moonshot} MOONSHOT`,
  CRATER: `${TYPE_EMOJI.crater} CRATER`,
  BREAKOUT: `${TYPE_EMOJI.breakout} BREAKOUT`,
  DUMP: `${TYPE_EMOJI.dump} DUMP`,
  MOVE: `${TYPE_EMOJI.move} MOVE`,
  WHALE: `${TYPE_EMOJI.whale} WHALE`,
  STEALTH: `${TYPE_EMOJI.stealth} STEALTH`,
  DIVERGENCE: `${TYPE_EMOJI.divergence} DIVERGENCE`,
  FOMO: `${TYPE_EMOJI.fomo} FOMO`,
  FEAR: `${TYPE_EMOJI.fear} FEAR`,
  VOLUME: `${TYPE_EMOJI.volume} VOLUME`,
  SENTIMENT: `${TYPE_EMOJI.sentiment} SENTIMENT`,
  ALERT: `${TYPE_EMOJI.unknown} ALERT`,
};

export const getAlertTypeLabel = (alertType) => {
  const key = String(alertType || "").toUpperCase();
  return ALERT_TYPE_LABELS[key] || ALERT_TYPE_LABELS.ALERT;
};

export const deriveAlertType = ({ type, pct, severity, window, message, title } = {}) => {
  const norm = normalizeAlert({ type, pct, severity, window, message, title });
  return typeKeyToUpper(norm.type_key);
};
