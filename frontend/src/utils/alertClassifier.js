// Shared alert/intel classification helpers (single source of truth)
export const windowLabelFromType = (raw) => {
  const t = String(raw || "").toUpperCase();
  if (t.includes("_1M")) return "1m";
  if (t.includes("_3M")) return "3m";
  if (t.includes("_5M")) return "5m";
  if (t.includes("_15M")) return "15m";
  if (t.includes("_1H")) return "1h";
  return "";
};

// Parse backend message like: "TROLL-USD moved +10.94% in 1m"
export const parseImpulseMessage = (a) => {
  const msg = String(a?.message || "");
  const title = String(a?.title || "");

  const m = msg.match(/moved\s*([+\-]?\d+(?:\.\d+)?)%\s*in\s*(\d+)\s*m/i);
  const pct = m ? Number(m[1]) : null;
  const winM = m ? Number(m[2]) : null;

  let direction = null;
  if (pct !== null && Number.isFinite(pct)) direction = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  if (!direction) {
    const t = title.toLowerCase();
    if (t.includes(" down")) direction = "down";
    else if (t.includes(" up")) direction = "up";
    else direction = "flat";
  }

  return {
    parsed_pct: pct !== null && Number.isFinite(pct) ? pct : null,
    parsed_window_label: winM ? `${winM}m` : "",
    parsed_direction: direction,
  };
};

// Alert type display labels (emoji + name)
export const ALERT_TYPE_LABELS = {
  MOONSHOT:   "🚀 MOONSHOT",
  CRATER:     "📉 CRATER",
  BREAKOUT:   "📈 BREAKOUT",
  DUMP:       "📉 DUMP",
  WHALE:      "🐋 WHALE",
  STEALTH:    "👤 STEALTH",
  DIVERGENCE: "⚖️ DIVERGENCE",
  FOMO:       "🔥 FOMO",
  FEAR:       "🥶 FEAR",
  IMPULSE:    "⚡ IMPULSE",
  VOLUME:     "📊 VOLUME",
  SENTIMENT:  "🌊 SENTIMENT",
};

// Aligns with AlertsDock label logic
export const deriveAlertType = ({ type, pct, severity } = {}) => {
  const t = String(type || "").toUpperCase();
  const sev = String(severity || "").toUpperCase();
  const w = windowLabelFromType(type);
  const strong = w === "1m" ? 1.25 : w === "3m" ? 1.75 : 2.5;
  const medium = w === "1m" ? 0.75 : w === "3m" ? 1.0 : 1.5;
  const pctNum = Number(pct);
  const abs = Number.isFinite(pctNum) ? Math.abs(pctNum) : 0;

  // Exact type matches from backend (new rich types)
  if (t === "MOONSHOT") return "MOONSHOT";
  if (t === "CRATER") return "CRATER";
  if (t === "BREAKOUT") return "BREAKOUT";
  if (t === "DUMP") return "DUMP";
  if (t === "WHALE_MOVE" || t.includes("WHALE")) return "WHALE";
  if (t === "STEALTH_MOVE" || t.includes("STEALTH")) return "STEALTH";
  if (t === "FOMO_ALERT" || t.includes("FOMO")) return "FOMO";
  if (t === "FEAR_ALERT" || t.includes("FEAR")) return "FEAR";
  if (t.includes("DIVERGENCE")) return "DIVERGENCE";
  if (t.includes("VOLUME")) return "VOLUME";
  if (t.includes("SENTIMENT")) return "SENTIMENT";
  if (!Number.isFinite(pctNum)) return "IMPULSE";

  // Fallback: classify by magnitude
  if (pctNum >= 0) {
    if (sev === "CRITICAL" || abs >= strong) return "MOONSHOT";
    if (sev === "HIGH" || abs >= medium) return "BREAKOUT";
    return "IMPULSE";
  }

  if (sev === "CRITICAL" || abs >= strong) return "CRATER";
  if (sev === "HIGH" || abs >= medium) return "DUMP";
  return "IMPULSE";
};

// Get display label for an alert type
export const getAlertTypeLabel = (alertType) => {
  return ALERT_TYPE_LABELS[alertType] || ALERT_TYPE_LABELS.IMPULSE;
};
