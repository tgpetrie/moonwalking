export const FRESHNESS_THRESHOLDS = {
  "1m": { delayedAfterS: 10, staleAfterS: 20 },
  "3m": { delayedAfterS: 24, staleAfterS: 32 },
};

export const OFFLINE_AFTER_S = 60;

export function boardSourceTime(snapshot, receivedAt) {
  if (!Number.isFinite(receivedAt)) return null;
  const sourceAge = snapshot?.meta?.staleSeconds;
  if (Number.isFinite(sourceAge)) return receivedAt - Math.max(0, sourceAge) * 1000;
  const updatedAt = snapshot?.updated_at;
  const timestamp = typeof updatedAt === "number" ? updatedAt : Date.parse(updatedAt);
  return Number.isFinite(timestamp) ? Math.min(timestamp, receivedAt) : null;
}

export function deriveFreshness({
  cadence = "1m",
  hasData = false,
  warming = false,
  unreachable = false,
  sourceMs = null,
  lastSuccessMs = null,
  nowMs = Date.now(),
}) {
  const age = Number.isFinite(sourceMs) ? Math.max(0, (nowMs - sourceMs) / 1000) : null;
  const ageSeconds = age === null ? null : Math.floor(age);
  const requestAge = Number.isFinite(lastSuccessMs)
    ? (nowMs - lastSuccessMs) / 1000
    : null;
  if (requestAge >= OFFLINE_AFTER_S || (unreachable && requestAge === null)) {
    return { status: "offline", ageSeconds };
  }
  if (requestAge === null) return { status: hasData ? "stale" : "connecting", ageSeconds };
  if (warming && !hasData) return { status: "warming", ageSeconds: null };
  const { delayedAfterS, staleAfterS } = FRESHNESS_THRESHOLDS[cadence] ?? FRESHNESS_THRESHOLDS["1m"];
  if (age === null || age > staleAfterS) return { status: "stale", ageSeconds };
  if (age > delayedAfterS || unreachable) return { status: "delayed", ageSeconds };
  return { status: "live", ageSeconds };
}

export function formatAge(seconds) {
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
