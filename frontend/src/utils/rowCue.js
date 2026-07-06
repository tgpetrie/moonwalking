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
  moonshot: { key: "moonwalking", label: "Moonwalking", tone: "positive", emoji: "✦", alertOnly: true },
  breakout: { key: "breakout", label: "Breakout", tone: "positive", emoji: "↗", alertOnly: true },
  whale: { key: "whale", label: "Whale", tone: "neutral", emoji: "◉", alertOnly: true },
  stealth: { key: "stealth", label: "Stealth", tone: "neutral", emoji: "◌", alertOnly: true },
  divergence: { key: "reversal-risk", label: "Reversal Risk", tone: "warning", emoji: "⟁", alertOnly: true },
  dump: { key: "cooling", label: "Cooling", tone: "negative", emoji: "↘", alertOnly: true },
  crater: { key: "critical", label: "Critical", tone: "negative", emoji: "⨯", alertOnly: true },
  fear: { key: "reversal-risk", label: "Risk", tone: "negative", emoji: "⊘", alertOnly: true },
  fomo: { key: "heating", label: "Heating", tone: "positive", emoji: "✶", alertOnly: true },
  volume: { key: "whale", label: "Volume Event", tone: "neutral", emoji: "◍", alertOnly: true },
  sentiment: { key: "heating", label: "Sentiment", tone: "neutral", emoji: "∿", alertOnly: true },
  move: { key: "move", label: "Move", tone: "neutral", emoji: "~", alertOnly: true },
  unknown: { key: "alert", label: "Alert", tone: "neutral", emoji: "•", alertOnly: true },
};

const STATE_EMOJI_MAP = {
  moonwalking: "✦",
  breakout: "↗",
  whale: "◉",
  stealth: "◌",
  heating: "✶",
  building: "▵",
  cooling: "↘",
  critical: "⨯",
  "reversal-risk": "⟁",
  alert: "•",
  normal: "",
};

export const ROW_CUE_LEGEND = [
  {
    key: "moonwalking",
    emoji: "✦",
    tone: "positive",
    label: "Moonwalking",
    detail: "Strong upside impulse or moonshot-style alert.",
  },
  {
    key: "breakout",
    emoji: "↗",
    tone: "positive",
    label: "Breakout",
    detail: "Fresh upside expansion or breakout confirmation.",
  },
  {
    key: "heating",
    emoji: "✶",
    tone: "positive",
    label: "Heating",
    detail: "Momentum is building quickly right now.",
  },
  {
    key: "building",
    emoji: "▵",
    tone: "positive",
    label: "Building",
    detail: "Early constructive move, not fully heated yet.",
  },
  {
    key: "whale",
    emoji: "◉",
    tone: "neutral",
    label: "Whale / Volume",
    detail: "Unusual size or volume expansion is driving attention.",
  },
  {
    key: "stealth",
    emoji: "◌",
    tone: "neutral",
    label: "Stealth",
    detail: "Volume is waking up quietly before a larger move.",
  },
  {
    key: "sentiment",
    emoji: "∿",
    tone: "neutral",
    label: "Sentiment",
    detail: "External mood or social context is part of the signal.",
  },
  {
    key: "move",
    emoji: "~",
    tone: "neutral",
    label: "Move",
    detail: "Short-term move alert without a stronger special cue.",
  },
  {
    key: "reversal-risk",
    emoji: "⟁",
    tone: "warning",
    label: "Reversal Risk",
    detail: "Move is vulnerable to failure or reversal.",
  },
  {
    key: "fear",
    emoji: "⊘",
    tone: "negative",
    label: "Risk / Fear",
    detail: "Risk-off or fear-style alert is active.",
  },
  {
    key: "cooling",
    emoji: "↘",
    tone: "negative",
    label: "Cooling",
    detail: "Momentum is fading or rolling over.",
  },
  {
    key: "critical",
    emoji: "⨯",
    tone: "negative",
    label: "Critical",
    detail: "Severe downside or crater-style cue.",
  },
  {
    key: "alert",
    emoji: "•",
    tone: "neutral",
    label: "Generic Alert",
    detail: "Fallback alert marker when no stronger category applies.",
  },
];

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

const CUE_STATE_META = {
  moonwalking: { key: "moonwalking", label: "Moonwalking", tone: "positive", emoji: "✦" },
  breakout: { key: "breakout", label: "Breakout", tone: "positive", emoji: "↗" },
  whale: { key: "whale", label: "Whale", tone: "neutral", emoji: "◉" },
  stealth: { key: "stealth", label: "Stealth", tone: "neutral", emoji: "◌" },
  heating: { key: "heating", label: "Heating", tone: "positive", emoji: "✶" },
  building: { key: "building", label: "Building", tone: "positive", emoji: "▵" },
  sentiment: { key: "sentiment", label: "Sentiment", tone: "neutral", emoji: "∿" },
  move: { key: "move", label: "Move", tone: "neutral", emoji: "~" },
  cooling: { key: "cooling", label: "Cooling", tone: "negative", emoji: "↘" },
  critical: { key: "critical", label: "Critical", tone: "negative", emoji: "⨯" },
  "reversal-risk": { key: "reversal-risk", label: "Reversal Risk", tone: "warning", emoji: "⟁" },
  alert: { key: "alert", label: "Alert", tone: "neutral", emoji: "•" },
  normal: { key: "normal", label: "Watching", tone: "neutral", emoji: "" },
};

const CUE_PRIORITY = {
  moonwalking: 95,
  critical: 92,
  breakout: 86,
  whale: 80,
  stealth: 74,
  "reversal-risk": 72,
  cooling: 68,
  heating: 64,
  building: 52,
  sentiment: 42,
  move: 30,
  alert: 18,
  normal: 0,
};

const ALERT_MEMORY_TTL_MS = {
  liquidity: 10 * 60 * 1000,
  impulse: 8 * 60 * 1000,
  heating: 5 * 60 * 1000,
  context: 5 * 60 * 1000,
  risk: 8 * 60 * 1000,
  default: 8 * 60 * 1000,
};

const ALERT_FAMILY_PRIORITY = {
  liquidity: 88,
  impulse: 82,
  risk: 74,
  heating: 62,
  context: 42,
  default: 54,
};

const SEVERITY_PRIORITY = {
  critical: 14,
  high: 11,
  medium: 7,
  low: 4,
  info: 1,
};

const cueFromKey = (key, overrides = {}) => ({
  ...(CUE_STATE_META[key] || CUE_STATE_META.alert),
  ...overrides,
});

const cuePriority = (cue) => CUE_PRIORITY[cue?.key] || 0;

const intensityForCue = (cue) => {
  const key = cue?.key || "normal";
  if (key === "moonwalking" || key === "critical") return "high";
  if (["whale", "breakout", "reversal-risk", "heating", "cooling"].includes(key)) return "medium";
  if (key === "normal") return "low";
  return "low";
};

const alertSearchText = (alert) => {
  const normalized = alert ? normalizeAlert(alert) : null;
  return [alert?.type_key, alert?.type, alert?.alert_type, normalized?.type_key]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
};

const resolveAlertCue = (alert) => {
  if (!alert) return null;
  const normalized = normalizeAlert(alert);
  const raw = alertSearchText(alert);
  const severity = String(normalized?.severity || alert?.severity || "info").toLowerCase();

  if (raw.includes("liquidity")) {
    return { ...cueFromKey("whale", { label: "Liquidity Shock" }), family: "liquidity", severity };
  }
  if (raw.includes("whale")) {
    return { ...cueFromKey("whale"), family: "liquidity", severity };
  }
  if (raw.includes("stealth")) {
    return { ...cueFromKey("stealth"), family: "liquidity", severity };
  }
  if (raw.includes("volume")) {
    return { ...cueFromKey("whale", { label: "Volume Event", emoji: "◍" }), family: "liquidity", severity };
  }
  if (raw.includes("moonshot")) {
    return { ...cueFromKey("moonwalking", { label: "Moonshot" }), family: "impulse", severity };
  }
  if (raw.includes("crater")) {
    return { ...cueFromKey("critical", { label: "Crater" }), family: "impulse", severity };
  }
  if (raw.includes("breakout")) {
    return { ...cueFromKey("breakout"), family: "impulse", severity };
  }
  if (raw.includes("dump")) {
    return { ...cueFromKey("cooling", { label: "Dump" }), family: "impulse", severity };
  }
  if (
    raw.includes("diverg") ||
    raw.includes("fakeout") ||
    raw.includes("exhaust") ||
    raw.includes("reversal_down") ||
    raw.includes("breadth_failure")
  ) {
    return { ...cueFromKey("reversal-risk"), family: "risk", severity };
  }
  if (raw.includes("fear")) {
    return { ...cueFromKey("reversal-risk", { label: "Risk / Fear", emoji: "⊘", tone: "negative" }), family: "risk", severity };
  }
  if (
    raw.includes("fomo") ||
    raw.includes("thrust") ||
    raw.includes("reversal_up") ||
    raw.includes("trend_break_up") ||
    raw.includes("persistent_gainer") ||
    raw.includes("squeeze_break") ||
    raw.includes("bullish")
  ) {
    return { ...cueFromKey("heating"), family: "heating", severity };
  }
  if (raw.includes("trend_break_down") || raw.includes("persistent_loser")) {
    return { ...cueFromKey("cooling"), family: "risk", severity };
  }
  if (raw.includes("social") || raw.includes("sentiment")) {
    return { ...cueFromKey("sentiment"), family: "context", severity };
  }
  if (raw.includes("move") || raw.includes("impulse")) {
    return { ...cueFromKey("move"), family: "context", severity };
  }

  const normalizedKey = String(normalized?.type_key || "").toLowerCase();
  const mapped = ALERT_STATE_MAP[normalizedKey];
  if (!mapped) return null;
  return {
    ...cueFromKey(mapped.key, {
      label: mapped.label,
      emoji: mapped.emoji ?? STATE_EMOJI_MAP[mapped.key] ?? "",
      tone: mapped.tone,
    }),
    family: "default",
    severity,
  };
};

const heuristicState = ({ pct, changeField, volumePct }) => {
  const thresholds = THRESHOLDS[changeField] || THRESHOLDS.default;

  if (Number.isFinite(volumePct) && Math.abs(volumePct) >= 125 && Math.abs(pct || 0) < thresholds.heating) {
    return cueFromKey("whale", { label: "Volume" });
  }
  if (Number.isFinite(volumePct) && Math.abs(volumePct) >= 70 && Math.abs(pct || 0) < thresholds.building) {
    return cueFromKey("stealth");
  }
  if (!Number.isFinite(pct)) {
    return cueFromKey("normal", { label: "Waiting" });
  }
  if (pct >= thresholds.moonwalking) {
    return cueFromKey("moonwalking");
  }
  if (pct >= thresholds.heating) {
    return cueFromKey("heating");
  }
  if (pct >= thresholds.building) {
    return cueFromKey("building");
  }
  if (pct <= thresholds.critical) {
    return cueFromKey("critical");
  }
  if (pct <= thresholds.risk) {
    return cueFromKey("reversal-risk", { label: "Fragile" });
  }
  if (pct <= thresholds.cooling) {
    return cueFromKey("cooling");
  }
  return cueFromKey("normal");
};

const buildAlertCandidate = (alert, nowMs, { enforceTtl = false } = {}) => {
  if (!alert) return null;
  const cue = resolveAlertCue(alert);
  if (!cue) return null;
  const tsMs = alertTsMs(alert);
  const ageMs = Number.isFinite(tsMs) ? Math.max(0, nowMs - tsMs) : null;
  const ttlMs = ALERT_MEMORY_TTL_MS[cue.family] || ALERT_MEMORY_TTL_MS.default;
  if (enforceTtl && (!Number.isFinite(ageMs) || ageMs > ttlMs)) return null;
  const age = Number.isFinite(ageMs) ? ageLabel(ageMs) : null;
  const primaryScore =
    cuePriority(cue) +
    Math.min(6, Math.round((SEVERITY_PRIORITY[cue.severity] || 0) / 2));
  const score =
    primaryScore +
    (ALERT_FAMILY_PRIORITY[cue.family] || ALERT_FAMILY_PRIORITY.default) +
    (SEVERITY_PRIORITY[cue.severity] || 0) -
    (Number.isFinite(ageMs) ? ageMs / 60000 : 0);
  return {
    ...cue,
    age,
    ageMs,
    tsMs,
    primaryScore,
    score,
    ttlMs,
    sourceAlert: alert,
  };
};

const buildPersistenceCue = ({ token = {}, activeAlert = null, recentAlerts = [] }) => {
  const counts = [
    token?.board_presence_count,
    token?.presence_count,
    token?.presenceCount,
    token?.board_streak,
    token?.boardStreak,
    token?.rank_streak,
    token?.rankStreak,
    token?.repeat_presence,
    token?.peak_count,
    token?.peakCount,
    token?.trend_streak,
    token?.trendStreak,
    activeAlert?.evidence?.streak,
    activeAlert?.extra?.streak,
  ]
    .concat(
      (Array.isArray(recentAlerts) ? recentAlerts : []).flatMap((alert) => [
        alert?.evidence?.streak,
        alert?.extra?.streak,
      ])
    )
    .map((value) => Math.max(0, Math.round(toNum(value) || 0)));

  const count = counts.reduce((max, value) => Math.max(max, value), 0);
  if (count < 2) return null;

  return {
    count,
    compactCount: count >= 3 ? `${Math.min(count, 9)}x` : "",
    title:
      count >= 3
        ? `Repeated board presence or streak: ${count} refreshes`
        : "Repeated board presence",
    ariaLabel:
      count >= 3
        ? `${count} times repeated board presence`
        : "Repeated board presence",
  };
};

const uniqueAlertCandidates = (candidates = []) => {
  const seen = new Set();
  const out = [];
  candidates.forEach((candidate) => {
    if (!candidate?.key) return;
    const dedupeKey = [candidate.key, candidate.tsMs || "", candidate.age || ""].join(":");
    if (seen.has(dedupeKey)) return;
    seen.add(dedupeKey);
    out.push(candidate);
  });
  return out;
};

export function deriveRowCue({
  token = {},
  changeField = "change_1m",
  activeAlert = null,
  recentAlerts = [],
  rankDelta = 0,
  isWatchlisted = false,
  nowMs = Date.now(),
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

  const fallbackCue = heuristicState({ pct, changeField, volumePct });
  const activeCandidate = buildAlertCandidate(activeAlert, nowMs, { enforceTtl: false });

  let primaryCue = fallbackCue?.key !== "normal"
    ? {
        ...fallbackCue,
        source: "board",
        score: cuePriority(fallbackCue),
        title: `Current board context: ${fallbackCue.label}`,
      }
    : null;

  if (activeCandidate && (!primaryCue || activeCandidate.primaryScore >= primaryCue.score)) {
    primaryCue = {
      ...activeCandidate,
      source: "active",
      score: activeCandidate.primaryScore,
      title: activeCandidate.age ? `${activeCandidate.label} - ${activeCandidate.age} ago` : activeCandidate.label,
    };
  }

  const recentCandidates = uniqueAlertCandidates(
    [activeAlert, ...(Array.isArray(recentAlerts) ? recentAlerts : [])]
      .map((alert) => buildAlertCandidate(alert, nowMs, { enforceTtl: true }))
      .filter(Boolean)
      .filter((candidate) => candidate.key !== "normal")
      .filter((candidate) => !primaryCue || candidate.key !== primaryCue.key)
  )
    .sort((a, b) => b.score - a.score || (a.ageMs ?? Infinity) - (b.ageMs ?? Infinity));

  const secondaryCue = recentCandidates[0]
    ? {
        ...recentCandidates[0],
        source: "recent",
        title: recentCandidates[0].age
          ? `Recent ${recentCandidates[0].label} - ${recentCandidates[0].age} ago`
          : `Recent ${recentCandidates[0].label}`,
      }
    : null;

  const displayCue = primaryCue || secondaryCue || fallbackCue;
  const persistenceCue = buildPersistenceCue({ token, activeAlert, recentAlerts });
  const rankShiftTone = rankDelta > 0 ? "up" : rankDelta < 0 ? "down" : "flat";
  const rankShiftLabel = rankDelta > 0 ? `+${rankDelta}` : rankDelta < 0 ? `${rankDelta}` : "";

  return {
    key: displayCue?.key || "normal",
    label: displayCue?.label || "Watching",
    emoji: displayCue?.emoji || "",
    title: displayCue?.title || displayCue?.label || "Watching",
    tone: displayCue?.tone || "neutral",
    severity: activeCandidate?.severity || "info",
    intensity: intensityForCue(displayCue),
    display: displayCue || cueFromKey("normal"),
    primary: primaryCue,
    secondary: secondaryCue,
    persistence: persistenceCue,
    isWatchlisted: Boolean(isWatchlisted),
    rankShiftTone,
    rankShiftLabel,
    triggerKey: [
      displayCue?.key || "normal",
      primaryCue?.key || "",
      secondaryCue?.key || "",
      secondaryCue?.age || "",
      persistenceCue?.count || 0,
      clamp(rankDelta, -9, 9),
      Number.isFinite(pct) ? clamp(Math.round(pct), -99, 99) : "na",
    ].join(":"),
  };
}
