import { useMemo, useState, useEffect, useCallback } from "react";
import { useData } from "../context/DataContext";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { getMarketPressure } from "../utils/marketPressure";
import { stripLeadingSymbol } from "../utils/alertText";
import { RowInfo, RowStar } from "./tables/RowActions.jsx";
import "../styles/alerts-tab.css";

const TYPE_LABEL = {
  moonshot: "MOONSHOT",
  crater: "CRATER",
  breakout: "BREAKOUT",
  dump: "DUMP",
  whale_move: "WHALE",
  stealth_move: "STEALTH",
  divergence: "DIVERGENCE",
  impulse_1m: "MOVE",
  impulse_3m: "MOVE",
  coin_fomo: "COIN FOMO",
  coin_breadth_thrust: "BREADTH THRUST",
  coin_breadth_failure: "BREADTH FAILURE",
  coin_reversal_up: "REVERSAL UP",
  coin_reversal_down: "REVERSAL DOWN",
  coin_fakeout: "FAKEOUT",
  coin_persistent_gainer: "PERSIST GAINER",
  coin_persistent_loser: "PERSIST LOSER",
  coin_volatility_expansion: "VOL EXPANSION",
  coin_liquidity_shock: "LIQ SHOCK",
  coin_trend_break_up: "TREND BREAK UP",
  coin_trend_break_down: "TREND BREAK DOWN",
  coin_squeeze_break: "SQUEEZE BREAK",
  coin_exhaustion_top: "EXHAUSTION TOP",
  coin_exhaustion_bottom: "EXHAUSTION BOTTOM",
  social_spike_1h: "SOCIAL SPIKE",
  engagement_surge_1h: "ENGAGEMENT SURGE",
  social_divergence: "SOCIAL DIVERGENCE",
  social_pulse: "SOCIAL PULSE",
  listing: "LISTING",
  delisting: "DELISTING",
  unlock: "UNLOCK",
  upgrade: "UPGRADE",
  hack_or_exploit: "HACK / EXPLOIT",
  governance_vote: "GOVERNANCE",
  partnership: "PARTNERSHIP",
  news_positive: "NEWS POSITIVE",
  news_negative: "NEWS NEGATIVE",
  external_event: "EXTERNAL EVENT",
  news_confirmed_breakout: "NEWS CONFIRMED",
  social_confirmed_momentum: "SOCIAL CONFIRMED",
  event_confirmed_volume: "EVENT CONFIRMED",
  fomo: "FOMO",
  fomo_alert: "FOMO",
  fear: "FEAR",
  fear_alert: "FEAR",
};

const TYPE_HELP = {
  MOONSHOT: "Fast surge",
  CRATER: "Fast drop",
  BREAKOUT: "Trend shift",
  DUMP: "Strong sell pressure",
  WHALE: "Unusual volume spike",
  STEALTH: "Volume warming quietly",
  DIVERGENCE: "Price vs sentiment mismatch",
  "COIN FOMO": "Coin acceleration with market heat context",
  "BREADTH THRUST": "Coin strength confirmed by broad participation",
  "BREADTH FAILURE": "Coin weakness in weak market breadth",
  "REVERSAL UP": "Coin reversed from sell pressure to buy pressure",
  "REVERSAL DOWN": "Coin reversed from buy pressure to sell pressure",
  FAKEOUT: "Breakout trap rejected quickly",
  "PERSIST GAINER": "Coin stayed in sustained upside streak",
  "PERSIST LOSER": "Coin stayed in sustained downside streak",
  "VOL EXPANSION": "Coin volatility expanded vs recent baseline",
  "LIQ SHOCK": "Volume surged while price stayed muted",
  "TREND BREAK UP": "Fast/slow trend crossover with volume support",
  "TREND BREAK DOWN": "Fast/slow trend rollover with volume support",
  "SQUEEZE BREAK": "Compression regime broke into a sharp move",
  "EXHAUSTION TOP": "Upside run lost energy and flipped",
  "EXHAUSTION BOTTOM": "Downside run lost energy and snapped back",
  "SOCIAL SPIKE": "Social attention accelerated quickly",
  "ENGAGEMENT SURGE": "Participation expanded beyond baseline",
  "SOCIAL DIVERGENCE": "Social direction disagrees with tape direction",
  "SOCIAL PULSE": "Social timeline activity is live",
  LISTING: "Major listing catalyst detected",
  DELISTING: "Delisting risk or removal notice",
  UNLOCK: "Token unlock / vesting pressure",
  UPGRADE: "Protocol upgrade event",
  "HACK / EXPLOIT": "Security incident / exploit risk",
  GOVERNANCE: "Governance proposal or vote event",
  PARTNERSHIP: "Partnership or integration event",
  "NEWS POSITIVE": "Bullish external news catalyst",
  "NEWS NEGATIVE": "Bearish external news catalyst",
  "EXTERNAL EVENT": "External event without directional bias",
  "NEWS CONFIRMED": "News and tape action aligned",
  "SOCIAL CONFIRMED": "Social momentum and tape aligned",
  "EVENT CONFIRMED": "Event and volume expansion aligned",
  MOVE: "Short-term move",
  FOMO: "Chasing behavior",
  FEAR: "Risk-off behavior",
};

const ALERT_TABS = [
  { key: "ALL", label: "All" },
  { key: "MOONSHOT", label: "Moonshot" },
  { key: "BULLISH", label: "Bullish" },
  { key: "HEATING", label: "Heating Up" },
  { key: "WHALE", label: "Whale" },
  { key: "DUMP", label: "Dump" },
  { key: "BREAKOUT", label: "Breakout" },
  { key: "LIQ", label: "Liq Shock" },
];

const marketMoodKey = (a) => {
  const mood = String(a?.evidence?.mood || a?.direction || "").toLowerCase();
  return mood === "fear" ? "FEAR" : "FOMO";
};

const tabKeyForAlert = (a) => {
  const raw = String(a?.type_key || a?.type || "").toLowerCase();
  if (!raw) return "ALL";
  if (raw.includes("social_") || raw.includes("engagement") || raw.includes("sentiment")) return "SOCIAL";
  if (raw.includes("news_")) return "NEWS";
  if (raw.includes("listing") || raw.includes("delisting") || raw.includes("unlock") || raw.includes("upgrade") || raw.includes("governance") || raw.includes("partnership") || raw.includes("hack") || raw.includes("external_event")) return "EVENTS";
  if (raw.includes("funding") || raw.includes("open_interest") || raw.includes("liquidation") || raw.includes("derivative") || raw === "oi_spike") return "DERIV";
  if (raw.includes("moonshot")) return "MOONSHOT";
  if (raw.includes("breakout")) return "BREAKOUT";
  if (raw.includes("crater")) return "DUMP";
  if (raw.includes("whale")) return "WHALE";
  if (raw.includes("stealth")) return "WHALE";
  if (raw.includes("dump")) return "DUMP";
  if (raw.includes("coin_fomo")) return "COIN_FOMO";
  if (raw.includes("coin_breadth_thrust")) return "THRUST";
  if (raw.includes("coin_breadth_failure")) return "FAILURE";
  if (raw.includes("coin_reversal")) return "REVERSAL";
  if (raw.includes("coin_fakeout")) return "FAKEOUT";
  if (raw.includes("coin_persistent")) return "PERSIST";
  if (raw.includes("coin_volatility_expansion")) return "VOLX";
  if (raw.includes("coin_liquidity_shock")) return "LIQ";
  if (raw.includes("coin_trend_break")) return "TREND";
  if (raw.includes("coin_squeeze_break")) return "SQUEEZE";
  if (raw.includes("coin_exhaustion")) return "EXHAUST";
  if (raw.includes("fear") || raw.includes("fomo")) return marketMoodKey(a);
  if (raw.includes("divergence")) return "ALL";
  if (raw.includes("impulse")) return "IMPULSE";
  return "ALL";
};

const rawTypeKey = (a) => String(a?.type_key || a?.type || "").toLowerCase();

const HEATING_TYPE_TOKENS = [
  "coin_fomo",
  "coin_breadth_thrust",
  "coin_persistent_gainer",
  "coin_trend_break_up",
  "coin_squeeze_break",
  "breakout",
];

const BULLISH_TYPE_TOKENS = [
  ...HEATING_TYPE_TOKENS,
  "moonshot",
  "coin_reversal_up",
  "market_fomo_siren",
  "fomo",
];

const isHeatingAlert = (a) => {
  const raw = rawTypeKey(a);
  if (!raw) return false;
  if (HEATING_TYPE_TOKENS.some((token) => raw.includes(token))) return true;
  const heat = Number(a?.evidence?.heat ?? a?.evidence?.mood_index ?? null);
  const pct = Number(pickPct(a));
  return Number.isFinite(heat) && heat >= 65 && Number.isFinite(pct) && pct > 0;
};

const isBullishAlert = (a) => {
  const raw = rawTypeKey(a);
  if (!raw) return false;
  if (raw.includes("fear") || raw.includes("crater") || raw.includes("dump")) return false;
  if (BULLISH_TYPE_TOKENS.some((token) => raw.includes(token))) return true;
  const pct = Number(pickPct(a));
  return Number.isFinite(pct) && pct > 0.75;
};

const isWhaleAlert = (a) => {
  const raw = rawTypeKey(a);
  if (!raw) return false;
  return (
    raw.includes("whale") ||
    raw.includes("stealth") ||
    raw.includes("liquidity_shock")
  );
};

const isDumpAlert = (a) => {
  const raw = rawTypeKey(a);
  if (!raw) return false;
  if (raw.includes("dump") || raw.includes("crater") || raw.includes("fear")) return true;
  if (
    raw.includes("persistent_loser") ||
    raw.includes("trend_break_down") ||
    raw.includes("reversal_down") ||
    raw.includes("exhaustion_top") ||
    raw.includes("breadth_failure")
  ) {
    return true;
  }
  const pct = Number(pickPct(a));
  return Number.isFinite(pct) && pct < -0.75;
};

const alertMatchesTab = (a, tabKey) => {
  if (tabKey === "ALL") return true;
  if (tabKey === "HEATING") return isHeatingAlert(a);
  if (tabKey === "BULLISH") return isBullishAlert(a);
  if (tabKey === "WHALE") return isWhaleAlert(a);
  if (tabKey === "DUMP") return isDumpAlert(a);
  return tabKeyForAlert(a) === tabKey;
};

const SEV_RANK = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
const PRIORITY_WINDOW_MS = 7 * 60 * 1000;
const PRIORITY_HALF_LIFE_MS = 165 * 1000;
const PRIORITY_FRESH_MS = 2 * 60 * 1000;
const PRIORITY_FADING_MS = 3.5 * 60 * 1000;
const PRIORITY_SOFT_EXPIRY_MS = 9 * 60 * 1000;

const toUpperType = (alert) => {
  const k = String(alert?.type_key || alert?.type || "").toLowerCase();
  if (k.startsWith("coin_")) {
    return TYPE_LABEL[k] || k.toUpperCase();
  }
  if (k.includes("fear") || k.includes("fomo")) {
    return marketMoodKey(alert);
  }
  return TYPE_LABEL[k] || k.toUpperCase() || "ALERT";
};

const toEpochMs = (value) => {
  if (value == null || value === "") return null;

  if (value instanceof Date) {
    const ms = value.getTime();
    return Number.isFinite(ms) ? ms : null;
  }

  const normalizeNumericTs = (raw) => {
    if (!Number.isFinite(raw)) return null;
    const abs = Math.abs(raw);
    if (abs < 1e11) return Math.round(raw * 1000); // seconds
    if (abs < 1e14) return Math.round(raw); // milliseconds
    if (abs < 1e17) return Math.round(raw / 1000); // microseconds
    return Math.round(raw / 1e6); // nanoseconds-ish
  };

  if (typeof value === "number") {
    return normalizeNumericTs(value);
  }

  const raw = String(value).trim();
  if (!raw) return null;

  if (/^-?\d+(?:\.\d+)?$/.test(raw)) {
    return normalizeNumericTs(Number(raw));
  }

  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

const pickTsMs = (a) => {
  if (!a || typeof a !== "object") return null;
  const fields = [
    a.event_ts_ms,
    a.ts_ms,
    a.timestamp_ms,
    a.event_ts,
    a.ts,
    a.timestamp,
    a.created_at,
    a.createdAt,
    a.time,
    a.when,
    a.date,
  ];
  for (const value of fields) {
    const ms = toEpochMs(value);
    if (Number.isFinite(ms)) return ms;
  }
  return null;
};

const formatAlertTimestamp = (a) => {
  const tsMs = pickTsMs(a);
  if (!Number.isFinite(tsMs)) return null;
  const d = new Date(tsMs);
  if (!Number.isFinite(d.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
};

const ageLabel = (ms) => {
  if (!Number.isFinite(ms) || ms < 0) return "\u2014";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
};

const pickPct = (a) => {
  const ev = a?.evidence || {};
  const pct =
    ev.pct_1m ??
    ev.pct_3m ??
    ev.pct_5m ??
    ev.pct_15m ??
    ev.pct_1h ??
    a?.pct ??
    a?.magnitude ??
    null;
  const n = Number(pct);
  return Number.isFinite(n) ? n : null;
};

const pickVolPct = (a) => {
  const ev = a?.evidence || {};
  const v = ev.volume_change_1h_pct ?? ev.vol_change_1h_pct ?? ev.vol_pct ?? null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const shouldShowVolPct = (volPct) => Number.isFinite(volPct) && Math.abs(volPct) >= 0.01;

const toProductId = (a) => {
  let p = String(a?.product_id || a?.symbol || "").trim().toUpperCase();
  if (!p) return "";
  if (!p.includes("-")) p = `${p}-USD`;
  return p;
};

const alertSymbol = (a) =>
  String(a?.symbol || a?.product_id || "").toUpperCase().replace(/-USD$|-USDT$|-PERP$/i, "");

const sentimentSymbolForAlert = (a) => {
  const candidates = [
    a?.symbol,
    a?.product_id,
    a?.productId,
    a?.coin,
    a?.pair,
    a?.asset,
  ];
  for (const value of candidates) {
    const raw = String(value || "").trim().toUpperCase();
    if (!raw) continue;
    return raw.replace(/-USD$|-USDT$|-PERP$/i, "");
  }
  return "";
};

const pickWatchPrice = (a, latestBySymbol = {}) => {
  const ev = a?.evidence || {};
  const symbol = sentimentSymbolForAlert(a);
  const productId = toProductId(a);
  const latestCandidates = [
    latestBySymbol?.[symbol],
    latestBySymbol?.[productId],
  ].filter(Boolean);

  const candidates = [
    ev.price_now,
    ev.current_price,
    ev.price,
    a?.price,
    a?.current_price,
    ...latestCandidates.flatMap((row) => [
      row?.price,
      row?.current_price,
      row?.last_price,
      row?.close,
      typeof row === "number" ? row : null,
    ]),
  ];
  for (const value of candidates) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return null;
};

const moodFromHeat = (heat) => {
  if (heat >= 67) return { mood: "Bullish", tone: "bull", detail: "Buy pressure is leading right now." };
  if (heat <= 33) return { mood: "Bearish", tone: "bear", detail: "Sell pressure is leading right now." };
  return { mood: "Neutral", tone: "neutral", detail: "Pressure is balanced. Signals may chop." };
};

const confidenceFromStale = (priceStale, volStale) => {
  const p = Number.isFinite(priceStale) ? priceStale : null;
  const v = Number.isFinite(volStale) ? volStale : null;
  const worst = Math.max(p ?? 0, v ?? 0);
  if (p == null && v == null) return { label: "Unknown", tone: "unknown", hint: "Data freshness unavailable." };
  if (worst <= 6) return { label: "High", tone: "high", hint: `Data is ${worst.toFixed(1)}s old.` };
  if (worst <= 15) return { label: "Medium", tone: "med", hint: `Data is ${worst.toFixed(1)}s old.` };
  return { label: "Low", tone: "low", hint: `Data is ${worst.toFixed(1)}s old.` };
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const priorityBucketForAlert = (alert) => {
  const raw = rawTypeKey(alert);
  const pct = pickPct(alert);

  if (
    raw.includes("divergence") ||
    raw.includes("fakeout") ||
    raw.includes("exhaustion") ||
    raw.includes("liquidity_shock") ||
    raw.includes("stealth")
  ) {
    return "divergence";
  }

  if (
    raw.includes("dump") ||
    raw.includes("crater") ||
    raw.includes("fear") ||
    raw.includes("persistent_loser") ||
    raw.includes("trend_break_down") ||
    raw.includes("reversal_down") ||
    raw.includes("breadth_failure")
  ) {
    return "bearish";
  }

  if (
    raw.includes("moonshot") ||
    raw.includes("breakout") ||
    raw.includes("fomo") ||
    raw.includes("persistent_gainer") ||
    raw.includes("trend_break_up") ||
    raw.includes("breadth_thrust") ||
    raw.includes("reversal_up") ||
    raw.includes("squeeze_break")
  ) {
    return "bullish";
  }

  if (Number.isFinite(pct)) {
    if (pct > 0) return "bullish";
    if (pct < 0) return "bearish";
  }

  return null;
};

const priorityFamilyBonus = (alert, bucket) => {
  const raw = rawTypeKey(alert);
  if (bucket === "divergence") {
    if (raw.includes("divergence")) return 8;
    if (raw.includes("fakeout") || raw.includes("exhaustion")) return 7;
    if (raw.includes("liquidity_shock") || raw.includes("stealth")) return 6;
    return 4;
  }
  if (bucket === "bullish") {
    if (raw.includes("moonshot") || raw.includes("breakout")) return 8;
    if (raw.includes("trend_break_up") || raw.includes("breadth_thrust")) return 7;
    if (raw.includes("persistent_gainer") || raw.includes("fomo")) return 6;
    return 4;
  }
  if (bucket === "bearish") {
    if (raw.includes("crater") || raw.includes("dump")) return 8;
    if (raw.includes("trend_break_down") || raw.includes("breadth_failure")) return 7;
    if (raw.includes("persistent_loser") || raw.includes("fear")) return 6;
    return 4;
  }
  return 0;
};

const priorityContributionScore = (alert, nowMs) => {
  const tsMs = pickTsMs(alert);
  if (!Number.isFinite(tsMs)) return null;
  const ageMs = Math.max(0, nowMs - tsMs);
  if (ageMs > PRIORITY_SOFT_EXPIRY_MS) return null;

  const severity = String(alert?.severity || "info").toLowerCase();
  const severityWeight =
    {
      critical: 24,
      high: 18,
      medium: 12,
      low: 6,
      info: 3,
    }[severity] || 3;
  const pct = Math.abs(pickPct(alert) ?? 0);
  const volPct = Math.abs(pickVolPct(alert) ?? 0);
  const streak = Math.max(
    0,
    Number(alert?.evidence?.streak ?? alert?.extra?.streak ?? 0) || 0
  );
  const familyBonus = priorityFamilyBonus(alert, priorityBucketForAlert(alert));

  const baseScore =
    severityWeight +
    clamp(pct * 5, 0, 18) +
    clamp(volPct / 5, 0, 14) +
    clamp(streak, 0, 4) * 4 +
    familyBonus;

  const decay = Math.exp(-ageMs / PRIORITY_HALF_LIFE_MS);
  return {
    ageMs,
    tsMs,
    decay,
    weighted: baseScore * decay,
    isFresh: ageMs <= PRIORITY_FRESH_MS,
    baseScore,
    pct,
    volPct,
    streak,
  };
};

const priorityReasons = (entry) => {
  const reasons = [];
  if (entry.confirms > 1) {
    reasons.push(`${entry.confirms} confirms`);
  }
  if (entry.rankSummary) {
    reasons.push(entry.rankSummary);
  }
  if (entry.volumeAligned) {
    reasons.push("volume aligned");
  }
  if (entry.breadthSupport >= 0.62) {
    reasons.push("breadth aligned");
  } else if (entry.rankTrend === "slipping") {
    reasons.push("rank slipping");
  } else if (entry.noConfirmMs >= PRIORITY_FADING_MS) {
    reasons.push(`no confirm in ${(entry.noConfirmMs / 60000).toFixed(1)}m`);
  } else {
    reasons.push(`fresh ${ageLabel(Math.max(0, entry.nowMs - entry.lastTsMs))} ago`);
  }
  return reasons.slice(0, 3);
};

const priorityStateForEntry = (entry) => {
  if (entry.reversalRiskScore >= 14 || entry.bucket === "divergence") return "Reversal Risk";
  if (entry.noConfirmMs >= PRIORITY_FADING_MS || entry.score < 40) return "Fading";
  if (entry.score >= 85 && entry.freshConfirms >= 1 && entry.volumeAligned && !entry.divergenceFlag) return "Dominant";
  if (entry.score >= 70 && entry.rankPersistenceScore >= 10) return "Persistent";
  if (entry.score >= 55) return "Building";
  return "Fragile";
};

const priorityToneForBucket = (bucket) => {
  if (bucket === "bullish") return "bullish";
  if (bucket === "bearish") return "bearish";
  return "divergence";
};

const priorityStateTone = (label, bucket) => {
  if (label === "Reversal Risk" || label === "Fading") return "divergence";
  return priorityToneForBucket(bucket);
};

const toBoardSymbol = (row) => alertSymbol(row) || sentimentSymbolForAlert(row);

const buildRankMaps = (rows = [], fallbackKey = "rank") => {
  const map = new Map();
  rows.forEach((row, idx) => {
    const symbol = toBoardSymbol(row);
    if (!symbol || map.has(symbol)) return;
    const rankValue = Number(row?.rank ?? idx + 1);
    map.set(symbol, {
      rank: Number.isFinite(rankValue) ? rankValue : idx + 1,
      streak: Number(row?.trend_streak ?? row?.peak_count ?? 0) || 0,
      pct:
        Number(
          row?.price_change_percentage_1min ??
          row?.price_change_percentage_3min ??
          row?.pct_1m ??
          row?.pct_3m ??
          row?.pct ??
          null
        ) || null,
      key: fallbackKey,
    });
  });
  return map;
};

const computeRankPersistenceScore = (entry) => {
  let score = 0;
  if (Number.isFinite(entry.rank1m)) score += clamp(12 - entry.rank1m, 0, 10);
  if (Number.isFinite(entry.rank3m)) score += clamp(12 - entry.rank3m, 0, 10);
  if (Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    score += clamp(6 - (Math.abs(entry.rank1m - entry.rank3m) * 2), 0, 6);
  }
  return clamp(score, 0, 18);
};

const computeRankTrend = (entry) => {
  if (entry.bucket === "bullish" && Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    if (entry.rank1m + 1 < entry.rank3m) return "rising";
    if (Math.abs(entry.rank1m - entry.rank3m) <= 1) return "flat-strong";
    return "slipping";
  }
  if (entry.bucket === "bearish") {
    if (entry.noConfirmMs >= PRIORITY_FADING_MS) return "slipping";
    if (Number.isFinite(entry.rank3m) && entry.rank3m <= 3) return "flat-strong";
    return "rising";
  }
  return entry.noConfirmMs >= PRIORITY_FADING_MS ? "slipping" : "mixed";
};

const buildRankSummary = (entry) => {
  if (Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    const lo = Math.min(entry.rank1m, entry.rank3m);
    const hi = Math.max(entry.rank1m, entry.rank3m);
    return `rank held ${lo}-${hi}`;
  }
  if (Number.isFinite(entry.rank1m)) return `1m rank ${entry.rank1m}`;
  if (Number.isFinite(entry.rank3m)) return `${entry.bucket === "bearish" ? "3m loss" : "3m"} rank ${entry.rank3m}`;
  return "";
};

const deriveTapeState = (items, marketPressure) => {
  const activeLeaders = items.filter((item) => item.score >= 55).length;
  const weakening = items.filter((item) => ["Fading", "Reversal Risk"].includes(item.stateLabel)).length;
  const freshConfirms = items.reduce((sum, item) => sum + item.freshConfirms, 0);
  const breadth = Number(marketPressure?.components?.breadth ?? 0);

  let tapeState = "Choppy";
  if (weakening >= 2 && activeLeaders <= 1) tapeState = "Reversing";
  else if (activeLeaders >= 3 && freshConfirms >= 3 && breadth >= 0.56) tapeState = "Expanding";
  else if (activeLeaders <= 2 && items.some((item) => item.score >= 70)) tapeState = "Concentrated";
  else if (weakening >= 1 && freshConfirms < 2) tapeState = "Cooling";

  return {
    tapeState,
    freshConfirms,
    activeLeaders,
    weakening,
  };
};

const filterAlertRows = (rows, { coinFilter = "ALL", typeTab = "ALL", sev = "ALL" }) => {
  let out = Array.isArray(rows) ? rows : [];
  if (coinFilter !== "ALL") {
    out = out.filter((a) => alertSymbol(a) === coinFilter);
  }
  if (typeTab !== "ALL") {
    out = out.filter((a) => alertMatchesTab(a, typeTab));
  }
  if (sev !== "ALL") {
    out = out.filter((a) => String(a?.severity || "info").toUpperCase() === sev);
  }
  return out;
};

const sortAlertRows = (rows, { sort = "IMPORTANCE", feed = "ACTIVE" }) => {
  const out = Array.isArray(rows) ? [...rows] : [];
  if (sort === "URGENCY") {
    return out.sort((a, b) =>
      (SEV_RANK[String(b?.severity || "info").toLowerCase()] || 0) -
      (SEV_RANK[String(a?.severity || "info").toLowerCase()] || 0)
    );
  }
  if (sort === "MAGNITUDE") {
    return out.sort((a, b) => Math.abs(pickPct(b) ?? 0) - Math.abs(pickPct(a) ?? 0));
  }
  if (sort === "TIME") {
    return out.sort((a, b) => (pickTsMs(b) || 0) - (pickTsMs(a) || 0));
  }
  if (feed === "ACTIVE") return out;
  return out.sort((a, b) => {
    const sb = SEV_RANK[String(b?.severity || "info").toLowerCase()] || 0;
    const sa = SEV_RANK[String(a?.severity || "info").toLowerCase()] || 0;
    if (sb !== sa) return sb - sa;
    return (pickTsMs(b) || 0) - (pickTsMs(a) || 0);
  });
};

function PriorityStrip({ items = [], nowMs, onOpenCoinSentiment = null, marketPressure = null }) {
  const summary = deriveTapeState(items, marketPressure);

  return (
    <section className="bh-priority-strip" aria-label="Hot right now">
      <div className="bh-priority-strip__head">
        <div>
          <div className="bh-priority-strip__title">Hot Right Now</div>
          <div className="bh-priority-strip__sub">Live shortlist</div>
        </div>
        <div className="bh-priority-strip__meta">7m model</div>
      </div>

      <div className="bh-priority-strip__stats">
        <span>Tape {summary.tapeState}</span>
        <span>Fresh {summary.freshConfirms}</span>
        <span>Leaders {summary.activeLeaders}</span>
        <span>Weakening {summary.weakening}</span>
      </div>

      {!items.length ? (
        <div className="bh-priority-empty">
          <div>No dominant live setup right now.</div>
        </div>
      ) : (
        <div className="bh-priority-rows">
          {items.map((item) => {
            const reasons = priorityReasons({ ...item, nowMs });
            return (
              <button
                key={`${item.bucket}:${item.symbol}`}
                type="button"
                className="bh-priority-row"
                data-tone={priorityStateTone(item.stateLabel, item.bucket)}
                onClick={() => onOpenCoinSentiment?.(item.symbol, { source: "priority_strip", symbol: item.symbol })}
              >
                <div className="bh-priority-row__top">
                  <div className="bh-priority-row__title">
                    <span className="bh-priority-row__symbol">{item.symbol}</span>
                    <span className="bh-priority-row__sep">·</span>
                    <span className="bh-priority-row__label">{item.stateLabel}</span>
                  </div>
                  <div className="bh-priority-row__score">{item.score}</div>
                </div>
                <div className="bh-priority-row__summary">
                  {reasons.join(" · ")}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

function MarketMoodCard({ meta, variant = "full" }) {
  const compact = variant === "compact";
  const micro = variant === "micro";
  const mp = getMarketPressure({ market_pressure: meta?.market_pressure });
  const heat = Number(mp.index ?? 50);

  const stale = meta?.stale_seconds || {};
  const priceStale = Number(stale?.price);
  const volStale = Number(stale?.volume);

  const { mood, tone, detail } = moodFromHeat(heat);
  const confidence = confidenceFromStale(priceStale, volStale);

  if (micro) {
    return (
      <div className="bh-pressure-card bh-pressure-card--micro" data-tone={tone}>
        <div className="bh-pressure-micro-top">
          <span className="bh-pressure-micro-mood">{mood}</span>
        </div>
        <div className="bh-pressure-track bh-pressure-track--micro" aria-label="Market mood gauge">
          <div className="bh-pressure-fill" style={{ width: `${heat}%` }} />
        </div>
        <div className="bh-pressure-micro-foot">
          <span>{heat.toFixed(0)} / 100</span>
          <span>{confidence.label}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bh-pressure-card ${compact ? "bh-pressure-card--compact" : ""}`}
      data-tone={tone}
    >
      <div className="bh-pressure-toprow">
        <div className="bh-pressure-title">
          <span className="bh-mood-dot" aria-hidden="true" />
          Market Mood
        </div>
        <div className="bh-pressure-label">{mood}</div>
      </div>

      <div className={`bh-pressure-sub ${compact ? "bh-pressure-sub--compact" : ""}`}>{detail}</div>

      <div className="bh-pressure-track" aria-label="Market mood gauge">
        <div className="bh-pressure-fill" style={{ width: `${heat}%` }} />
      </div>

      <div className="bh-pressure-row">
        <div className="bh-pressure-score">{heat.toFixed(0)} / 100</div>
        <div className="bh-pressure-confidence" data-tone={confidence.tone}>
          Confidence: {confidence.label}
        </div>
      </div>

      <div className="bh-pressure-fresh">
        <span>Price: {Number.isFinite(priceStale) ? `${priceStale.toFixed(1)}s old` : "\u2014"}</span>
        <span>Volume: {Number.isFinite(volStale) ? `${volStale.toFixed(1)}s old` : "\u2014"}</span>
      </div>

      {!compact ? <div className="bh-pressure-hint">{confidence.hint}</div> : null}
    </div>
  );
}

function ProofFooter({ meta, activeCount, recentCount }) {
  const stale = meta?.stale_seconds || {};
  const priceStale = Number(stale?.price);
  const volStale = Number(stale?.volume);

  const healthy =
    Number.isFinite(priceStale) && priceStale < 30 &&
    Number.isFinite(volStale) && volStale < 60;

  return (
    <div className="bh-proof-footer">
      <div className="bh-proof-item">
        <span className="bh-proof-key">Signals healthy</span>
        <span className={`bh-proof-val ${healthy ? "bh-proof--ok" : "bh-proof--warn"}`}>
          {healthy ? "Yes" : "Degraded"}
        </span>
      </div>
      <div className="bh-proof-item">
        <span className="bh-proof-key">Active</span>
        <span className="bh-proof-val">{activeCount}</span>
      </div>
      <div className="bh-proof-item">
        <span className="bh-proof-key">Recent</span>
        <span className="bh-proof-val">{recentCount}</span>
      </div>
      <div className="bh-proof-item">
        <span className="bh-proof-key">Data age</span>
        <span className="bh-proof-val">
          price {Number.isFinite(priceStale) ? `${priceStale.toFixed(0)}s` : "\u2014"},
          vol {Number.isFinite(volStale) ? `${volStale.toFixed(0)}s` : "\u2014"}
        </span>
      </div>
    </div>
  );
}

function SignalRow({
  a,
  nowMs,
  onOpenCoinSentiment = null,
  isWatchlisted = false,
  onToggleWatchlist = null,
}) {
  const type = toUpperType(a);
  const sev = String(a?.severity || "info").toLowerCase();
  const promotion = String(a?.promotion || "").toUpperCase();
  const sourceLabel = String(a?.source || "")
    .trim()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (s) => s.toUpperCase());
  const sym = String(a?.product_id || a?.symbol || "").toUpperCase().replace("-USD", "");
  const ts = pickTsMs(a);
  const absTs = formatAlertTimestamp(a);
  const age = ts ? ageLabel(nowMs - ts) : "\u2014";
  const windowLabel = String(a?.window || a?.evidence?.window || "").trim();

  // Build clean message without repeating coin name
  let rawMsg = String(a?.message || a?.title || TYPE_HELP[type] || "")
    .replace(/\s+/g, " ")
    .trim();
  // Strip leading "SYMBOL:" or "SYMBOL " patterns
  rawMsg = stripLeadingSymbol(rawMsg, sym).replace(new RegExp(`^${sym}[:\\s]+`, "i"), "");
  const detail = rawMsg || TYPE_HELP[type] || "Signal detected";

  const pct = pickPct(a);
  const volPct = pickVolPct(a);

  const pctText = pct == null ? "" : `${pct > 0 ? "+" : ""}${pct.toFixed(Math.abs(pct) < 5 ? 3 : 2)}%`;
  const volText = shouldShowVolPct(volPct) ? `Vol ${volPct > 0 ? "+" : ""}${volPct.toFixed(0)}%` : "";

  const url = a?.url || a?.trade_url || coinbaseSpotUrl({ product_id: toProductId(a), symbol: a?.symbol });
  const cls = tabKeyForAlert(a);
  const heating = isHeatingAlert(a);
  const bullish = isBullishAlert(a);
  const sentimentSymbol = sentimentSymbolForAlert(a) || sym;

  // Determine direction for color coding
  const direction = pct == null ? "neutral" : pct > 0 ? "up" : "down";
  const handleInfoClick = (event) => {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    if (!sentimentSymbol) return;
    if (typeof onOpenCoinSentiment === "function") {
      onOpenCoinSentiment(sentimentSymbol, { source: "alerts_center", alert: a });
    }
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent("openInfo", { detail: sentimentSymbol }));
    }
  };

  const handleToggleStar = () => {
    if (typeof onToggleWatchlist !== "function") return;
    onToggleWatchlist(a);
  };

  return (
    <div
      className="bh-signal-row"
      data-sev={sev}
      data-class={cls.toLowerCase()}
      data-direction={direction}
      role="button"
      tabIndex={0}
      onClick={() => url && window.open(url, "_blank", "noopener,noreferrer")}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          url && window.open(url, "_blank", "noopener,noreferrer");
        }
      }}
      title={TYPE_HELP[type] ? `${type}: ${TYPE_HELP[type]}` : type}
    >
      <div className="bh-signal-main">
        <div className="bh-signal-meta">
          <span className="bh-signal-type">{type}</span>
          {windowLabel ? <span className="bh-signal-window">{windowLabel}</span> : null}
          <span className="bh-signal-sev" data-sev={sev}>{String(a?.severity || "INFO").toUpperCase()}</span>
          {promotion ? <span className="bh-signal-promo" data-promo={promotion}>{promotion}</span> : null}
          {heating ? <span className="bh-signal-bias" data-bias="heating">HEATING</span> : null}
          {!heating && bullish ? <span className="bh-signal-bias" data-bias="bullish">BULLISH</span> : null}
          {sourceLabel ? <span className="bh-signal-source">{sourceLabel}</span> : null}
        </div>

        <div className="bh-signal-ticker">{sym || "\u2014"}</div>

        <div className="bh-signal-msg">{detail}</div>

        <div className="bh-signal-metrics">
          {pctText ? <span className="bh-metric" data-direction={direction}>{pctText}</span> : null}
          {volText ? <span className="bh-metric bh-metric--vol">{volText}</span> : null}
        </div>
      </div>

      <div className="bh-signal-row-right">
        <div className="bh-row-actions row-actions--stack">
          <RowStar starred={Boolean(isWatchlisted)} onToggleStar={handleToggleStar} />
          <RowInfo onInfoClick={() => handleInfoClick()} />
        </div>
        <div className="bh-alert-time">
          <div className="bh-alert-time-abs">{absTs || "\u2014"}</div>
          <div className="bh-alert-time-rel">{age}</div>
        </div>
      </div>
    </div>
  );
}

export default function AlertsTab({
  filterSymbol = null,
  compact = false,
  onOpenCoinSentiment = null,
  hideHeader = false,
  hideFoot = false,
  emptyCopy = null,
}) {
  const {
    activeAlerts = [],
    alertsRecent = [],
    alertsMeta = {},
    latestBySymbol = {},
    gainers_1m = [],
    gainers_3m = [],
    losers_3m = [],
    market_pressure = null,
  } = useData() || {};
  const { items: watchlistItems = [], has: watchHas, toggle: watchToggle } = useWatchlist();
  const forcedCoin = useMemo(() => {
    const raw = String(filterSymbol || "").toUpperCase().replace(/-USD$|-USDT$|-PERP$/i, "");
    return raw || null;
  }, [filterSymbol]);

  const [feed, setFeed] = useState("ACTIVE");
  const [typeTab, setTypeTab] = useState("ALL");
  const [sev, setSev] = useState("ALL");
  const [sort, setSort] = useState(() => "IMPORTANCE");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [showHelp, setShowHelp] = useState(false);
  // Default to the full market stream; symbol-specific filtering is user-driven.
  const [coinFilter, setCoinFilter] = useState(() => forcedCoin || "ALL");

  useEffect(() => {
    if (!forcedCoin) return;
    setCoinFilter(forcedCoin);
  }, [forcedCoin]);

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setSort(feed === "ACTIVE" ? "IMPORTANCE" : "TIME");
  }, [feed]);

  const fallbackForcedActive = useMemo(() => {
    if (!forcedCoin) return [];
    return (Array.isArray(activeAlerts) ? activeAlerts : []).filter((a) => alertSymbol(a) === forcedCoin);
  }, [activeAlerts, forcedCoin]);

  const fallbackForcedRecent = useMemo(() => {
    if (!forcedCoin) return [];
    return (Array.isArray(alertsRecent) ? alertsRecent : []).filter((a) => alertSymbol(a) === forcedCoin);
  }, [alertsRecent, forcedCoin]);

  const effectiveActiveAlerts = useMemo(() => {
    if (!forcedCoin) return Array.isArray(activeAlerts) ? activeAlerts : [];
    return fallbackForcedActive;
  }, [forcedCoin, activeAlerts, fallbackForcedActive]);

  const effectiveRecentAlerts = useMemo(() => {
    if (!forcedCoin) return Array.isArray(alertsRecent) ? alertsRecent : [];
    return fallbackForcedRecent;
  }, [forcedCoin, alertsRecent, fallbackForcedRecent]);

  const effectiveMeta = useMemo(() => alertsMeta || {}, [alertsMeta]);

  const source = feed === "ACTIVE" ? effectiveActiveAlerts : effectiveRecentAlerts;
  const effectiveCoinFilter = forcedCoin || coinFilter;

  // Build coin options from available alerts
  const coinOptions = useMemo(() => {
    if (forcedCoin) return [forcedCoin];
    const set = new Set(["ALL"]);
    for (const a of alertsRecent || []) {
      const s = alertSymbol(a);
      if (s) set.add(s);
    }
    for (const a of activeAlerts || []) {
      const s = alertSymbol(a);
      if (s) set.add(s);
    }
    return Array.from(set).sort();
  }, [forcedCoin, alertsRecent, activeAlerts]);

  const tabSeedRows = useMemo(() => {
    let out = Array.isArray(source) ? source : [];
    if (effectiveCoinFilter !== "ALL") {
      out = out.filter((a) => alertSymbol(a) === effectiveCoinFilter);
    }
    return out;
  }, [source, effectiveCoinFilter]);

  const tabCounts = useMemo(() => {
    const counts = new Map();
    for (const tab of ALERT_TABS) {
      counts.set(tab.key, 0);
    }
    counts.set("ALL", tabSeedRows.length);
    for (const a of tabSeedRows) {
      for (const tab of ALERT_TABS) {
        if (tab.key === "ALL") continue;
        if (!alertMatchesTab(a, tab.key)) continue;
        counts.set(tab.key, (counts.get(tab.key) || 0) + 1);
      }
    }
    return counts;
  }, [tabSeedRows]);

  const visibleTabs = ALERT_TABS;

  const rows = useMemo(
    () =>
      sortAlertRows(
        filterAlertRows(source, {
          coinFilter: effectiveCoinFilter,
          typeTab,
          sev,
        }),
        { sort, feed }
      ),
    [source, effectiveCoinFilter, typeTab, sev, sort, feed]
  );

  const compactRecentFallbackRows = useMemo(() => {
    return sortAlertRows(
      filterAlertRows(effectiveRecentAlerts, {
        coinFilter: effectiveCoinFilter,
        typeTab,
        sev,
      }),
      { sort: "TIME", feed: "RECENT" }
    );
  }, [effectiveRecentAlerts, effectiveCoinFilter, typeTab, sev]);

  const compactFallbackToRecent =
    compact && feed === "ACTIVE" && rows.length === 0 && compactRecentFallbackRows.length > 0;
  const rowsForRender = compactFallbackToRecent ? compactRecentFallbackRows : rows;
  const displayedRows = useMemo(
    () => rowsForRender.slice(0, compact ? 8 : 8),
    [rowsForRender, compact]
  );

  const watchlistAttentionRows = useMemo(() => {
    if (compact || forcedCoin) return [];
    const filtered = filterAlertRows(effectiveActiveAlerts, {
      coinFilter: effectiveCoinFilter,
      typeTab,
      sev,
    }).filter((alert) => watchHas(sentimentSymbolForAlert(alert)));
    return sortAlertRows(filtered, { sort, feed: "ACTIVE" }).slice(0, 4);
  }, [compact, forcedCoin, effectiveActiveAlerts, effectiveCoinFilter, typeTab, sev, sort, watchHas]);

  const allAlertsTitle = forcedCoin ? `${forcedCoin} Signals` : "All Alerts";

  const toggleAlertWatch = useCallback(
    (alert) => {
      const symbol = sentimentSymbolForAlert(alert);
      const price = pickWatchPrice(alert, latestBySymbol);
      if (!symbol || !Number.isFinite(price) || price <= 0) return;
      watchToggle({ symbol, price });
    },
    [watchToggle, latestBySymbol]
  );

  const boardRanks = useMemo(() => ({
    oneMin: buildRankMaps(gainers_1m, "1m"),
    gain3m: buildRankMaps(gainers_3m, "3m"),
    loss3m: buildRankMaps(losers_3m, "3m-loss"),
  }), [gainers_1m, gainers_3m, losers_3m]);

  const boardContext = useMemo(() => {
    if (!forcedCoin) return null;
    const oneMinBoard = boardRanks.oneMin.get(forcedCoin);
    const gain3Board = boardRanks.gain3m.get(forcedCoin);
    const loss3Board = boardRanks.loss3m.get(forcedCoin);
    const parts = [];
    if (oneMinBoard?.rank) parts.push(`1m rank #${oneMinBoard.rank}`);
    if (gain3Board?.rank) parts.push(`3m rank #${gain3Board.rank}`);
    if (loss3Board?.rank) parts.push(`3m loss rank #${loss3Board.rank}`);
    return parts.length ? parts.join(" · ") : null;
  }, [forcedCoin, boardRanks]);

  const latestRecentTsMs = useMemo(() => {
    for (const row of compactRecentFallbackRows) {
      const ts = pickTsMs(row);
      if (Number.isFinite(ts)) return ts;
    }
    return null;
  }, [compactRecentFallbackRows]);

  const resolvedEmptyCopy = useMemo(() => {
    if (emptyCopy) return emptyCopy;
    if (!forcedCoin) {
      return feed === "ACTIVE" ? "No active signals right now." : "No recent signals yet.";
    }
    if (boardContext) {
      return `No live coin signal right now. ${forcedCoin} is still on the board: ${boardContext}.`;
    }
    if (Number.isFinite(latestRecentTsMs)) {
      return `No live coin signal right now. Last ${forcedCoin} signal was ${ageLabel(Math.max(0, nowMs - latestRecentTsMs))} ago.`;
    }
    return `No live coin signal for ${forcedCoin} yet. Board position alone does not always produce an alert.`;
  }, [emptyCopy, forcedCoin, feed, boardContext, latestRecentTsMs, nowMs]);

  const marketPressure = useMemo(
    () => getMarketPressure({ market_pressure: market_pressure ?? effectiveMeta?.market_pressure }),
    [market_pressure, effectiveMeta]
  );

  const priorityItems = useMemo(() => {
    if (compact) return [];

    let candidates = Array.isArray(effectiveRecentAlerts) ? effectiveRecentAlerts : [];
    if (effectiveCoinFilter !== "ALL") {
      candidates = candidates.filter((a) => alertSymbol(a) === effectiveCoinFilter);
    }
    if (typeTab !== "ALL") {
      candidates = candidates.filter((a) => alertMatchesTab(a, typeTab));
    }
    if (sev !== "ALL") {
      candidates = candidates.filter((a) => String(a?.severity || "info").toUpperCase() === sev);
    }

    const grouped = new Map();
    for (const alert of candidates) {
      const symbol = sentimentSymbolForAlert(alert);
      const bucket = priorityBucketForAlert(alert);
      if (!symbol || !bucket) continue;

      const contribution = priorityContributionScore(alert, nowMs);
      if (!contribution) continue;

      const key = `${bucket}:${symbol}`;
      const existing = grouped.get(key) || {
        bucket,
        symbol,
        scoreRaw: 0,
        confirms: 0,
        freshConfirms: 0,
        lastTsMs: 0,
        maxStreak: 0,
        topPct: 0,
        netPctSign: 1,
        topVolPct: 0,
        topVolSign: 1,
        rank1m: null,
        rank3m: null,
        breadthSupport: 0,
        divergenceFlag: bucket === "divergence",
        watchlistRelevant: watchHas(symbol),
      };

      existing.scoreRaw += contribution.weighted;
      existing.confirms += 1;
      if (contribution.isFresh) existing.freshConfirms += 1;
      if (contribution.tsMs > existing.lastTsMs) existing.lastTsMs = contribution.tsMs;
      if (contribution.streak > existing.maxStreak) existing.maxStreak = contribution.streak;

      const pctSigned = pickPct(alert);
      if (Number.isFinite(pctSigned) && Math.abs(pctSigned) >= existing.topPct) {
        existing.topPct = Math.abs(pctSigned);
        existing.netPctSign = pctSigned >= 0 ? 1 : -1;
      }

      const volSigned = pickVolPct(alert);
      if (Number.isFinite(volSigned) && Math.abs(volSigned) >= existing.topVolPct) {
        existing.topVolPct = Math.abs(volSigned);
        existing.topVolSign = volSigned >= 0 ? 1 : -1;
      }

      const oneMinBoard = boardRanks.oneMin.get(symbol);
      const gain3Board = boardRanks.gain3m.get(symbol);
      const loss3Board = boardRanks.loss3m.get(symbol);
      if (oneMinBoard && Number.isFinite(oneMinBoard.rank)) existing.rank1m = oneMinBoard.rank;
      if (bucket === "bearish") {
        if (loss3Board && Number.isFinite(loss3Board.rank)) existing.rank3m = loss3Board.rank;
      } else if (gain3Board && Number.isFinite(gain3Board.rank)) {
        existing.rank3m = gain3Board.rank;
      }

      const ev = alert?.evidence || {};
      const breadthUp = Number(ev.breadth_up ?? marketPressure?.breadth_up ?? marketPressure?.components?.breadth ?? 0) || 0;
      const breadthDown = Number(ev.breadth_down ?? marketPressure?.breadth_down ?? 0) || 0;
      const breadthSupport =
        bucket === "bullish" ? breadthUp :
        bucket === "bearish" ? breadthDown :
        Math.max(Math.abs(breadthUp - breadthDown), marketPressure?.components?.breadth ?? 0);
      existing.breadthSupport = Math.max(existing.breadthSupport, clamp(breadthSupport, 0, 1));

      grouped.set(key, existing);
    }

    const ranked = Array.from(grouped.values()).map((entry) => {
      const confirmationBonus = Math.min(18, Math.max(0, entry.confirms - 1) * 6);
      const freshBonus = entry.freshConfirms > 0 ? Math.min(10, entry.freshConfirms * 4) : 0;
      entry.noConfirmMs = Math.max(0, nowMs - entry.lastTsMs);
      entry.rankPersistenceScore = computeRankPersistenceScore(entry);
      entry.rankTrend = computeRankTrend(entry);
      entry.rankSummary = buildRankSummary(entry);
      entry.volumeAligned = entry.topVolSign > 0 && entry.topVolPct >= 10;
      entry.reversalRiskScore =
        (entry.bucket === "divergence" ? 10 : 0) +
        (entry.rankTrend === "slipping" ? 4 : 0) +
        (entry.noConfirmMs >= PRIORITY_FADING_MS ? 4 : 0);
      const stalePenalty = entry.noConfirmMs > PRIORITY_FADING_MS ? 12 : 0;
      const volumeBonus = entry.volumeAligned ? 10 : 0;
      const breadthBonus = Math.round(entry.breadthSupport * 10);
      const rankBonus = entry.rankPersistenceScore;
      const watchlistBonus = entry.watchlistRelevant ? 5 : 0;
      const score = clamp(
        Math.round(
          entry.scoreRaw +
          confirmationBonus +
          freshBonus +
          rankBonus +
          volumeBonus +
          breadthBonus +
          watchlistBonus -
          stalePenalty
        ),
        1,
        99
      );
      const stateLabel = priorityStateForEntry({ ...entry, score });
      return { ...entry, score, stateLabel };
    });

    const ordered = ["Dominant", "Persistent", "Building", "Reversal Risk", "Fading"]
      .flatMap((label) =>
        ranked
          .filter((item) => item.stateLabel === label)
          .sort((a, b) => b.score - a.score || b.lastTsMs - a.lastTsMs)
      );

    const deduped = [];
    const seenSymbols = new Set();
    for (const item of ordered) {
      if (seenSymbols.has(item.symbol)) continue;
      seenSymbols.add(item.symbol);
      deduped.push(item);
      if (deduped.length >= 3) break;
    }

    return deduped;
  }, [
    compact,
    effectiveRecentAlerts,
    effectiveCoinFilter,
    typeTab,
    sev,
    nowMs,
    boardRanks,
    marketPressure,
    watchHas,
  ]);

  return (
    <div className={`bh-alerts-tab ${compact ? "bh-alerts-tab--compact" : ""}`}>
      <div className="bh-alerts-layout">
        <div className="bh-alerts-controls">
          {!hideHeader ? (
            <div className="bh-alerts-feed-head">
              <div className="bh-alerts-feed-title">{allAlertsTitle}</div>

              {!compact ? (
                <div className="bh-alerts-toggle" role="tablist" aria-label="Signals feed">
                  <button
                    className={`bh-toggle-btn ${feed === "ACTIVE" ? "active" : ""}`}
                    onClick={() => setFeed("ACTIVE")}
                    type="button"
                  >
                    Active
                  </button>
                  <button
                    className={`bh-toggle-btn ${feed === "RECENT" ? "active" : ""}`}
                    onClick={() => setFeed("RECENT")}
                    type="button"
                  >
                    Recent
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          {!compact ? (
            <div className="bh-alerts-type-tabs" role="tablist" aria-label="Signal classes">
              {visibleTabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={`bh-type-tab ${typeTab === tab.key ? "active" : ""}`}
                  onClick={() => setTypeTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          ) : null}

          {!compact ? (
            <div className="bh-alerts-tab-controls">
              <div className="bh-control">
                <div className="bh-control-label">Urgency</div>
                <select className="bh-control-select" value={sev} onChange={(e) => setSev(e.target.value)}>
                  {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="bh-control">
                <div className="bh-control-label">Order</div>
                <select className="bh-control-select" value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="IMPORTANCE">Most Important</option>
                  <option value="TIME">Newest</option>
                  <option value="URGENCY">Urgency</option>
                  <option value="MAGNITUDE">Biggest Move</option>
                </select>
              </div>

              {!forcedCoin ? (
                <div className="bh-control">
                  <div className="bh-control-label">Coin</div>
                  <select className="bh-control-select" value={coinFilter} onChange={(e) => setCoinFilter(e.target.value)}>
                    {coinOptions.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              ) : null}

              <div className="bh-control bh-control--mood">
                <div className="bh-control-label">Market Mood</div>
                <MarketMoodCard meta={effectiveMeta} variant="micro" />
              </div>
            </div>
          ) : null}

          {!compact ? (
            <div className="bh-alerts-help-bar">
              <button
                type="button"
                className="bh-help-toggle"
                onClick={() => setShowHelp((v) => !v)}
                aria-expanded={showHelp}
              >
                {showHelp ? "Hide guide" : "Show guide"}
              </button>
            </div>
          ) : null}

          {!compact && showHelp ? (
            <div className="bh-alerts-help">
              <div className="bh-alerts-help-title">What you are looking at</div>
              <div className="bh-alerts-help-body">
                <div className="bh-alerts-help-line">
                  <strong>Active</strong> shows the strongest signal per coin and signal type.
                </div>
                <div className="bh-alerts-help-line">
                  <strong>Recent</strong> shows everything detected, newest first.
                </div>
              </div>

              <div className="bh-alerts-glossary" role="list" aria-label="Signal glossary">
                {Object.entries(TYPE_HELP).map(([k, v]) => (
                  <div key={k} className="bh-gloss-item" role="listitem">
                    <span className="bh-gloss-key">{k}</span>
                    <span className="bh-gloss-val">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="bh-alerts-feed">
          {!compact && !forcedCoin ? (
            <PriorityStrip
              items={priorityItems}
              nowMs={nowMs}
              onOpenCoinSentiment={onOpenCoinSentiment}
              marketPressure={marketPressure}
            />
          ) : null}
          {!compact && !forcedCoin ? (
            <section className="bh-alerts-feed-section bh-alerts-feed-section--watchlist" aria-label="Watchlist attention">
              <div className="bh-alerts-feed-section__head">
                <div className="bh-alerts-feed-section__title">
                  <span className="bh-alerts-feed-section__marker" aria-hidden="true">☆</span>
                  <span>Watchlist Attention</span>
                </div>
                <div className="bh-alerts-feed-section__meta">
                  {watchlistItems.length ? `${watchlistAttentionRows.length} live` : "watchlist"}
                </div>
              </div>
              {watchlistAttentionRows.length === 0 ? (
                <div className="bh-signal-empty bh-signal-empty--compact">
                  No active watchlist alerts right now
                </div>
              ) : (
                <div className="bh-signal-list bh-signal-list--watchlist" role="list">
                  {watchlistAttentionRows.map((a) => (
                    <SignalRow
                      key={`watch:${a.id || `${a.symbol}-${a.type_key}-${pickTsMs(a)}`}`}
                      a={a}
                      nowMs={nowMs}
                      onOpenCoinSentiment={onOpenCoinSentiment}
                      isWatchlisted={watchHas(sentimentSymbolForAlert(a))}
                      onToggleWatchlist={toggleAlertWatch}
                    />
                  ))}
                </div>
              )}
            </section>
          ) : null}
          {compactFallbackToRecent ? (
            <div className="bh-alerts-inline-note">
              No active signals right now. Showing recent matches.
            </div>
          ) : null}
          {!compact && !forcedCoin ? (
            <div className="bh-alerts-feed-section__head bh-alerts-feed-section__head--all">
              <div className="bh-alerts-feed-section__title">All Alerts</div>
              <div className="bh-alerts-feed-section__meta">{displayedRows.length} shown</div>
            </div>
          ) : null}
          <div className="bh-signal-list" role="list">
            {displayedRows.length === 0 ? (
              <div className="bh-signal-empty">
                {resolvedEmptyCopy}
              </div>
            ) : (
              displayedRows.map((a) => (
                <SignalRow
                  key={a.id || `${a.symbol}-${a.type_key}-${pickTsMs(a)}`}
                  a={a}
                  nowMs={nowMs}
                  onOpenCoinSentiment={onOpenCoinSentiment}
                  isWatchlisted={watchHas(sentimentSymbolForAlert(a))}
                  onToggleWatchlist={toggleAlertWatch}
                />
              ))
            )}
          </div>

          {!hideFoot ? (
            <div className="bh-signal-foot">
              Click any signal to open the source link or Coinbase Advanced Trade.
            </div>
          ) : null}

          {!compact ? (
            <ProofFooter
              meta={effectiveMeta}
              activeCount={effectiveActiveAlerts.length}
              recentCount={effectiveRecentAlerts.length}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
