import { useMemo } from "react";

export const SEV_RANK = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
};

const normalizeSeverityKey = (sev) => {
  const s = String(sev || "").toLowerCase().replace(/[^a-z]/g, "");
  if (s === "critical" || s === "high" || s === "medium" || s === "low") return s;
  return "info";
};

const normalizeWindow = (raw) => {
  const text = String(raw || "");
  const match = text.match(/\b(\d+)\s*(m|min|mins|minute|minutes)\b/i);
  if (match) return `${match[1]}m`;
  return "—";
};

const pulseTypeLabel = (a) => {
  const raw = a?.typeLabel || a?.type || a?.title || a?.class_key || "ALERT";
  return String(raw).toUpperCase().replace(/[^A-Z0-9_ ]+/g, "").trim() || "ALERT";
};

const pulseWindowLabel = (a) => {
  const raw = a?.window || a?.intel_text || a?.type || "";
  return normalizeWindow(raw);
};

const toTsMs = (a) => {
  if (Number.isFinite(a?.tsMs)) return Number(a.tsMs);
  if (Number.isFinite(a?.ts_ms)) return Number(a.ts_ms);
  const t = Date.parse(a?.ts || a?.time || "");
  return Number.isFinite(t) ? t : null;
};

const normalizeSymbol = (a) => {
  const raw = a?.symbol || a?.product_id || a?.pair || a?.ticker || "";
  const clean = String(raw || "").toUpperCase();
  return clean.replace(/-USD$|-USDT$|-PERP$/i, "") || "—";
};

const alertId = (a, symbol) => {
  if (a?.id) return a.id;
  const type = a?.type || a?.typeLabel || a?.title || "ALERT";
  const ts = a?.ts || a?.time || "";
  return `${symbol}-${type}-${ts}`;
};

const normalizeAlert = (a) => {
  if (!a || typeof a !== "object") return null;
  const symbol = normalizeSymbol(a);
  const tsMs = toTsMs(a);
  const severityKey = a?.severityKey || a?.severity_key || normalizeSeverityKey(a?.severity);
  const direction = a?.direction || (Number(a?.change_pct ?? a?.magnitude) < 0 ? "down" : "up");
  const id = alertId(a, symbol);

  return {
    ...a,
    id,
    symbol,
    tsMs,
    severityKey,
    direction,
  };
};

export function useAlertsModel(alerts) {
  return useMemo(() => {
    const list = Array.isArray(alerts) ? alerts.map(normalizeAlert).filter(Boolean) : [];

    const sorted = list.slice().sort((a, b) => {
      const sx = SEV_RANK[a.severityKey] ?? 0;
      const sy = SEV_RANK[b.severityKey] ?? 0;
      if (sx !== sy) return sy - sx;
      const tx = Number(a.tsMs || 0);
      const ty = Number(b.tsMs || 0);
      return ty - tx;
    });

    const byId = Object.create(null);
    const order = [];
    for (const a of sorted) {
      byId[a.id] = a;
      order.push(a.id);
    }

    const pulseMap = new Map();
    for (const a of sorted) {
      const sev = normalizeSeverityKey(a.severityKey || a.severity);
      if (sev !== "low" && sev !== "info") continue;
      const pulseKey = `${a.symbol}::${pulseTypeLabel(a)}::${a.direction || "flat"}::${pulseWindowLabel(a)}`;
      const existing = pulseMap.get(pulseKey);
      if (!existing || (a.tsMs || 0) > (existing.tsMs || 0)) {
        pulseMap.set(pulseKey, {
          ...a,
          pulseKey,
        });
      }
    }

    return {
      state: {
        byId,
        order,
        nowMs: Date.now(),
      },
      visible: sorted,
      pulseAlerts: Array.from(pulseMap.values()),
    };
  }, [alerts]);
}
