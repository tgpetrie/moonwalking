/**
 * Semantic dedup for Intelligence Log backend alerts.
 *
 * Identity = type_key | symbol | window | direction
 * (mirrors the backend's own _alert_stream_key — same ongoing condition,
 *  same key, regardless of UUID rotation between backend cooldown cycles).
 *
 * TTL-based: entries expire after SEEN_TTL_MS so the same condition can
 * re-appear after a backend cooldown cycle without being permanently suppressed.
 */

const SEEN_TTL_MS = 5 * 60 * 1000; // 5 min — covers one backend cooldown cycle

export function createEventKey(alert) {
  const type = String(alert?.type_key || alert?.type || "").toLowerCase();
  const symbol = String(alert?.symbol || alert?.product_id || "")
    .replace(/-USD$|-USDT$|-PERP$/i, "")
    .toUpperCase();
  const window = String(
    alert?.window || alert?.evidence?.window || ""
  ).toLowerCase();
  const direction = String(alert?.direction || "").toLowerCase();
  return `${type}|${symbol}|${window}|${direction}`;
}

export function shouldSkip(key, seenMap, nowMs) {
  const ts = seenMap.get(key);
  return ts !== undefined && nowMs - ts < SEEN_TTL_MS;
}

export function markSeen(key, seenMap, nowMs) {
  seenMap.set(key, nowMs);
}

export function expireOldKeys(seenMap, nowMs) {
  for (const [k, ts] of seenMap) {
    if (nowMs - ts > SEEN_TTL_MS * 2) seenMap.delete(k);
  }
}
