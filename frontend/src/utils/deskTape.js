import { normalizeWindowKey } from "./windows.js";

/**
 * Desk tape for INTELLIGENCE_LOG: turns the raw anomaly log into a
 * cycle-confluent read.
 *
 * 1. Contradictions: the same symbol never shows an up and a down signal
 *    within CONFLICT_WINDOW_MS; the higher-severity (then newer) one wins.
 * 2. Noise: a 1m move under NOISE_PCT_1M is dropped unless volume expanded
 *    or it is a STEALTH accumulation/distribution read.
 * 3. Context: each row is joined to its /api/macro-cycle-scan coin row and
 *    the watchlist/held sets to produce badges and confluence calls.
 * 4. Filters: Confluence & Desk (default), Watchlist, Raw Tape.
 */

export const CONFLICT_WINDOW_MS = 60_000;
export const NOISE_PCT_1M = 1.0;
export const VOLUME_EXPANSION_PCT = 50;
export const STEALTH_SURGE_VOL_PCT = 100;
export const DESK_FALLBACK_LIMIT = 12;

export const TAPE_FILTERS = [
  { key: "desk", label: "Confluence & Desk" },
  { key: "watchlist", label: "Watchlist" },
  { key: "raw", label: "Raw Tape" },
];

const BULLISH = new Set(["MOONSHOT", "BREAKOUT", "IMPULSE", "FOMO"]);
const BEARISH = new Set(["CRATER", "DUMP", "BREAKDOWN", "FEAR"]);
const FLOW = new Set(["STEALTH", "VOLUME", "WHALE"]);
const SEVERITY_RANK = { critical: 4, high: 3, warning: 2, medium: 2, info: 1, low: 1 };

const finite = (value) => {
  if (typeof value !== "number" && (typeof value !== "string" || !value.trim())) return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
};

export const baseSymbol = (value) =>
  String(value || "").trim().toUpperCase().replace(/[-/](USD|USDC|USDT|PERP)$/, "");

export const severityRank = (log) =>
  SEVERITY_RANK[String(log?.severity || "").toLowerCase()] ?? 0;

export function signalDirection(log, label) {
  const dir = String(log?.direction || "").toLowerCase();
  if (dir === "up" || dir === "down") return dir;
  if (dir === "flat") return null;
  if (BULLISH.has(label)) return "up";
  if (BEARISH.has(label)) return "down";
  const text = String(log?.body || "").toLowerCase();
  if (text.includes("distribut")) return "down";
  if (text.includes("accumul")) return "up";
  const pct = finite(log?.pct);
  if (pct) return pct > 0 ? "up" : "down";
  return null;
}

const volumePct = (log) => finite(log?.vol_change_pct);

const isOneMinute = (log) =>
  normalizeWindowKey(log?.window, { type: log?.type }) === "1m";

const eventTime = (log) => finite(Object.hasOwn(log, "eventTs") ? log.eventTs : log.ts);
const compareEntries = (a, b) => b.rank - a.rank || (eventTime(b.log) ?? 0) - (eventTime(a.log) ?? 0);

export function isTrivialNoise(log, label) {
  if (label === "STEALTH" || !isOneMinute(log)) return false;
  const pct = finite(log?.pct);
  if (pct === null || Math.abs(pct) >= NOISE_PCT_1M) return false;
  return !((volumePct(log) ?? 0) >= VOLUME_EXPANSION_PCT);
}

/** Drops the weaker side of every same-symbol up/down pair inside the window. */
export function dropContradictions(entries, windowMs = CONFLICT_WINDOW_MS) {
  const ranked = [...entries].sort(compareEntries);
  const kept = [];
  const keep = new Set();
  for (const entry of ranked) {
    const symbol = baseSymbol(entry.log.symbol);
    const ts = eventTime(entry.log);
    const conflict = entry.direction && symbol && ts !== null && kept.some((k) =>
      baseSymbol(k.log.symbol) === symbol
      && k.direction
      && k.direction !== entry.direction
      && eventTime(k.log) !== null
      && Math.abs(eventTime(k.log) - ts) <= windowMs
    );
    if (conflict) continue;
    kept.push(entry);
    keep.add(entry);
  }
  return entries.filter((entry) => keep.has(entry));
}

/** symbol -> coin row from both `coins` and every `buckets` list of the scan. */
export function buildCycleIndex(scan) {
  const index = new Map();
  if (!scan || typeof scan !== "object") return index;
  const add = (row) => {
    const symbol = baseSymbol(row?.symbol || row?.product_id);
    if (symbol && row?.available !== false && !index.has(symbol)) index.set(symbol, row);
  };
  (Array.isArray(scan.coins) ? scan.coins : []).forEach(add);
  Object.values(scan.buckets || {}).forEach((rows) => {
    if (Array.isArray(rows)) rows.forEach(add);
  });
  return index;
}

export function cycleContext(row, price) {
  const flags = { deepAccum: false, rolloverBox: false, breakout: false };
  const badges = [];
  if (!row) return { flags, badges };
  const bucket = row.bucket;
  if (bucket === "deep_accumulation_exhaustion") {
    flags.deepAccum = true;
    const streak = finite(row.monthly_bearish_streak);
    badges.push({ key: "deep", label: streak ? `DEEP ACCUM · ${streak}m` : "DEEP ACCUM", tone: "accum" });
  }
  const box = row.rollover_target_box || {};
  const low = finite(box.low);
  const high = finite(box.high);
  const px = finite(price) ?? finite(row.price);
  const inBox = low !== null && high !== null && px !== null && low < high && px >= low && px <= high;
  if (inBox) {
    flags.rolloverBox = true;
    badges.push({ key: "rollover", label: "ROLLOVER BOX", tone: "risk" });
  }
  if (bucket === "low_confirmation_breakout" || row.breaking_confirmation_pivot === true) {
    flags.breakout = true;
    badges.push({ key: "pivot", label: "PIVOT BREAK", tone: "gain" });
    if (row.above_50w_sma === true) badges.push({ key: "50w", label: "ABOVE 50W", tone: "gain" });
  }
  if (bucket === "growth_expansion_ride") badges.push({ key: "growth", label: "GROWTH", tone: "gain" });
  return { flags, badges };
}

function confluenceCall(flags, label, direction) {
  if (flags.deepAccum && direction === "up" && (BULLISH.has(label) || FLOW.has(label) || label === "MOVE")) {
    return {
      label: FLOW.has(label) ? "ACCUMULATION BID" : "EXHAUSTION BREAKOUT",
      tone: "gain",
      detail: "on a deep-accumulation coin",
    };
  }
  if (flags.rolloverBox && direction === "down") {
    return { label: "ROLLOVER DISTRIBUTION", tone: "loss", detail: "inside the rollover box" };
  }
  return null;
}

/**
 * @param {Array} logs raw log rows (ingest order)
 * @param {(log) => {label: string}} classify the panel's chip classifier
 * @param {{scan?: object, watchSymbols?: string[], heldSymbols?: string[]}} context
 */
export function buildDeskTape(logs, classify, { scan = null, watchSymbols = [], heldSymbols = [] } = {}) {
  const index = buildCycleIndex(scan?.status === "ready" ? scan : null);
  const watch = new Set(watchSymbols.map(baseSymbol).filter(Boolean));
  const held = new Set(heldSymbols.map(baseSymbol).filter(Boolean));
  const stage = scan?.status === "ready" && scan.industry?.available === true
    ? finite(scan.industry.stage_number) : null;
  const stageNumber = [1, 2, 3, 4].includes(stage) ? stage : null;
  const entries = [];
  for (const log of Array.isArray(logs) ? logs : []) {
    const { label, chipTone } = classify(log);
    if (log?.symbol && isTrivialNoise(log, label)) continue;
    const direction = log?.symbol ? signalDirection(log, label) : null;
    entries.push({ log, label, chipTone, direction, rank: severityRank(log) });
  }
  return dropContradictions(entries).map((entry) => {
    const symbol = baseSymbol(entry.log.symbol);
    const { flags, badges } = cycleContext(index.get(symbol), entry.log.ref_price);
    const isHeld = held.has(symbol);
    const isWatch = watch.has(symbol);
    if (symbol && stageNumber) badges.push({ key: "stage", label: `STAGE ${stageNumber}`, tone: "stage" });
    if (isHeld) badges.push({ key: "held", label: "HELD", tone: "watch" });
    else if (isWatch) badges.push({ key: "watch", label: "WATCHLIST", tone: "watch" });
    const stealthSurge = entry.label === "STEALTH" && (volumePct(entry.log) ?? 0) >= STEALTH_SURGE_VOL_PCT;
    return {
      ...entry,
      badges,
      flags,
      watched: isHeld || isWatch,
      stealthSurge,
      call: confluenceCall(flags, entry.label, entry.direction),
    };
  });
}

export const scanIsReady = (scan) => scan?.status === "ready" && buildCycleIndex(scan).size > 0;

/** Applies a filter pill. `fallback` is true when desk shows top anomalies because the scan is not ready. */
export function filterTape(tape, filter, { scanReady = false } = {}) {
  if (filter === "raw") return { rows: tape, fallback: false };
  if (filter === "watchlist") return { rows: tape.filter((e) => e.watched), fallback: false };
  const desk = new Set(tape.filter((e) =>
    e.flags.deepAccum || e.flags.rolloverBox || e.flags.breakout || e.stealthSurge || e.watched
  ));
  if (scanReady) return { rows: tape.filter((e) => desk.has(e)), fallback: false };
  const top = new Set(
    tape
      .filter((e) => e.log.symbol)
      .sort(compareEntries)
      .slice(0, DESK_FALLBACK_LIMIT)
  );
  return { rows: tape.filter((e) => desk.has(e) || top.has(e)), fallback: true };
}
