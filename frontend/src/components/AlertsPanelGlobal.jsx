import { useEffect, useMemo, useRef, useState } from "react";
import { useData } from "../context/DataContext";
import "../styles/alerts-panel-global.css";

const MW_DEBUG = import.meta.env.VITE_MW_DEBUG === "1";

const CHIPS = [
  "ALL",
  "ACTIVE",
  "DIVERGENCE",
  "IMPULSE",
  "MOONSHOT",
  "BREAKOUT",
  "CRATER",
  "DUMP",
  "MOVE",
  "FOMO",
  "WHALE",
  "SENTIMENT",
  "NEWS",
  "STEALTH",
  "ALERT",
];

const EMOJI_BY_LABEL = {
  ALL: "🧭",
  ACTIVE: "🟢",
  DIVERGENCE: "⚖️",
  IMPULSE: "⚡",
  MOONSHOT: "🚀",
  BREAKOUT: "📈",
  CRATER: "📉",
  DUMP: "🧨",
  MOVE: "🛰️",
  FOMO: "🔥",
  WHALE: "🐋",
  SENTIMENT: "🌊",
  NEWS: "📰",
  STEALTH: "👤",
  ALERT: "🔔",
};

const WINDOW_RE = /_(1M|3M|5M|15M|1H)\b/i;

const toUpper = (value) => String(value || "").trim().toUpperCase();

function coerceTsMs(alert) {
  const n =
    (typeof alert?.event_ts_ms === "number" && Number.isFinite(alert.event_ts_ms) && alert.event_ts_ms) ||
    (typeof alert?.ts_ms === "number" && Number.isFinite(alert.ts_ms) && alert.ts_ms) ||
    (typeof alert?.emitted_ts_ms === "number" && Number.isFinite(alert.emitted_ts_ms) && alert.emitted_ts_ms) ||
    null;
  if (n) return n;
  const parsed = Date.parse(alert?.event_ts || alert?.ts || alert?.emitted_ts || "");
  return Number.isFinite(parsed) ? parsed : Date.now();
}

function formatEvidenceValue(value) {
  if (value == null) return null;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    if (Math.abs(value) >= 1000) return value.toLocaleString();
    if (Math.abs(value) >= 10) return value.toFixed(1);
    return value.toFixed(3).replace(/\.?0+$/, "");
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string") return value;
  return null;
}

function evidenceToChips(evidence) {
  if (!evidence) return [];
  if (Array.isArray(evidence)) {
    return evidence.map((x) => String(x)).filter(Boolean).slice(0, 6);
  }
  if (typeof evidence !== "object") return [];

  const preferred = [
    "window",
    "pct_1m",
    "pct_3m",
    "pct_1h",
    "pct",
    "volume_change_1h_pct",
    "vol_ratio",
    "vol_z",
    "z_vol",
    "heat",
    "mood_label",
    "streak",
  ];
  const keys = [...preferred.filter((k) => k in evidence), ...Object.keys(evidence).filter((k) => !preferred.includes(k))];
  const out = [];
  for (const key of keys) {
    const v = formatEvidenceValue(evidence[key]);
    if (v == null || v === "") continue;
    out.push(`${key}:${v}`);
    if (out.length >= 6) break;
  }
  return out;
}

function labelFromTypeKey(typeKey) {
  const k = String(typeKey || "").toLowerCase();
  if (k.includes("diverg")) return "DIVERGENCE";
  if (k.includes("fomo")) return "FOMO";
  if (k.includes("whale")) return "WHALE";
  if (k.includes("sentiment")) return "SENTIMENT";
  if (k.includes("news")) return "NEWS";
  if (k.includes("stealth")) return "STEALTH";
  if (k.includes("moon")) return "MOONSHOT";
  if (k.includes("break")) return "BREAKOUT";
  if (k.includes("crater")) return "CRATER";
  if (k.includes("dump")) return "DUMP";
  if (k.includes("impulse")) return "IMPULSE";
  if (k.includes("volatility") || k.includes("expansion")) return "MOVE";
  if (k.includes("breadth") || k.includes("failure")) return "MOVE";
  if (k.includes("move")) return "MOVE";
  return "ALERT";
}

function getTypeKeyLoose(alert) {
  const direct =
    alert?.type_key ??
    alert?.typeKey ??
    alert?.class_key ??
    alert?.classKey ??
    alert?.alert_type ??
    alert?.alertType ??
    alert?.type ??
    alert?.kind ??
    alert?.category ??
    alert?.family ??
    alert?.name ??
    null;
  if (direct != null && String(direct).trim()) return String(direct);

  const msg = String(alert?.message ?? alert?.title ?? alert?.text ?? "").trim();
  if (msg) return msg;

  return "ALERT";
}

function typeDisplay(label) {
  const emoji = EMOJI_BY_LABEL[label] || EMOJI_BY_LABEL.ALERT;
  return `${emoji} ${label}`;
}

function windowLabel(alert) {
  if (alert?.window) return String(alert.window).toLowerCase();
  const fromEvidence = alert?.evidence?.window;
  if (fromEvidence) return String(fromEvidence).toLowerCase();
  const match = String(alert?.type_key || "").match(WINDOW_RE);
  return match ? match[1].toLowerCase() : "";
}

function severityClass(sev) {
  const s = String(sev || "").toLowerCase();
  if (s === "critical") return "critical";
  if (s === "high") return "high";
  if (s === "medium") return "medium";
  if (s === "low") return "low";
  return "info";
}

function fmtTime(tsMs) {
  try {
    return new Date(tsMs).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "";
  }
}

function normalizeAlertForPanel(alert) {
  if (!alert || typeof alert !== "object") return null;

  const rawProduct = alert.product_id ?? alert.productId ?? alert.pair ?? "";
  const rawSymbol = alert.symbol ?? alert.ticker ?? rawProduct ?? "";

  const productInput = toUpper(rawProduct);
  const symbolInput = toUpper(rawSymbol);

  let product_id = "";
  if (productInput.includes("-")) product_id = productInput;
  else if (symbolInput.includes("-")) product_id = symbolInput;
  else if (symbolInput) product_id = `${symbolInput}-USD`;

  const symbol = (product_id || symbolInput).split("-", 1)[0] || "";
  const type_key = getTypeKeyLoose(alert);
  const severity = String(alert.severity ?? alert.level ?? alert.sev ?? "info").toLowerCase();
  const title = String(alert.title ?? alert.headline ?? "");
  const message = String(alert.message ?? alert.text ?? alert.raw ?? "");

  const matchPct = message.match(/([+-]?\d+(\.\d+)?)\s*%/);
  const pct = matchPct ? Number(matchPct[1]) : (typeof alert.pct === "number" ? alert.pct : null);
  const ts_ms = coerceTsMs(alert);
  const evidence = evidenceToChips(alert.evidence);
  const window = windowLabel(alert);
  const source = String(alert.source ?? alert.origin ?? alert.feed ?? "cb")
    .trim()
    .toLowerCase();

  return {
    id: String(alert.id ?? `${type_key}:${product_id}:${ts_ms}`),
    symbol,
    product_id,
    type_key,
    severity,
    title,
    message,
    pct: Number.isFinite(pct) ? pct : null,
    ts_ms,
    evidence,
    window,
    source: source || "cb",
    trade_url: alert.trade_url || null,
    href: alert.href ?? alert.url ?? null,
  };
}







































































































































































































































































































































































































































































































































































































































































































































































































































































































































      <div className="mw-alerts-global__list">
        {filtered.length === 0 ? (
          <div className="mw-alerts-global__empty">
            No alerts match this filter. (recent={recentCount}, active={activeCount}, data.alerts={embeddedCount})
          </div>
        ) : (
          filtered.map((a) => {
            const looseTypeKey = getTypeKeyLoose(a);
            const lbl = labelFromTypeKey(looseTypeKey);
            const sevClass = severityClass(a.severity);
            const win = a.window ? ` · ${a.window}` : "";
            const tradeLink = a.trade_url || coinbaseLink(a.product_id);
            return (
              <article key={`${a.id}-${a.ts_ms}`} className={`mw-alert-row severity-${sevClass}`}>
                <div className="mw-alert-row__top">
                  <span className="mw-alert-pill type">{typeDisplay(lbl)}{win}</span>
                  <span className={`mw-alert-pill sev ${sevClass}`}>{sevClass}</span>
                  <span className={`mw-alert-pill src ${(a.source || "cb") === "external" ? "external" : "cb"}`}>
                    {(a.source || "cb") === "external" ? "EXT" : "CB"}
                  </span>
                  {a.symbol ? <span className="mw-alert-row__sym">{a.symbol}</span> : null}
                  <span className="mw-alert-row__time">{fmtTime(a.ts_ms)}</span>
                </div>

                {a.title ? <div className="mw-alert-row__title">{a.title}</div> : null}
                {a.message ? <div className="mw-alert-row__msg">{a.message}</div> : null}
                {MW_DEBUG ? (
                  <div className="mw-alert-row__msg" style={{ marginTop: "-0.15rem", opacity: 0.7 }}>
                    type_key={String(a.type_key)} · loose={looseTypeKey}
                  </div>
                ) : null}

                <div className="mw-alert-row__actions">
                  {tradeLink ? (
                    <a href={tradeLink} target="_blank" rel="noreferrer">
                      Advanced Trade
                    </a>
                  ) : null}
                  {a.href ? (
                    <a href={a.href} target="_blank" rel="noreferrer">
                      Source
                    </a>
                  ) : null}
                </div>

                {a.evidence?.length ? (
                  <div className="mw-alert-row__evidence">
                    {a.evidence.map((e, idx) => (
                      <span key={`${a.id}-${idx}`} className="mw-evidence-chip">{e}</span>
                    ))}
                  </div>
                ) : null}
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
