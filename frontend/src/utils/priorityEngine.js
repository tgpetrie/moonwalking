import { isCoinEventActive } from "./coinHistoryCache.js";

export const PRIORITY_HALF_LIFE_MS = 165 * 1000;
export const PRIORITY_FRESH_MS = 2 * 60 * 1000;
export const PRIORITY_FADING_MS = 3.5 * 60 * 1000;
export const PRIORITY_SOFT_EXPIRY_MS = 9 * 60 * 1000;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const rawTypeKey = (alert) =>
  String(alert?.type_key || alert?.type || "").toLowerCase();

const toEpochMs = (value) => {
  if (value == null || value === "") return null;
  if (typeof value === "number" && Number.isFinite(value)) {
    if (Math.abs(value) < 1e11) return Math.round(value * 1000);
    if (Math.abs(value) < 1e14) return Math.round(value);
    return Math.round(value / 1000);
  }
  const raw = String(value).trim();
  if (!raw) return null;
  if (/^-?\d+(?:\.\d+)?$/.test(raw)) return toEpochMs(Number(raw));
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

const pickTsMs = (alert) => {
  const fields = [
    alert?.event_ts_ms,
    alert?.ts_ms,
    alert?.timestamp_ms,
    alert?.event_ts,
    alert?.ts,
    alert?.timestamp,
    alert?.created_at,
    alert?.createdAt,
    alert?.time,
    alert?.when,
    alert?.date,
  ];
  for (const value of fields) {
    const ts = toEpochMs(value);
    if (Number.isFinite(ts)) return ts;
  }
  return null;
};

const pickPct = (alert) => {
  const evidence = alert?.evidence || {};
  const value =
    evidence.pct_1m ??
    evidence.pct_3m ??
    evidence.pct_5m ??
    evidence.pct_15m ??
    evidence.pct_1h ??
    alert?.pct ??
    alert?.magnitude ??
    null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const pickVolPct = (alert) => {
  const evidence = alert?.evidence || {};
  const value =
    evidence.volume_change_1h_pct ??
    evidence.vol_change_1h_pct ??
    evidence.vol_pct ??
    null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const alertSymbol = (alert) =>
  String(
    alert?.symbol ||
      alert?.product_id ||
      alert?.productId ||
      alert?.coin ||
      alert?.pair ||
      alert?.asset ||
      ""
  )
    .toUpperCase()
    .replace(/-USD$|-USDT$|-USDC$|-PERP$/i, "");

const priorityEvidenceIdentity = (alert) => {
  if (alert?.id != null) return `id:${String(alert.id)}`;
  if (alert?.alert_id != null) return `alert:${String(alert.alert_id)}`;
  return [
    alertSymbol(alert),
    rawTypeKey(alert),
    String(alert?.window || alert?.evidence?.window || "").toLowerCase(),
    String(alert?.direction || "").toLowerCase(),
    pickTsMs(alert) ?? "",
  ].join(":");
};

export const buildPriorityEvidence = ({
  activeAlerts = [],
  recentAlerts = [],
  nowMs,
}) => {
  const seen = new Set();
  const eligible = [];
  for (const alert of [...activeAlerts, ...recentAlerts]) {
    if (!alert || typeof alert !== "object") continue;
    if (!isCoinEventActive(alert, nowMs)) continue;
    const identity = priorityEvidenceIdentity(alert);
    if (seen.has(identity)) continue;
    seen.add(identity);
    eligible.push(alert);
  }
  return eligible;
};

export const priorityBucketForAlert = (alert) => {
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

export const priorityContributionScore = (alert, nowMs) => {
  const tsMs = pickTsMs(alert);
  if (!Number.isFinite(tsMs)) return null;
  const ageMs = Math.max(0, nowMs - tsMs);
  if (ageMs > PRIORITY_SOFT_EXPIRY_MS) return null;

  const severity = String(alert?.severity || "info").toLowerCase();
  const severityWeight =
    { critical: 24, high: 18, medium: 12, low: 6, info: 3 }[severity] || 3;
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

const buildRankMap = (rows = []) => {
  const map = new Map();
  rows.forEach((row, index) => {
    const symbol = alertSymbol(row);
    if (!symbol || map.has(symbol)) return;
    const rank = Number(row?.rank ?? index + 1);
    map.set(symbol, Number.isFinite(rank) ? rank : index + 1);
  });
  return map;
};

const computeRankPersistenceScore = (entry) => {
  let score = 0;
  if (Number.isFinite(entry.rank1m)) score += clamp(12 - entry.rank1m, 0, 10);
  if (Number.isFinite(entry.rank3m)) score += clamp(12 - entry.rank3m, 0, 10);
  if (Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    score += clamp(6 - Math.abs(entry.rank1m - entry.rank3m) * 2, 0, 6);
  }
  return clamp(score, 0, 18);
};

export const computeRankTrend = (entry) => {
  if (
    entry.bucket === "bullish" &&
    Number.isFinite(entry.rank1m) &&
    Number.isFinite(entry.rank3m)
  ) {
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

export const buildRankSummary = (entry) => {
  if (Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    const low = Math.min(entry.rank1m, entry.rank3m);
    const high = Math.max(entry.rank1m, entry.rank3m);
    return `rank held ${low}-${high}`;
  }
  if (Number.isFinite(entry.rank1m)) return `1m rank ${entry.rank1m}`;
  if (Number.isFinite(entry.rank3m)) {
    return `${entry.bucket === "bearish" ? "3m loss" : "3m"} rank ${entry.rank3m}`;
  }
  return "";
};

export const priorityStateForEntry = (entry) => {
  if (entry.noConfirmMs >= PRIORITY_FADING_MS) return "Fading";
  if (entry.reversalRiskScore >= 14 || entry.bucket === "divergence") {
    return "Reversal Risk";
  }
  if (entry.score < 40) return "Fading";
  if (
    entry.score >= 85 &&
    entry.freshConfirms >= 1 &&
    entry.volumeAligned &&
    !entry.divergenceFlag
  ) {
    return "Dominant";
  }
  if (entry.score >= 70 && entry.rankPersistenceScore >= 10) return "Persistent";
  if (entry.score >= 55) return "Building";
  return "Fragile";
};

const PRIORITY_STATE_ORDER = [
  "Dominant",
  "Persistent",
  "Building",
  "Reversal Risk",
  "Fragile",
  "Fading",
];

const comparePriorityEntries = (a, b) => {
  const stateDelta =
    PRIORITY_STATE_ORDER.indexOf(a.stateLabel) -
    PRIORITY_STATE_ORDER.indexOf(b.stateLabel);
  return stateDelta || b.score - a.score || b.lastTsMs - a.lastTsMs;
};

const selectCanonicalEntry = (entries) => {
  const currentRisk = entries
    .filter(
      (entry) =>
        entry.stateLabel === "Reversal Risk" &&
        entry.noConfirmMs < PRIORITY_FADING_MS
    )
    .sort(comparePriorityEntries)[0];
  if (currentRisk) return currentRisk;

  // Once risk is stale, current directional evidence is the better authority.
  const nonRisk = entries.filter((entry) => entry.stateLabel !== "Reversal Risk");
  return [...(nonRisk.length ? nonRisk : entries)].sort(comparePriorityEntries)[0];
};

export const buildPriorityItems = ({
  alerts = [],
  gainers1m = [],
  gainers3m = [],
  losers3m = [],
  marketPressure = null,
  nowMs,
  limit = null,
}) => {
  const boardRanks = {
    oneMin: buildRankMap(gainers1m),
    gain3m: buildRankMap(gainers3m),
    loss3m: buildRankMap(losers3m),
  };
  const grouped = new Map();

  for (const alert of alerts) {
    const symbol = alertSymbol(alert);
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
      topVolPct: 0,
      topVolSign: 1,
      rank1m: null,
      rank3m: null,
      breadthSupport: null,
      divergenceFlag: bucket === "divergence",
    };

    existing.scoreRaw += contribution.weighted;
    existing.confirms += 1;
    if (contribution.isFresh) existing.freshConfirms += 1;
    if (contribution.tsMs > existing.lastTsMs) existing.lastTsMs = contribution.tsMs;
    if (contribution.streak > existing.maxStreak) existing.maxStreak = contribution.streak;

    const volSigned = pickVolPct(alert);
    if (Number.isFinite(volSigned) && Math.abs(volSigned) >= existing.topVolPct) {
      existing.topVolPct = Math.abs(volSigned);
      existing.topVolSign = volSigned >= 0 ? 1 : -1;
    }

    const rank1m = boardRanks.oneMin.get(symbol);
    const rank3m =
      bucket === "bearish"
        ? boardRanks.loss3m.get(symbol)
        : boardRanks.gain3m.get(symbol);
    if (Number.isFinite(rank1m)) existing.rank1m = rank1m;
    if (Number.isFinite(rank3m)) existing.rank3m = rank3m;

    const evidence = alert?.evidence || {};
    const breadthUpRaw =
      evidence.breadth_up ??
      marketPressure?.breadth_up ??
      marketPressure?.components?.breadth;
    const breadthDownRaw = evidence.breadth_down ?? marketPressure?.breadth_down;
    const breadthComponentRaw = marketPressure?.components?.breadth;
    const numberOrNull = (value) =>
      value === null || value === undefined || value === "" ? null : Number(value);
    const breadthUp = numberOrNull(breadthUpRaw);
    const breadthDown = numberOrNull(breadthDownRaw);
    const breadthComponent = numberOrNull(breadthComponentRaw);
    const breadthSupport =
      bucket === "bullish"
        ? breadthUp
        : bucket === "bearish"
          ? breadthDown
          : Number.isFinite(breadthUp) && Number.isFinite(breadthDown)
            ? Math.max(
                Math.abs(breadthUp - breadthDown),
                Number.isFinite(breadthComponent) ? breadthComponent : 0
              )
            : breadthComponent;
    if (Number.isFinite(breadthSupport)) {
      existing.breadthSupport = Math.max(
        Number.isFinite(existing.breadthSupport) ? existing.breadthSupport : 0,
        clamp(breadthSupport, 0, 1)
      );
    }

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
    const breadthBonus = Number.isFinite(entry.breadthSupport)
      ? Math.round(entry.breadthSupport * 10)
      : 0;
    const score = clamp(
      Math.round(
        entry.scoreRaw +
          confirmationBonus +
          freshBonus +
          entry.rankPersistenceScore +
          volumeBonus +
          breadthBonus -
          stalePenalty
      ),
      1,
      99
    );
    return { ...entry, score, stateLabel: priorityStateForEntry({ ...entry, score }) };
  });

  const entriesBySymbol = new Map();
  for (const entry of ranked) {
    const entries = entriesBySymbol.get(entry.symbol) || [];
    entries.push(entry);
    entriesBySymbol.set(entry.symbol, entries);
  }

  const canonical = Array.from(entriesBySymbol.values()).map(selectCanonicalEntry);
  const ordered = canonical.sort(comparePriorityEntries);
  return Number.isFinite(limit) ? ordered.slice(0, limit) : ordered;
};
