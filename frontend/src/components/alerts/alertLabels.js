/**
 * Plain-language translation for alert rules and events.
 *
 * The backend is precise; the interface stays calm. Internal machinery —
 * arm_cycle, fingerprint, armed, reset_pct, percent_rearm_ratio — is never
 * surfaced here, and raw enum values never reach the DOM.
 *
 * No buy/sell/hold language, no predictions, no loss-prevention promises.
 */

export const WINDOWS = [
  { value: "1h", label: "a rolling 1-hour period", short: "1h" },
  { value: "4h", label: "a rolling 4-hour period", short: "4h" },
  { value: "24h", label: "a rolling 24-hour period", short: "24h" },
];
// Deliberately no 7d: the backend rejects it and it must not exist in the DOM.

export const TRIGGER_TYPES = [
  { value: "percent_move", label: "moves by" },
  { value: "price_cross", label: "reaches a price" },
];

export const DIRECTIONS = {
  price_cross: [
    { value: "above", label: "goes above" },
    { value: "below", label: "goes below" },
  ],
  percent_move: [
    { value: "up", label: "moves up" },
    { value: "down", label: "moves down" },
    { value: "either", label: "moves either way" },
  ],
};

const STATUS_LABELS = {
  active: "Active",
  cooling_down: "Waiting to reset",
  paused: "Paused",
  triggered: "Completed",
  expired: "Expired",
};

const STATUS_TONES = {
  active: "positive",
  cooling_down: "neutral",
  paused: "muted",
  triggered: "muted",
  expired: "muted",
};

export function statusLabel(status) {
  return STATUS_LABELS[String(status || "").toLowerCase()] || "Active";
}

export function statusTone(status) {
  return STATUS_TONES[String(status || "").toLowerCase()] || "neutral";
}

export function windowLabel(value) {
  return WINDOWS.find((w) => w.value === value)?.label || "";
}

export function windowShort(value) {
  return WINDOWS.find((w) => w.value === value)?.short || "";
}

export function directionLabel(triggerType, direction) {
  const list = DIRECTIONS[triggerType] || [];
  return list.find((d) => d.value === direction)?.label || "";
}

export function formatPrice(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  const abs = Math.abs(n);
  const digits = abs >= 10000 ? 0 : abs >= 100 ? 2 : abs >= 1 ? 3 : 6;
  return `$${n.toLocaleString(undefined, {
    minimumFractionDigits: digits === 0 ? 0 : 2,
    maximumFractionDigits: digits,
  })}`;
}

/** One-line human summary of what a rule watches. */
export function describeRule(rule) {
  if (!rule) return "";
  const symbol = rule.symbol || "";
  const params = rule.params || {};
  const dir = directionLabel(rule.trigger_type, params.direction);

  if (rule.trigger_type === "price_cross") {
    return `${symbol} ${dir} ${formatPrice(params.threshold)}`;
  }
  const pct = Number(params.threshold);
  const pctText = Number.isFinite(pct) ? `${pct}%` : "";
  return `${symbol} ${dir} ${pctText} during ${windowLabel(params.window)}`;
}

/** Human summary of a fired event. */
export function describeEvent(event) {
  if (!event) return "";
  if (event.event_type === "price_cross") {
    return `Reached ${formatPrice(event.observed_value)} (target ${formatPrice(
      event.boundary_value
    )})`;
  }
  const parts = [`Reached ${formatPrice(event.observed_value)}`];
  if (Number.isFinite(Number(event.boundary_value))) {
    parts.push(`${Number(event.boundary_value)}% mark`);
  }
  if (event.window_label) parts.push(windowShort(event.window_label));
  return parts.join(" · ");
}

export function repeatLabel(mode) {
  return mode === "recurring" ? "Notifies again after the market resets" : "Notifies once";
}

/** Relative time, e.g. "12m ago". Falls back to a locale string. */
export function timeAgo(value) {
  const ts = typeof value === "number" ? value * 1000 : Date.parse(String(value || ""));
  if (!Number.isFinite(ts)) return "";
  const diff = Date.now() - ts;
  if (diff < 0) return "just now";
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(ts).toLocaleDateString();
}
