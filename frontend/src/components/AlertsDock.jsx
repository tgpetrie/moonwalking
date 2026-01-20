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

const windowLabelFromType = (raw) => {
  const t = String(raw || "").toUpperCase();
  if (t.includes("_1M")) return "1m";
  if (t.includes("_3M")) return "3m";
  if (t.includes("_5M")) return "5m";
  if (t.includes("_15M")) return "15m";
  return "";
};

const pctForDisplay = (pct, windowLabel) => {
  if (pct == null || !Number.isFinite(pct)) return "–";
  const abs = Math.abs(pct);
  const decimals = (windowLabel === "1m" || windowLabel === "3m")
    ? (abs < 5 ? 3 : 2)
    : (abs < 10 ? 2 : 1);
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(decimals)}%`;
};

const priceForDisplay = (p) => {
  if (p == null || !Number.isFinite(p)) return "–";
  if (p >= 1000) return p.toFixed(0);
  if (p >= 100) return p.toFixed(2);
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(4);
  return p.toPrecision(3);
};

const uiTypeLabel = (a) => {
  const pct = Number(a?.pct);
  const sev = String(a?.severity || a?.sev || "").toUpperCase();
  const w = windowLabelFromType(a?.type);
  const strong = (w === "1m") ? 1.25 : (w === "3m") ? 1.75 : 2.5;
  const medium = (w === "1m") ? 0.75 : (w === "3m") ? 1.00 : 1.5;
  const abs = Number.isFinite(pct) ? Math.abs(pct) : 0;
  const t = String(a?.type || "").toUpperCase();

  if (t.includes("DIVERGENCE")) return "DIVERGENCE";
  if (t.includes("VOLUME")) return "VOLUME";
  if (!Number.isFinite(pct)) return "IMPULSE";

  if (pct >= 0) {
    if (sev === "CRITICAL" || abs >= strong) return "MOONSHOT";
    if (sev === "HIGH" || abs >= medium) return "BREAKOUT";
    return "IMPULSE";
  }
  if (sev === "CRITICAL" || abs >= strong) return "CRATER";
  if (sev === "HIGH" || abs >= medium) return "DUMP";
  return "IMPULSE";
};

const formatDirection = (raw) => {
  const d = String(raw || "").toLowerCase();
  if (d === "up") return { label: "Up", arrow: "↑", tone: "up" };
  if (d === "down") return { label: "Down", arrow: "↓", tone: "down" };
  return { label: "Flat", arrow: "•", tone: "flat" };
};

const toProductId = (a) => {
  let p = String(a?.product_id || a?.symbol || "").trim().toUpperCase();
  if (!p) return "";
  if (!p.includes("-")) p = `${p}-USD`;
  return p;
};

const TYPE_OPTIONS = ["ALL", "MOONSHOT", "CRATER", "BREAKOUT", "DUMP", "DIVERGENCE", "VOLUME", "IMPULSE"];

export default function AlertsDock() {
  const { alerts = [] } = useData() || {};
  const [open, setOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState("ALL");
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
      const derivedType = uiTypeLabel(a);

      out.push({
        ...a,
        id,
        tsMs,
        productId,
        url,
        derivedType,
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
  const filtered = useMemo(() => {
    if (typeFilter === "ALL") return normalized;
    return normalized.filter((a) => a.derivedType === typeFilter);
  }, [normalized, typeFilter]);

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
          <div className="bh-alerts-filters" role="tablist" aria-label="Alert type filters">
            {TYPE_OPTIONS.map((t) => (
              <button
                key={t}
                type="button"
                className={`bh-alerts-filter${typeFilter === t ? " is-active" : ""}`}
                onClick={() => setTypeFilter(t)}
                role="tab"
                aria-selected={typeFilter === t}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="bh-alerts-list" role="list">
            {filtered.length === 0 ? (
              <div className="bh-alerts-empty">No active alerts.</div>
            ) : (
              filtered.slice(0, 50).map((a) => {
                const age = a.tsMs ? formatAge(now - a.tsMs) : "—";
                const sev = String(a.severity || "info").toUpperCase();
                const direction = formatDirection(a.meta?.direction);
                const w = windowLabelFromType(a.type);
                const magnitude = Number.isFinite(Number(a?.pct))
                  ? Number(a.pct)
                  : Number.isFinite(Number(a?.meta?.magnitude))
                    ? (String(a?.meta?.direction || "").toLowerCase() === "down"
                      ? -Number(a.meta.magnitude)
                      : Number(a.meta.magnitude))
                    : null;
                const pctText = pctForDisplay(magnitude, w);
                const priceNowRaw = Number(a.price_now ?? a.price ?? null);
                const priceThenRaw = Number(a.price_then ?? null);
                const priceNow = priceForDisplay(Number.isFinite(priceNowRaw) ? priceNowRaw : null);
                const priceThen = priceForDisplay(Number.isFinite(priceThenRaw) ? priceThenRaw : null);
                const priceLine = (priceNow !== "–" && priceThen !== "–")
                  ? `$${priceNow} from $${priceThen}`
                  : (priceNow !== "–" ? `$${priceNow}` : "");
                const volPct = Number(a.vol_change_pct ?? null);
                const volNow = Number(a.vol_now ?? null);
                const volThen = Number(a.vol_then ?? null);
                let volLine = "";
                if (Number.isFinite(volPct)) {
                  const sign = volPct > 0 ? "+" : "";
                  volLine = `Vol ${sign}${volPct.toFixed(0)}%`;
                } else if (Number.isFinite(volNow) && Number.isFinite(volThen) && volThen > 0) {
                  const v = ((volNow - volThen) / volThen) * 100;
                  const sign = v > 0 ? "+" : "";
                  volLine = `Vol ${sign}${v.toFixed(0)}%`;
                }
                const symbol = String(a.productId || a.symbol || "").replace("-USD", "").toUpperCase();
                const headerParts = [
                  `${a.derivedType} ${symbol}`,
                  pctText !== "–" ? `${pctText}${w ? ` in ${w}` : ""}` : null,
                ].filter(Boolean);
                const lineParts = [
                  headerParts.join(" "),
                  priceLine || null,
                  volLine || null,
                ].filter(Boolean);
                const line = lineParts.join(" · ");
                const url = a.url || coinbaseSpotUrl({ product_id: toProductId(a), symbol: a.symbol });
                const handleRowClick = () => {
                  if (!url) return;
                  window.open(url, "_blank", "noopener,noreferrer");
                };

                return (
                  <div
                    key={a.id}
                    className="bh-alert bh-alert--clickable"
                    role="button"
                    tabIndex={0}
                    onClick={handleRowClick}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleRowClick();
                      }
                    }}
                  >
                    <div className="bh-alert-top">
                      <div className="bh-alert-left">
                        <a className="bh-alert-symbol" href={a.url || "#"} target="_blank" rel="noreferrer">
                          {String(a.symbol || "—").toUpperCase()}
                        </a>
                        <span className="bh-alert-age">{age}</span>
                      </div>
                      <div className="bh-alert-right">
                        <span className={severityTone(a.severity)}>{sev}</span>
                      </div>
                    </div>

                    <div className="bh-alert-subline">
                      <span className={`bh-alert-dir bh-alert-dir--${direction.tone}`}>
                        {direction.arrow} {direction.label}
                      </span>
                      <span className="bh-alert-chip bh-alert-chip--type">{a.derivedType}</span>
                    </div>

                    {line ? <div className="bh-alert-msg">{line}</div> : null}
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
