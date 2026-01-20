import { useEffect, useMemo, useRef, useState } from "react";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { useData } from "../context/DataContext";
import { SEV_RANK, useAlertsModel } from "./alertsState";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";
const MODE_ALL = "ALL";
const MODE_TYPE = "TYPE";
const MODE_HISTORY = "HISTORY";
const MODE_PULSE = "PULSE";
const alertKey = (a) => a?.id || `${a?.type || "t"}::${a?.symbol || "sym"}::${a?.ts || ""}`;
const formatAge = (ms) => {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
};

const fmtSignedPct = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  const sign = x > 0 ? "+" : x < 0 ? "-" : "";
  return `${sign}${x.toFixed(2)}%`;
};

const fmtWindow = (a) => {
  if (a?.window) return a.window;
  const t = String(a?.intel_text || "");
  const m = t.match(/\bin\s+(\d+)\s*(m|min|mins)\b/i);
  if (m) return `${m[1]}m`;
  return "—";
};

const alertSignedChange = (a) => {
  const raw = Number(a?.change_pct);
  if (Number.isFinite(raw)) return raw;
  const mag = Number(a?.magnitude);
  if (!Number.isFinite(mag)) return null;
  const dir = a?.direction === "down" ? -1 : 1;
  return dir * Math.abs(mag);
};

const alertAgeMs = (a, nowMs) => {
  const ts = Number(a?.tsMs);
  if (!Number.isFinite(ts)) return null;
  return Math.max(0, nowMs - ts);
};

const severityTone = (sev) => {
  const s = String(sev || "").toLowerCase().replace(/[^a-z]/g, "");
  if (s === "critical") return "bh-alert-chip bh-alert-chip--critical";
  if (s === "high") return "bh-alert-chip bh-alert-chip--high";
  if (s === "medium") return "bh-alert-chip bh-alert-chip--medium";
  if (s === "low") return "bh-alert-chip bh-alert-chip--low";
  return "bh-alert-chip bh-alert-chip--info";
};

const normalizeSeverity = (sev) => {
  const s = String(sev || "").toLowerCase().replace(/[^a-z]/g, "");
  if (s === "critical" || s === "high" || s === "medium" || s === "low") return s;
  return "info";
};

const normalizeType = (type) => {
  const raw = String(type || "alert").toUpperCase();
  const cleaned = raw.replace(/[^A-Z0-9_ ]+/g, "").trim();
  return cleaned || "ALERT";
};

const alertLabel = (a) => normalizeType(a?.typeLabel || a?.type || a?.title || "alert");

const CLASS_ORDER = {
  CRATER: 1,
  MOONSHOT: 2,
  WHALE_MOVE: 3,
  SENTIMENT_SPIKE: 4,
  DIVERGENCE: 5,
  BREAKOUT: 6,
  ARBITRAGE: 7,
  NEWS: 8,
  ALERT: 9,
};

const normalizeClassKey = (a) => {
  const ck = (a.class_key || a.type || a.scope || "").toString().toUpperCase().replace(/[^A-Z0-9_ ]+/g, "").trim();
  if (ck) return ck;
  return "ALERT";
};

export default function AlertsDock() {
  const { alerts = [] } = useData() || {};
  const { state, visible, pulseAlerts } = useAlertsModel(alerts);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState(MODE_ALL);
  const flashRef = useRef(new Map());
  const [flashTick, setFlashTick] = useState(0);
  const mountedRef = useRef(false);
  const now = state.nowMs ?? Date.now();
  const latestId = useMemo(() => {
    let newestId = null;
    let newestTs = -1;
    for (const id of state.order) {
      const a = state.byId[id];
      const ts = a?.tsMs ?? 0;
      if (ts > newestTs) {
        newestTs = ts;
        newestId = id;
      }
    }
    return newestId;
  }, [state.byId, state.order]);
  const [lastSeenId, setLastSeenId] = useState(() => {
    try {
      return localStorage.getItem(LS_SEEN_KEY);
    } catch {
      return null;
    }
  });

  const unread = Boolean(latestId && latestId !== lastSeenId);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      const tag = String(e.target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || e.target?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "Escape") setOpen(false);
      const key = String(e.key || "").toLowerCase();
      if (key === "a") setMode(MODE_ALL);
      if (key === "t") setMode(MODE_TYPE);
      if (key === "h") setMode(MODE_HISTORY);
      if (key === "p") setMode(MODE_PULSE);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (!latestId) return;
    setLastSeenId(latestId);
    try {
      localStorage.setItem(LS_SEEN_KEY, latestId);
    } catch {}
  }, [open, latestId]);

  const markFlashIfChanged = (a) => {
    const id = alertKey(a);
    const mag = Number(a?.magnitude);
    const pct = Number(a?.change_pct);
    const prev = flashRef.current.get(id);
    const changed = (Number.isFinite(mag) && prev?.mag !== mag) || (Number.isFinite(pct) && prev?.pct !== pct);

    if (changed) {
      flashRef.current.set(id, { mag, pct, t: Date.now() });
      setFlashTick((x) => x + 1);
    } else if (!prev) {
      flashRef.current.set(id, { mag, pct, t: 0 });
    }
  };

  const flashClassFor = (a) => {
    const id = alertKey(a);
    const rec = flashRef.current.get(id);
    if (!rec?.t) return "";
    const age = Date.now() - rec.t;
    if (age < 260) return "bh-alert-tick";
    return "";
  };

  const renderAlertRow = (a) => {
    markFlashIfChanged(a);
    const flashCls = flashClassFor(a);
    const ageMs = alertAgeMs(a, now);
    const age = ageMs == null ? "" : `${formatAge(ageMs)} ago`;
    const severityKey = a.severityKey || normalizeSeverity(a.severity);
    const sev = String(severityKey || "info").toUpperCase();
    const label = alertLabel(a);
    const symbol = String(a.symbol || "—").toUpperCase();
    const signedChange = alertSignedChange(a);
    const pctText = fmtSignedPct(signedChange);
    const win = fmtWindow(a);
    const moveText = pctText === "—" ? "—" : (win !== "—" ? `${pctText} in ${win}` : pctText);
    const headline = `${label} ${symbol} ${moveText}${age ? ` · ${age}` : ""}`;
    const expired = typeof a.expired === "boolean" ? a.expired : (Number.isFinite(a.expiresMs) ? now >= a.expiresMs : false);
    const productId = a.product_id || (a.symbol ? `${a.symbol}-USD` : null);
    const url = a.trade_url || a.url || coinbaseSpotUrl({ product_id: productId, symbol: a.symbol });
    const fade = typeof a.fade === "number" ? a.fade : 1;
    const dirCls = a.direction === "down" ? "bh-alert-dir-down" : "bh-alert-dir-up";

    const unpinned = a.unpinned === true;

    return (
      <div
        key={alertKey(a)}
        className={`bh-alert bh-alert-row bh-row ${dirCls}${expired ? " bh-alert--expired" : ""}${unpinned ? " bh-alert--unpinned" : ""}`}
        data-expired={expired ? "1" : "0"}
        role="listitem"
        style={{ opacity: fade }}
        title={headline}
      >
        <div className="bh-alert-line">
          <span className="bh-alert-chip">{label}</span>
          <a className="bh-alert-symbol" href={url || "#"} target="_blank" rel="noreferrer">
            {symbol}
          </a>
          <span className={`bh-alert-move bh-price ${flashCls}`}>{moveText}</span>
          {age ? <span className="bh-alert-age">{`· ${age}`}</span> : null}
          <span className={severityTone(severityKey)}>{sev}</span>
          {a.resurfaced ? <span className="bh-alert-chip bh-alert-chip--resurfaced">RESURFACED</span> : null}
        </div>
      </div>
    );
  };

  const renderTypeRow = (a) => {
    const severityKey = a.severityKey || normalizeSeverity(a.severity);
    const sev = String(severityKey || "info").toUpperCase();
    const productId = a.product_id || (a.symbol ? `${a.symbol}-USD` : null);
    const url = a.trade_url || a.url || coinbaseSpotUrl({ product_id: productId, symbol: a.symbol });
    const fade = typeof a.fade === "number" ? a.fade : 1;
    return (
      <a
        key={a.id}
        className="flex items-center gap-2 py-1 text-xs text-gray-200 hover:text-amber-200"
        href={url || "#"}
        target="_blank"
        rel="noreferrer"
        style={{ opacity: fade }}
      >
        <span className="text-gray-500">•</span>
        <span className="font-semibold">{String(a.symbol || "—").toUpperCase()}</span>
        <span className="ml-auto px-1 py-0.5 rounded bg-gray-800 text-[10px] tracking-wide">{sev}</span>
      </a>
    );
  };

  const renderPulseRow = (a) => {
    const ageMs = alertAgeMs(a, now);
    const ageText = ageMs == null ? "" : `${formatAge(ageMs)} ago`;
    const label = alertLabel(a);
    const symbol = String(a.symbol || "—").toUpperCase();
    const signedChange = alertSignedChange(a);
    const pctText = fmtSignedPct(signedChange);
    const win = fmtWindow(a);
    const moveText = pctText === "—" ? "—" : (win !== "—" ? `${pctText} in ${win}` : pctText);
    const productId = a.product_id || (a.symbol ? `${a.symbol}-USD` : null);
    const url = a.trade_url || a.url || coinbaseSpotUrl({ product_id: productId, symbol: a.symbol });
    const fade = typeof a.fade === "number" ? a.fade : 1;

    return (
      <div
        key={a.pulseKey}
        className="bh-pulse-row bh-row"
        role={url ? "link" : "listitem"}
        tabIndex={url ? 0 : undefined}
        onClick={() => url && window.open(url, "_blank", "noopener,noreferrer")}
        onKeyDown={(e) => {
          if (!url) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            window.open(url, "_blank", "noopener,noreferrer");
          }
        }}
        style={{ opacity: fade }}
        title={`${label} ${symbol} ${moveText}${ageText ? ` · ${ageText}` : ""}`}
      >
        <div className="bh-alert-line">
          <span className="bh-alert-chip">{label}</span>
          <span className="bh-alert-symbol">{symbol}</span>
          <span className="bh-alert-move">{moveText}</span>
          {ageText ? <span className="bh-alert-age">{`· ${ageText}`}</span> : null}
          <span className={severityTone(a.severityKey || normalizeSeverity(a.severity))}>
            {String(a.severityKey || a.severity || "low").toUpperCase()}
          </span>
        </div>
      </div>
    );
  };

  const listLimit = mode === MODE_HISTORY ? 200 : 50;
  const visibleList = visible.slice(0, listLimit);
  const pulseList = pulseAlerts.slice(0, listLimit);
  const groups = useMemo(() => {
    if (mode !== MODE_TYPE) return null;
    const map = new Map();
    for (const a of visible) {
      const key = normalizeClassKey(a);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(a);
    }
    const sorter = (x, y) => {
      const sx = SEV_RANK[x.severity] ?? 0;
      const sy = SEV_RANK[y.severity] ?? 0;
      if (sx !== sy) return sy - sx;
      const mx = x.magnitude ?? 0;
      const my = y.magnitude ?? 0;
      if (mx !== my) return my - mx;
      return (y.tsMs || 0) - (x.tsMs || 0);
    };
    return Array.from(map.entries())
      .map(([key, items]) => ({
        key,
        items: items.slice().sort(sorter),
        order: CLASS_ORDER[key] ?? 99,
      }))
      .sort((a, b) => (a.order || 99) - (b.order || 99));
  }, [mode, visible]);

  return (
    <div className="bh-alerts-dock" data-open={open ? "1" : "0"}>
      <button
        type="button"
        className="bh-alerts-btn"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title={unread ? "New alerts" : "Alerts"}
      >
        <span className="bh-alerts-btn-label">ALERTS</span>
        {unread ? <span className="bh-alerts-badge" aria-label="unread alerts" /> : null}
      </button>

      {open ? (
        <div className="bh-alerts-panel bh-rail bh-mod-alert" role="dialog" aria-label="Alerts">
            <div className="bh-alerts-head">
              <div className="bh-alerts-title">Moonwalking Alerts</div>
              <div className="bh-alerts-modes" role="tablist" aria-label="Alert modes">
              {[MODE_ALL, MODE_TYPE, MODE_HISTORY, MODE_PULSE].map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`bh-alerts-mode${mode === m ? " is-active" : ""}`}
                  onClick={() => setMode(m)}
                  aria-pressed={mode === m}
                >
                  {m}
                </button>
              ))}
            </div>
            <button type="button" className="bh-alerts-close" onClick={() => setOpen(false)} aria-label="Close">
              ×
            </button>
          </div>

          <div className="bh-alerts-list" role="list">
            {mode !== MODE_PULSE && pulseAlerts.length > 0 && (
              <div className="bh-pulse-strip">
                <div className="bh-pulse-strip-title">LOW PULSE</div>
                {pulseAlerts.slice(0, 10).map(renderPulseRow)}
              </div>
            )}
            {mode === MODE_PULSE ? (
              pulseList.length === 0 ? (
                <div className="bh-alerts-empty">No pulse alerts.</div>
              ) : (
                pulseList.map((a) => renderPulseRow(a))
              )
            ) : visibleList.length === 0 ? (
              <div className="bh-alerts-empty">No active alerts.</div>
            ) : mode === MODE_TYPE && groups ? (
              groups.map((group) => (
                <div key={group.key} className="bh-alert-group">
                  <div className="bh-alert-group-title">{group.key}</div>
                  {group.items.slice(0, listLimit).map((a) => renderTypeRow(a))}
                </div>
              ))
            ) : (
              visibleList.map((a) => renderAlertRow(a))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
