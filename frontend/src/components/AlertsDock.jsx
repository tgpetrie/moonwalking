import { useEffect, useMemo, useRef, useState } from "react";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { useData } from "../context/DataContext";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";

const toMs = (ts) => {
  const t = Date.parse(ts || "");
  return Number.isFinite(t) ? t : null;
};

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

const severityTone = (sev) => {
  const s = String(sev || "").toLowerCase();
  if (s === "critical") return "bh-alert-chip bh-alert-chip--critical";
  if (s === "high") return "bh-alert-chip bh-alert-chip--high";
  if (s === "medium") return "bh-alert-chip bh-alert-chip--medium";
  if (s === "low") return "bh-alert-chip bh-alert-chip--low";
  return "bh-alert-chip bh-alert-chip--info";
};

export default function AlertsDock() {
  const { alerts = [] } = useData() || {};
  const [open, setOpen] = useState(false);
  const mountedRef = useRef(false);

  const normalized = useMemo(() => {
    const list = Array.isArray(alerts) ? alerts : [];
    const out = [];
    const seen = new Set();

    for (const a of list) {
      if (!a || typeof a !== "object") continue;
      const id = a.id || `${a.symbol || "UNK"}-${a.type || "t"}-${a.ts || ""}`;
      if (seen.has(id)) continue;
      seen.add(id);

      const tsMs = toMs(a.ts);
      const productId = a.product_id || (a.symbol ? `${a.symbol}-USD` : null);
      const url = a.trade_url || coinbaseSpotUrl({ product_id: productId, symbol: a.symbol });

      out.push({
        ...a,
        id,
        tsMs,
        productId,
        url,
      });
    }

    out.sort((x, y) => (y.tsMs || 0) - (x.tsMs || 0));
    return out;
  }, [alerts]);

  const latestId = normalized[0]?.id || null;
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
      if (e.key === "Escape") setOpen(false);
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

  const now = Date.now();

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
        <div className="bh-alerts-panel" role="dialog" aria-label="Alerts">
          <div className="bh-alerts-head">
            <div className="bh-alerts-title">Moonwalking Alerts</div>
            <button type="button" className="bh-alerts-close" onClick={() => setOpen(false)} aria-label="Close">
              ×
            </button>
          </div>

          <div className="bh-alerts-list" role="list">
            {normalized.length === 0 ? (
              <div className="bh-alerts-empty">No active alerts.</div>
            ) : (
              normalized.slice(0, 50).map((a) => {
                const age = a.tsMs ? formatAge(now - a.tsMs) : "—";
                const type = String(a.type || "alert").toUpperCase();
                const sev = String(a.severity || "info").toUpperCase();

                return (
                  <div key={a.id} className="bh-alert" role="listitem">
                    <div className="bh-alert-top">
                      <div className="bh-alert-left">
                        <a className="bh-alert-symbol" href={a.url || "#"} target="_blank" rel="noreferrer">
                          {String(a.symbol || "—").toUpperCase()}
                        </a>
                        <span className="bh-alert-age">{age}</span>
                      </div>
                      <div className="bh-alert-right">
                        <span className="bh-alert-chip">{type}</span>
                        <span className={severityTone(a.severity)}>{sev}</span>
                      </div>
                    </div>

                    {a.message ? <div className="bh-alert-msg">{a.message}</div> : null}
                  </div>
                );
              })
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
