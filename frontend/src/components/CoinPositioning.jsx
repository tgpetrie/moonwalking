import React from "react";

/*
 * CoinPositioning — per-coin derivatives positioning (funding + OI) from
 * Hyperliquid. Context that qualifies a coin's price case; never a buy/sell
 * signal, and labelled as such. Consumes the shape from
 * backend get_symbol_positioning / holding.intel.positioning.
 *
 * Rendered in two places: the portfolio holdings card (compact) and the
 * SymbolPanel detail. Inline styles keep it consistent across both hosts.
 */

const TONE = {
  favorable: "#45ffb3",
  caution: "#f1b43a",
  adverse: "#ff6b6b",
  neutral: "#a3a3a3",
};

const VENUE_LABELS = { hyperliquid: "Hyperliquid", coinalyze: "Coinalyze" };

function fmtUsd(n) {
  if (n == null || !Number.isFinite(Number(n))) return null;
  const v = Number(n);
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function timeAgo(iso) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return null;
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.round(mins / 60)}h ago`;
}

const pillBase = {
  fontSize: 11.5,
  padding: "2px 8px",
  borderRadius: 6,
  whiteSpace: "nowrap",
};

export default function CoinPositioning({ positioning, compact = false }) {
  const p = positioning || null;

  if (!p || !p.available) {
    return (
      <div
        className="coin-positioning coin-positioning--unavailable"
        style={{ fontSize: compact ? 12 : 13, color: "#8a8a8a", fontStyle: "italic" }}
      >
        No derivatives market
      </div>
    );
  }

  const tone = TONE[p.read_tone] || TONE.neutral;
  const oiUsd = fmtUsd(p.open_interest_usd);
  const oiChange = p.oi_change_pct;
  const venue = VENUE_LABELS[p.venue] || p.venue || "on-chain";
  const ago = timeAgo(p.updated_at);

  return (
    <div className="coin-positioning" data-tone={p.read_tone}>
      <div
        style={{
          fontWeight: 500,
          color: tone,
          fontSize: compact ? 13 : 14,
          lineHeight: 1.4,
        }}
      >
        {p.read}
      </div>
      <div
        style={{
          marginTop: 6,
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          alignItems: "center",
        }}
      >
        <span
          style={{
            ...pillBase,
            background: "rgba(255,255,255,0.06)",
            color: "#d8d8d8",
          }}
        >
          Funding: {p.funding_label}
        </span>
        {oiUsd ? (
          <span style={{ ...pillBase, background: "rgba(255,255,255,0.03)", color: "#a3a3a3" }}>
            OI {oiUsd}
          </span>
        ) : null}
        {oiChange != null ? (
          <span style={{ ...pillBase, background: "rgba(255,255,255,0.03)", color: "#a3a3a3" }}>
            {oiChange >= 0 ? "+" : ""}
            {oiChange}%{p.oi_window_hours ? ` / ${p.oi_window_hours}h` : ""}
          </span>
        ) : null}
      </div>
      <div style={{ marginTop: 6, fontSize: 11, color: "#7a7a7a" }}>
        {venue} · context, not a signal{ago ? ` · updated ${ago}` : ""}
      </div>
    </div>
  );
}
