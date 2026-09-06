import { useEffect, useRef, useState } from "react";
import { getBackendBase } from "../config/api.js";
import { deriveDashboardCadence } from "../config/cadence.js";
import { readGuestItems } from "../context/WatchlistContext.jsx";
import { formatPrice } from "../utils/format.js";
import RiskLevelsChart from "./RiskLevelsChart.jsx";
import ManualRefreshButton from "./ManualRefreshButton.jsx";
import "../styles/sentiment-popup-advanced.css";
import "../styles/portfolio-risk-board.css";

const money = (value) => value == null ? "Unavailable" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
const price = (value) => value == null ? "Unavailable" : formatPrice(value, { fallback: "Unavailable" });
const cadence = deriveDashboardCadence(import.meta.env).PUBLISH_BANNER_MS;

export function RiskLevelCard({ row, source }) {
  const [expanded, setExpanded] = useState(false);
  const plan = row.plan || {};
  const signal = plan.top_signal || {};
  const position = plan.market_structure?.range_position_pct;
  const stopDistance = row.distance_to_stop_pct;
  const resistanceDistance = row.distance_to_resistance_pct;
  return (
    <article className={`mw-panel prb-card prb-card--${row.status}`} aria-label={`${row.symbol} risk levels`}>
      <div className="prb-card__heading">
        <div><h3>{row.symbol}</h3><span className="prb-price">{price(row.price_usd)}</span></div>
        <span className={`prb-chip prb-chip--${row.status}`}>{plan.available ? signal.label : "Unavailable"}</span>
      </div>
      <p className="prb-position">{source === "portfolio"
        ? `${row.quantity == null ? "Unknown quantity" : row.quantity.toLocaleString(undefined, { maximumFractionDigits: 8 }) + " held"} · ${money(row.market_value_usd)}`
        : "Watchlist coin · position size unknown"}</p>
      {plan.available ? <>
        <p className="prb-reason">{signal.reasons?.[0] || signal.action || "No elevated risk cue in the available data."}</p>
        {position != null && Number.isFinite(position) ? <div className="prb-range" role="img" aria-label={`${row.symbol}: ${position.toFixed(0)}% of the recent support-to-resistance range`}>
          <div className="prb-range__labels"><span>Support</span><span>Resistance</span></div>
          <div className="prb-range__track"><span style={{ left: `${Math.min(100, Math.max(0, position))}%` }} /></div>
          <p>{position < 0 ? "Below the measured range" : position > 100 ? "Above the measured range" : `${position.toFixed(0)}% through the measured range`}</p>
        </div> : <p>Range position unavailable</p>}
        <dl className="prb-distances">
          <div><dt>Stop trigger</dt><dd>{stopDistance == null ? "Unavailable" : row.trigger_breached ? "Trigger already reached" : `${Math.abs(stopDistance).toFixed(1)}% below current price`}</dd></div>
          <div><dt>Resistance</dt><dd>{resistanceDistance == null ? "Unavailable" : `${Math.abs(resistanceDistance).toFixed(1)}% ${resistanceDistance >= 0 ? "above" : "below"} current price`}</dd></div>
          {source === "portfolio" && <div><dt>Value down to trigger</dt><dd>{money(row.capital_to_stop_usd)}</dd></div>}
        </dl>
        <button type="button" className="mw-button mw-button--ghost mw-button--sm" aria-expanded={expanded} aria-controls={`risk-chart-${row.product_id}`} onClick={() => setExpanded(!expanded)}>
          {expanded ? "Hide chart" : "Explore levels"}
        </button>
        {expanded && <div id={`risk-chart-${row.product_id}`} className="prb-expanded"><RiskLevelsChart plan={plan} /></div>}
      </> : <p className="prb-unavailable">{plan.reason || "Not enough history yet."}</p>}
    </article>
  );
}

export default function PortfolioRiskBoard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useRef(() => {});
  useEffect(() => {
    let disposed = false;
    let active = null;
    async function load(force = false) {
      if (active || document.hidden) return;
      const controller = new AbortController();
      active = controller;
      const timeout = setTimeout(() => controller.abort(), 60000);
      setLoading(true);
      try {
        const symbols = readGuestItems().map((item) => item.symbol).join(",");
        const query = new URLSearchParams({ symbols, ...(force ? { refresh: "1" } : {}) });
        const response = await fetch(`${getBackendBase()}/api/risk-levels/portfolio?${query}`, { credentials: "include", signal: controller.signal, headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`Could not refresh risk levels (HTTP ${response.status}).`);
        const payload = await response.json();
        if (!Array.isArray(payload.rows) || !payload.summary || !["portfolio", "watchlist"].includes(payload.source)) throw new Error("The risk board response is unavailable.");
        if (!disposed) { setData(payload); setError(""); }
      } catch (cause) {
        if (!disposed) setError(cause.name === "AbortError" ? "Refresh timed out. Try again." : cause.message);
      } finally {
        clearTimeout(timeout);
        active = null;
        if (!disposed) setLoading(false);
      }
    }
    refresh.current = () => load(true);
    const onVisible = () => { if (!document.hidden) load(); };
    const onStorage = (event) => { if (event.key === "mw_watchlist") load(); };
    load();
    const timer = setInterval(load, cadence);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("storage", onStorage);
    return () => { disposed = true; clearInterval(timer); active?.abort(); document.removeEventListener("visibilitychange", onVisible); window.removeEventListener("storage", onStorage); };
  }, []);
  const counts = data?.summary?.counts || {};
  return (
    <main className="prb-page" aria-busy={loading}>
      <header className="prb-header">
        <div><span className="prb-eyebrow">Your risk map</span><h1>Portfolio Risk Board</h1><p>Review support, resistance, and stop distances across your coins.</p></div>
        <fieldset disabled={loading} className="prb-refresh"><ManualRefreshButton onAfterRefresh={() => refresh.current()} /></fieldset>
      </header>
      <div role="status" className="prb-update">{error ? `${error}${data ? " Showing the last snapshot; it may be stale." : ""}` : loading ? "Refreshing risk levels…" : data ? `Updated ${new Date(data.updated_at * 1000).toLocaleTimeString()}` : ""}</div>
      {data?.fallback_reason && <p className="prb-fallback">{data.fallback_reason}</p>}
      {data && <>
        <section className="mw-panel prb-summary" aria-label="Risk summary">
          <div className="prb-counts"><span><strong>{counts.high || 0}</strong> protect now</span><span><strong>{counts.watch || 0}</strong> watch</span><span><strong>{counts.clear || 0}</strong> clear</span><span><strong>{counts.unavailable || 0}</strong> unavailable</span></div>
          <div className="prb-total"><span>Value down to stop triggers</span><strong>{data.source === "portfolio" ? money(data.summary.capital_to_stop_usd) : "Position sizes needed"}</strong></div>
          <p>{data.source === "portfolio" ? `Includes ${data.summary.sized_plan_count} sized positions with available plans. ` : "Watchlist coins have no known position sizes. "}This measures price distance to the triggers, not a guaranteed loss limit. A stop-limit order can remain unfilled.</p>
          {data.summary.excluded_symbols?.length > 0 && <p>Excluded from the dollar total: {data.summary.excluded_symbols.join(", ")}.</p>}
          {data.summary.breached_symbols?.length > 0 && <p>Triggers already reached: {data.summary.breached_symbols.join(", ")}.</p>}
        </section>
        {data.rows.length ? <div className="prb-grid">{data.rows.map((row) => <RiskLevelCard key={row.product_id} row={row} source={data.source} />)}</div>
          : <section className="mw-panel prb-empty"><h2>{data.source === "portfolio" ? "No crypto positions to show" : "No watchlist coins yet"}</h2><p>{data.source === "portfolio" ? "Cash balances do not need crypto risk levels." : "Add coins to your watchlist or connect your Coinbase portfolio."}</p><a href={data.source === "portfolio" ? "/app/portfolio" : "/"} className="mw-button mw-button--ghost">{data.source === "portfolio" ? "Open portfolio" : "Open live board"}</a></section>}
      </>}
    </main>
  );
}
