import React from "react";

/*
 * MarketPositioningStatus
 * -----------------------
 * A deliberately small, unobtrusive block that reports the health of the
 * derivatives / market-positioning source (funding rate + open interest across
 * Binance / OKX / Bybit). It is context, not a buy/sell signal.
 *
 * Product rules honored here:
 * - Show provenance, freshness, and failure state.
 * - Never present an unavailable source as live (driven by `positioning.available`).
 * - Plain labels, no slang.
 *
 * It consumes the `marketPositioning` object produced by normalizeSentiment.js.
 */

const EXCHANGE_LABELS = {
  binance: "Binance",
  okx: "OKX",
  bybit: "Bybit",
  hyperliquid: "Hyperliquid",
  coinalyze: "Coinalyze",
};

const labelFor = (id) => {
  const key = String(id || "").toLowerCase();
  if (EXCHANGE_LABELS[key]) return EXCHANGE_LABELS[key];
  return key ? key.charAt(0).toUpperCase() + key.slice(1) : "";
};

/**
 * Turn the raw backend funding-bias enum into human-readable context copy.
 *
 * This is the product-voice decision point for this feature: the backend emits
 * neutral machine values (`longs_pay`, `shorts_pay`, `neutral`, `unknown`) and
 * the phrasing below is intentionally descriptive rather than directional so it
 * never reads as a trade recommendation. Tune the wording here if the desired
 * tone changes.
 */
export function describeFundingBias(bias) {
  switch (String(bias || "").toLowerCase()) {
    case "longs_pay":
      return "Longs paying (crowd leaning long)";
    case "shorts_pay":
      return "Shorts paying (crowd leaning short)";
    case "neutral":
      return "Neutral";
    default:
      return "Unknown";
  }
}

/**
 * Build the ordered per-exchange status list, e.g.
 *   [{ id: "okx", label: "OKX", state: "live" }, ...]
 * Live exchanges are listed first so the working sources read at a glance.
 */
export function exchangeStatuses(positioning) {
  const lower = (list) => (list || []).map((x) => String(x).toLowerCase());
  const live = new Set(lower(positioning.liveExchanges));
  const blocked = new Set(lower(positioning.blockedExchanges));
  const failed = new Set(lower(positioning.failedExchanges));

  const universe = positioning.configuredExchanges?.length
    ? positioning.configuredExchanges
    : [
        ...positioning.liveExchanges,
        ...positioning.blockedExchanges,
        ...positioning.failedExchanges,
      ];

  const seen = new Set();
  const rows = [];
  for (const raw of universe) {
    const id = String(raw).toLowerCase();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    let state = "unknown";
    if (live.has(id)) state = "live";
    else if (blocked.has(id)) state = "blocked";
    else if (failed.has(id)) state = "failed";
    rows.push({ id, label: labelFor(id), state });
  }

  const rank = { live: 0, blocked: 1, failed: 1, unknown: 2 };
  return rows.sort((a, b) => rank[a.state] - rank[b.state]);
}

export default function MarketPositioningStatus({ positioning }) {
  const p = positioning || null;

  // Unavailable / no live exchanges: state it plainly, do NOT imply live data.
  if (!p || !p.available) {
    return (
      <div
        className="mw-positioning mw-positioning--unavailable"
        data-status="UNAVAILABLE"
      >
        <div className="mw-positioning__row">
          <span className="mw-positioning__label">Market positioning</span>
          <span className="mw-positioning__value">Unavailable</span>
        </div>
      </div>
    );
  }

  const statuses = exchangeStatuses(p);
  const statusText = statuses
    .map((s) => `${s.label} ${s.state}`)
    .join(", ");

  return (
    <div
      className={`mw-positioning mw-positioning--${p.status.toLowerCase()}`}
      data-status={p.status}
    >
      <div className="mw-positioning__row">
        <span className="mw-positioning__label">Market positioning</span>
        <span className="mw-positioning__value">
          {statusText}
          {p.stale ? " · stale" : ""}
        </span>
      </div>
      <div className="mw-positioning__row">
        <span className="mw-positioning__label">Funding bias</span>
        <span className="mw-positioning__value">
          {describeFundingBias(p.fundingBias)}
        </span>
      </div>
      <div className="mw-positioning__row">
        <span className="mw-positioning__label">Coverage</span>
        <span className="mw-positioning__value">
          {p.coverageLive}/{p.coverageTotal} exchanges
        </span>
      </div>
    </div>
  );
}
