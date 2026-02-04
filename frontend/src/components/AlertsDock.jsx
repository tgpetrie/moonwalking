import { useEffect, useMemo, useState } from "react";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { deriveAlertType, parseImpulseMessage, windowLabelFromType } from "../utils/alertClassifier";
import { useData } from "../context/DataContext";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";

const toMs = (v) => {
  if (v == null) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const n = Number(v);
  if (Number.isFinite(n) && n > 0) return n;
  const t = Date.parse(String(v));
  return Number.isFinite(t) ? t : null;
};

// Strict numeric parse: never turns null/undefined into 0
const asNumber = (v) => {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const s = String(v).trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
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

const TYPE_OPTIONS = ["ALL", "MOONSHOT", "CRATER", "BREAKOUT", "DUMP", "WHALE", "STEALTH", "DIVERGENCE", "FOMO", "FEAR", "VOLUME", "IMPULSE"];

export default function AlertsDock() {
  const { alerts = [] } = useData() || {};
  const [open, setOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [nowMs, setNowMs] = useState(() => Date.now());

  const normalized = useMemo(() => {
    const list = Array.isArray(alerts) ? alerts : [];
    const out = [];
    const seen = new Set();

    for (const a of list) {
      if (!a || typeof a !== "object") continue;
      const id = a.id || `${a.symbol || "UNK"}-${a.type || "t"}-${a.ts || ""}`;
      if (seen.has(id)) continue;
      seen.add(id);

      const tsMs = toMs(a.event_ts_ms ?? a.eventTsMs ?? a.ts_ms ?? a.tsMs ?? a.ts);
      const productId = a.product_id || (a.symbol ? `${a.symbol}-USD` : null);
      const url = a.trade_url || coinbaseSpotUrl({ product_id: productId, symbol: a.symbol });
      const parsed = parseImpulseMessage(a);
      const derivedType = deriveAlertType({ type: a?.type, pct: a.pct ?? parsed.parsed_pct, severity: a?.severity || a?.sev });

      out.push({
        ...a,
        ...parsed,
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
    if (!open) return;
    const handler = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (!latestId) return;
    setLastSeenId(latestId);
    try {
      localStorage.setItem(LS_SEEN_KEY, latestId);
    } catch {}
  }, [open, latestId]);

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
                const age = a.tsMs ? formatAge(nowMs - a.tsMs) : "—";
                const sev = String(a.severity || "info").toUpperCase();
                const direction = formatDirection(a.parsed_direction || a.meta?.direction);
                const w = windowLabelFromType(a.type) || a.parsed_window_label;
                const pctDirect = asNumber(a?.pct);
                const pctParsed = asNumber(a?.parsed_pct);
                const magnitude = pctDirect !== null
                  ? pctDirect
                  : pctParsed !== null
                    ? pctParsed
                    : Number.isFinite(Number(a?.meta?.magnitude))
                      ? (String(a?.meta?.direction || "").toLowerCase() === "down"
                        ? -Number(a.meta.magnitude)
                        : Number(a.meta.magnitude))
                      : null;
                const pctText = pctForDisplay(magnitude, w);
                // price (only if it actually exists)
                const priceNowRaw = asNumber(a.price_now ?? a.price ?? a.current_price ?? null);
                const priceThenRaw = asNumber(a.price_then ?? a.initial_price ?? null);
                const priceNowNum = priceNowRaw;
                const priceThenNum = priceThenRaw;
                const priceNow = priceNowNum != null ? priceForDisplay(priceNowNum) : "–";
                const priceThen = priceThenNum != null ? priceForDisplay(priceThenNum) : "–";
                const priceLine = (priceNow !== "–" && priceThen !== "–")
                  ? `$${priceNow} from $${priceThen}`
                  : (priceNow !== "–" ? `$${priceNow}` : "");
                // volume (only if it actually exists)
                const volPct = asNumber(a.vol_change_pct ?? a.vol_pct ?? null);
                const volNow = asNumber(a.vol_now ?? null);
                const volThen = asNumber(a.vol_then ?? null);
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
                const hasStructured = pctText !== "–" || priceLine || volLine;
                const lineParts = [
                  headerParts.join(" "),
                  priceLine || null,
                  volLine || null,
                ].filter(Boolean);
                const line = hasStructured ? lineParts.join(" · ") : (a.message || a.title || "");
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
