import { useState } from "react";
import { useMacroCycleScan } from "../hooks/useMacroCycleScan.js";
import { plainPrice } from "./WaveStructureOverlay.jsx";
import "../styles/industry-pulse.css";

/*
 * IndustryPulse
 * -------------
 * Compact read of GET /api/macro-cycle-scan on the main board: the liquidity
 * rotation stage (1–4) with its gate, breadth across the scanned coins, and
 * the four ranked cycle buckets as a filter.
 *
 * Display context only. The backend marks the scan `blocks_alerts: false` and
 * `outcome_validated: false`; the panel says so and never ranks or hides a
 * board row. A missing read renders as warming/unavailable, never as a value.
 */

export const CYCLE_BUCKETS = [
  { key: "deep_accumulation_exhaustion", label: "Deep Accumulation" },
  { key: "low_confirmation_breakout", label: "Confirmation Breakout" },
  { key: "growth_expansion_ride", label: "Growth Expansion" },
  { key: "rollover_profit_zone", label: "Rollover Zone" },
];

export const BREADTH_METRICS = [
  { key: "pct_monthly_exhausted", label: "1M Exhausted", detail: "Share of scanned coins in a monthly bear streak of 18+ months with the negative monthly MACD histogram shrinking" },
  { key: "pct_weekly_rsi_above_60", label: "1W RSI > 60", detail: "Share of scanned coins with weekly RSI above 60" },
  { key: "pct_above_50w_sma", label: "Above 50W SMA", detail: "Share of scanned coins trading above their 50-week average" },
];

const GATE_TONE = { risk_on_aligned: "ok", neutral_chop: "neutral", risk_off_headwind: "danger" };
const GATE_LABEL = { risk_on_aligned: "Risk-on aligned", neutral_chop: "Neutral chop", risk_off_headwind: "Risk-off headwind" };

const UNAVAILABLE_REASON = {
  warming: "Daily histories are still loading.",
  btc_history_unavailable: "BTC daily history is unavailable.",
  alt_index_unavailable: "Too few altcoins with history to build the index.",
  not_enough_weekly_history: "Not enough weekly history yet.",
  regime_failed: "The stage read failed.",
};

const RSI_REGIME = {
  oversold_compression: "oversold compression",
  no_mans_land: "no-man's-land",
  growth_expansion: "expansion",
};

const finite = (value) => typeof value === "number" && Number.isFinite(value);
const one = (value) => (finite(value) ? value.toFixed(1).replace(/\.0$/, "") : null);
const signed = (value) => (finite(value) ? `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)}%` : null);

export function breadthText(share) {
  if (!share || !finite(share.pct)) return "—";
  return `${Math.round(share.pct)}%`;
}

/** The one number and the short note a coin shows inside a bucket. */
export function coinFacts(row, bucket) {
  const rsi = one(row?.weekly_rsi);
  const rsiNote = rsi ? `1W RSI ${rsi}` : "1W RSI —";
  if (bucket === "deep_accumulation_exhaustion") {
    const streak = finite(row?.monthly_bearish_streak) ? `${row.monthly_bearish_streak} mo` : "—";
    return { metric: streak, note: row?.multi_year_oversold_exhaustion ? "1M exhausted" : rsiNote };
  }
  if (bucket === "low_confirmation_breakout") {
    return { metric: rsi || "—", note: row?.weekly_macd_bullish_cross ? "broke pivot · 1W MACD cross" : "broke pivot" };
  }
  if (bucket === "rollover_profit_zone") {
    return { metric: signed(row?.pct_from_cycle_high) || "—", note: "from cycle high" };
  }
  return { metric: rsi || "—", note: row?.above_50w_sma ? "above 50W SMA" : "1W RSI" };
}

function coinTitle(row) {
  const parts = [`${row.symbol}${plainPrice(row.price) ? ` · ${plainPrice(row.price)}` : ""}`];
  if (finite(row.weekly_rsi)) parts.push(`1W RSI ${one(row.weekly_rsi)}${RSI_REGIME[row.weekly_rsi_regime] ? ` (${RSI_REGIME[row.weekly_rsi_regime]})` : ""}`);
  if (finite(row.monthly_bearish_streak)) parts.push(`monthly bear streak ${row.monthly_bearish_streak}`);
  if (finite(row.pct_from_cycle_high)) parts.push(`${signed(row.pct_from_cycle_high)} from cycle high`);
  const pivot = row.low_confirmation_pivot;
  if (pivot && plainPrice(pivot.price)) parts.push(`confirmation pivot ${plainPrice(pivot.price)}`);
  const stop = row.accumulation_invalidation_stop;
  if (stop && plainPrice(stop.stop_price)) parts.push(`accumulation read invalid below ${plainPrice(stop.stop_price)}`);
  return parts.join(" · ");
}

function timeLabel(seconds) {
  if (!finite(seconds) || seconds <= 0) return null;
  return new Date(seconds * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const VISIBLE_COINS = 8;

export function IndustryPulseView({ scan, loading = false, error = null, onInfo }) {
  const [picked, setPicked] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const head = (note) => (
    <div className="bh-pulse__head">
      <span className="bh-pulse__title">Industry Pulse</span>
      <span className="bh-pulse__sub">cycle scanner · multi-year daily candles</span>
      {note ? <span className="bh-pulse__asof">{note}</span> : null}
    </div>
  );

  if (!scan) {
    const status = loading ? "LOADING" : "UNAVAILABLE";
    return (
      <section className="bh-pulse" aria-label="Industry pulse and cycle scanner" data-testid="industry-pulse" data-status={status}>
        {head()}
        <p className="bh-pulse__state">{loading ? "Reading the industry cycle…" : "Industry pulse unavailable."}</p>
      </section>
    );
  }

  const warming = scan.status === "warming";
  const industry = scan.industry || {};
  const breadth = scan.breadth || null;
  const buckets = scan.buckets || {};
  const rowsFor = (key) => (Array.isArray(buckets[key]) ? buckets[key] : []);
  const firstFilled = CYCLE_BUCKETS.find((b) => rowsFor(b.key).length)?.key || CYCLE_BUCKETS[0].key;
  const active = picked || firstFilled;
  const rows = rowsFor(active);
  const shown = expanded ? rows : rows.slice(0, VISIBLE_COINS);
  const stage = industry.available && finite(industry.stage_number) ? industry.stage_number : null;
  const gate = industry.available ? industry.macro_regime_gate : null;
  const asOf = timeLabel(scan.computed_at);
  const note = [asOf ? `as of ${asOf}` : null, scan.status === "refreshing" ? "refreshing" : null, error ? "last update failed" : null]
    .filter(Boolean).join(" · ");
  const skipped = Array.isArray(scan.skipped) ? scan.skipped.length : 0;
  const members = industry.alt_index?.member_count;

  if (warming) {
    return (
      <section className="bh-pulse" aria-label="Industry pulse and cycle scanner" data-testid="industry-pulse" data-status="WARMING">
        {head()}
        <p className="bh-pulse__state">Warming up · daily histories are loading. This fills in on its own.</p>
      </section>
    );
  }

  return (
    <section className="bh-pulse" aria-label="Industry pulse and cycle scanner" data-testid="industry-pulse"
      data-status={scan.status === "refreshing" ? "REFRESHING" : "READY"}>
      {head(note)}

      <div className="bh-pulse__summary">
        <div className="bh-pulse__stage" data-testid="industry-pulse-stage" data-stage={stage ?? "none"}
          title={(industry.reasons || []).join(" ")}>
          <span className="bh-pulse__steps" aria-hidden="true">
            {[1, 2, 3, 4].map((n) => (
              <span key={n} className={`bh-pulse__step${stage === n ? " is-active" : ""}${stage && n < stage ? " is-past" : ""}`}>{n}</span>
            ))}
          </span>
          <span className="bh-pulse__stage-copy">
            <strong className="bh-pulse__stage-label">
              {stage ? industry.stage_label || `Stage ${stage}` : "Stage unavailable"}
            </strong>
            <span className="bh-pulse__stage-why">
              {stage
                ? (industry.reasons || [])[0] || "Liquidity rotation stage, 1 to 4."
                : UNAVAILABLE_REASON[industry.reason] || "The stage could not be read."}
            </span>
          </span>
          {gate ? (
            <span className={`bh-pulse__gate bh-pulse__gate--${GATE_TONE[gate] || "neutral"}`} data-testid="industry-pulse-gate" data-gate={gate}
              title={(industry.reasons || []).slice(-1)[0] || undefined}>
              {industry.gate_label || GATE_LABEL[gate] || gate}
            </span>
          ) : null}
        </div>

        <dl className="bh-pulse__breadth" data-testid="industry-pulse-breadth">
          {BREADTH_METRICS.map((metric) => {
            const share = breadth?.[metric.key];
            return (
              <div key={metric.key} className="bh-pulse__metric" title={metric.detail} data-testid={`industry-pulse-${metric.key}`}>
                <dt>{metric.label}</dt>
                <dd>
                  <strong>{breadthText(share)}</strong>
                  <span>{share && finite(share.of) && share.of > 0 ? `${share.count} of ${share.of}` : "no read"}</span>
                </dd>
              </div>
            );
          })}
        </dl>
      </div>

      <div className="bh-pulse__filter" role="group" aria-label="Cycle bucket" data-testid="industry-pulse-buckets">
        {CYCLE_BUCKETS.map((bucket) => (
          <button key={bucket.key} type="button" className={`bh-pulse__bucket${active === bucket.key ? " is-active" : ""}`}
            aria-pressed={active === bucket.key} title={scan.bucket_labels?.[bucket.key] || bucket.label}
            onClick={() => { setPicked(bucket.key); setExpanded(false); }}>
            <span>{bucket.label}</span>
            <span className="bh-pulse__count">{rowsFor(bucket.key).length}</span>
          </button>
        ))}
      </div>

      {rows.length ? (
        <div className="bh-pulse__coins" data-testid="industry-pulse-coins">
          {shown.map((row, index) => {
            const facts = coinFacts(row, active);
            return (
              <button key={row.product_id || row.symbol} type="button" className="bh-pulse__coin" title={coinTitle(row)}
                onClick={() => onInfo?.(row.symbol)}>
                <span className="bh-pulse__rank">{index + 1}</span>
                <span className="bh-pulse__symbol">{row.symbol}</span>
                <span className="bh-pulse__value">{facts.metric}</span>
                <span className="bh-pulse__note">{facts.note}</span>
              </button>
            );
          })}
          {rows.length > VISIBLE_COINS ? (
            <button type="button" className="bh-pulse__more" onClick={() => setExpanded((open) => !open)}>
              {expanded ? "Show fewer" : `Show all ${rows.length}`}
            </button>
          ) : null}
        </div>
      ) : (
        <p className="bh-pulse__state" data-testid="industry-pulse-empty">No scanned coin is in this bucket right now.</p>
      )}

      <p className="bh-pulse__foot">
        Context only · rules of thumb, not tested against outcomes · does not block board alerts
        {finite(scan.scanned) ? ` · ${scan.scanned} coins read` : ""}
        {skipped ? ` · ${skipped} skipped (too little history)` : ""}
        {finite(members) ? ` · alt index: equal-weight proxy of ${members} coins, not market-cap weighted` : ""}
      </p>
    </section>
  );
}

/** `scanState` lets a parent share one scan poll with other panels. */
export default function IndustryPulse({ symbols = [], onInfo, scanState = null }) {
  const own = useMacroCycleScan(symbols, { enabled: !scanState });
  const { scan, loading, error } = scanState || own;
  return <IndustryPulseView scan={scan} loading={loading} error={error} onInfo={onInfo} />;
}
