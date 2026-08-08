import { describeEvent } from "./alertLabels.js";

/**
 * Unified intelligence-event envelope.
 *
 * Today Moonwalkings has two disconnected event planes: anonymous market-wide
 * alerts (alerts_engine → DataContext) and user-scoped rule events
 * (alert_events_user → /api/alert-history). This module folds both — plus
 * pending recommendations — into one normalized shape so a single stream can
 * rank them by personal relevance:
 *
 *   { id, kind, symbol, ts, headline, detail, severity, reason, score, raw }
 *
 * kind:    'your_alert' | 'suggestion' | 'market'
 * reason:  'holding' | 'your_rule' | 'watchlist' | 'market'  (why it's shown)
 *
 * This is deliberately a pure adapter over existing payloads — no fetching,
 * no storage, fully deterministic given `nowMs`. If the backend ever grows a
 * real unified event store (the long-term model), this file is the schema it
 * has to satisfy, and the UI above it doesn't change.
 */

export const KINDS = { YOUR_ALERT: "your_alert", SUGGESTION: "suggestion", MARKET: "market" };
export const REASONS = { HOLDING: "holding", RULE: "your_rule", WATCHLIST: "watchlist", MARKET: "market" };

// Base weight by kind: something that actually fired for *you* always beats a
// suggestion, which beats ambient market noise.
const KIND_BASE = { your_alert: 100, suggestion: 60, market: 25 };

const REASON_BOOST = { holding: 40, your_rule: 30, watchlist: 25, market: 0 };

// Sized so the bands stay disjoint and explainable:
//   your fired alert:            130–145  (always first)
//   urgent market on a holding:  ≤105     (critical+holding+fresh)
//   suggestion:                  100 (portfolio) / 85 (watchlist)
//   ambient relevant market:     below
// A fresh critical move on a coin you HOLD must outrank a static suggestion —
// that is why critical/high sit at 25/15, not lower.
const SEVERITY_BOOST = { critical: 25, high: 15, medium: 6, low: 2, info: 0 };

// Market noise ages out of "now" quickly; your own fired alerts linger longer
// (History remains the permanent archive).
export const MARKET_MAX_AGE_MS = 6 * 3600 * 1000;
export const USER_EVENT_MAX_AGE_MS = 48 * 3600 * 1000;

const RECENCY_MAX_BOOST = 15;

// Dedupe identity (candidate for the future canonical event model):
// (symbol, event family, time proximity). Rule events are price-move alerts
// today (price_cross / percent_move), so the family test is applied to the
// market item's type. Whale/volume/sentiment/divergence types are never
// suppressed — they are different intelligence about the same coin.
export const DEDUPE_PRICE_FAMILY = new Set([
  "moonshot",
  "crater",
  "breakout",
  "dump",
  "move",
]);
export const DEDUPE_PROXIMITY_MS = 2 * 3600 * 1000;

export function toTsMs(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number" && Number.isFinite(value)) {
    return value < 1e12 ? value * 1000 : value;
  }
  const n = Number(value);
  if (Number.isFinite(n)) return n < 1e12 ? n * 1000 : n;
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : null;
}

const cleanSymbol = (value) =>
  String(value || "")
    .toUpperCase()
    .replace(/-USD$|-USDT$|-PERP$/i, "")
    .trim();

/** Holdings signal available client-side today: recommendation/rule basis. */
export function holdingSymbolsFrom({ recommendations = [], rules = [] } = {}) {
  const out = new Set();
  for (const rec of recommendations) {
    if (rec?.basis === "portfolio" && rec.symbol) out.add(cleanSymbol(rec.symbol));
  }
  for (const rule of rules) {
    if (rule?.recommendation_basis === "portfolio" && rule.symbol) {
      out.add(cleanSymbol(rule.symbol));
    }
  }
  return out;
}

export function normalizeUserEvent(evt) {
  if (!evt) return null;
  const symbol = cleanSymbol(evt.symbol);
  return {
    id: `ua:${evt.id}`,
    kind: KINDS.YOUR_ALERT,
    symbol,
    ts: toTsMs(evt.triggered_ts ?? evt.triggered_at),
    headline: describeEvent(evt) || `${symbol} alert triggered`,
    detail: evt.explanation || "",
    severity: null,
    raw: evt,
  };
}

export function normalizeSuggestion(rec) {
  if (!rec) return null;
  const symbol = cleanSymbol(rec.symbol);
  return {
    id: `sg:${rec.id}`,
    kind: KINDS.SUGGESTION,
    symbol,
    ts: toTsMs(rec.created_at),
    headline: `Suggested alert for ${symbol}`,
    detail: rec.reason || "",
    severity: null,
    raw: rec,
  };
}

export function normalizeMarketAlert(alert) {
  if (!alert) return null;
  const symbol = cleanSymbol(alert.symbol || alert.product_id);
  if (!symbol) return null;
  const ts = toTsMs(alert.ts ?? alert.timestamp ?? alert.time);
  const typeKey = String(alert.type_key || alert.type || "signal").toLowerCase();
  const severity = String(alert.severity || alert.urgency || "info").toLowerCase();
  const text = String(alert.message || alert.title || "").trim();
  return {
    id: `mk:${alert.id || `${symbol}-${typeKey}-${ts || "x"}`}`,
    kind: KINDS.MARKET,
    symbol,
    ts,
    typeKey,
    headline: text || `${symbol} market signal`,
    detail: "",
    severity,
    raw: alert,
  };
}

function recencyBoost(ts, nowMs, maxAgeMs) {
  if (!Number.isFinite(ts)) return 0;
  const age = nowMs - ts;
  if (age < 0 || age > maxAgeMs) return 0;
  return RECENCY_MAX_BOOST * (1 - age / maxAgeMs);
}

/**
 * Merge, filter to personal relevance, dedupe, score, and rank.
 *
 * Market items with no personal tie (not held, not watched, no rule) are
 * excluded — ambient discovery is the Market Feed's job. This stream answers
 * "what matters to *me* right now".
 */
export function buildForYouStream({
  userEvents = [],
  recommendations = [],
  marketAlerts = [],
  isHolding = () => false,
  isWatchlisted = () => false,
  hasRuleFor = () => false,
  nowMs = Date.now(),
  limit = 30,
} = {}) {
  const reasonFor = (symbol) => {
    if (isHolding(symbol)) return REASONS.HOLDING;
    if (hasRuleFor(symbol)) return REASONS.RULE;
    if (isWatchlisted(symbol)) return REASONS.WATCHLIST;
    return REASONS.MARKET;
  };

  const out = [];

  for (const evt of userEvents) {
    const item = normalizeUserEvent(evt);
    if (!item) continue;
    if (Number.isFinite(item.ts) && nowMs - item.ts > USER_EVENT_MAX_AGE_MS) continue;
    item.reason = REASONS.RULE;
    item.score =
      KIND_BASE.your_alert +
      REASON_BOOST.your_rule +
      recencyBoost(item.ts, nowMs, USER_EVENT_MAX_AGE_MS);
    out.push(item);
  }

  for (const rec of recommendations) {
    const item = normalizeSuggestion(rec);
    if (!item) continue;
    item.reason = rec.basis === "portfolio" ? REASONS.HOLDING : REASONS.WATCHLIST;
    item.score = KIND_BASE.suggestion + REASON_BOOST[item.reason];
    out.push(item);
  }

  // Dedupe market alerts per (symbol, type), keeping the newest.
  const marketByKey = new Map();
  for (const alert of marketAlerts) {
    const item = normalizeMarketAlert(alert);
    if (!item) continue;
    if (Number.isFinite(item.ts) && nowMs - item.ts > MARKET_MAX_AGE_MS) continue;
    const reason = reasonFor(item.symbol);
    if (reason === REASONS.MARKET) continue; // no personal tie → Market Feed's job
    item.reason = reason;
    const key = `${item.symbol}|${item.typeKey}`;
    const existing = marketByKey.get(key);
    if (!existing || (item.ts || 0) > (existing.ts || 0)) marketByKey.set(key, item);
  }
  for (const item of marketByKey.values()) {
    item.score =
      KIND_BASE.market +
      REASON_BOOST[item.reason] +
      (SEVERITY_BOOST[item.severity] || 0) +
      recencyBoost(item.ts, nowMs, MARKET_MAX_AGE_MS);
    out.push(item);
  }

  // Anti-duplication: a market item is suppressed only when it is plausibly
  // the SAME occurrence the user's own alert already reported — same symbol,
  // price-move family, and close in time. A whale/volume/sentiment event on
  // that symbol is distinct intelligence and stays. Suggestions cannot
  // co-occur (a suggestion only exists while no rule covers the symbol).
  const firedTsBySymbol = new Map();
  for (const i of out) {
    if (i.kind !== KINDS.YOUR_ALERT) continue;
    const list = firedTsBySymbol.get(i.symbol) || [];
    list.push(i.ts);
    firedTsBySymbol.set(i.symbol, list);
  }
  const isSameOccurrence = (item) => {
    if (item.kind !== KINDS.MARKET) return false;
    if (!DEDUPE_PRICE_FAMILY.has(item.typeKey)) return false;
    const firedTimes = firedTsBySymbol.get(item.symbol);
    if (!firedTimes) return false;
    return firedTimes.some((firedTs) => {
      // Missing timestamps on either side: suppress conservatively — an
      // undatable price-move item next to a fired price alert reads as noise.
      if (!Number.isFinite(item.ts) || !Number.isFinite(firedTs)) return true;
      return Math.abs(item.ts - firedTs) <= DEDUPE_PROXIMITY_MS;
    });
  };
  const deduped = out.filter((i) => !isSameOccurrence(i));

  deduped.sort((a, b) => b.score - a.score || (b.ts || 0) - (a.ts || 0));
  return deduped.slice(0, Math.max(1, limit));
}

export const REASON_LABELS = {
  holding: "In your portfolio",
  your_rule: "You track this",
  watchlist: "On your watchlist",
};
