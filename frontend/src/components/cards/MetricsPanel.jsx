import React from "react";

export default function MetricsPanel({ row, interval = "3m" }) {
  if (!row) return null;

  const symbol = (row.symbol || "")
    .replace(/-USDT?$/i, "")
    .replace(/-USD$/i, "");

  const price = row.current_price;
  const prev =
    row.initial_price_3min ??
    row.initial_price_1min ??
    row.initial_price ??
    null;

  const pct =
    row.price_change_percentage_3min ??
    row.price_change_percentage_1min ??
    null;

  const isLoss = typeof pct === "number" && pct < 0;

  return (
    <aside className="metrics-panel">
      <div className="metrics-head">
        <div className="metrics-title">{symbol || "—"}</div>
        <div className={`metrics-tag ${interval === "1m" ? "is-gain" : "is-loss"}`}>
          {interval}
        </div>
      </div>

      <div className="metrics-price-block">
        <div className="metrics-price">
          {price != null ? `$${Number(price).toFixed(4)}` : "--"}
        </div>
        <div className="metrics-prev">
          {prev != null ? `$${Number(prev).toFixed(4)}` : ""}
        </div>
      </div>

      <div className="metrics-row">
        <span className="metrics-label">Change</span>
        <span className={isLoss ? "metrics-val loss" : "metrics-val gain"}>
          {pct != null ? `${pct.toFixed(3)}%` : "--"}
        </span>
      </div>

      {row.trend_direction ? (
        <div className="metrics-row">
          <span className="metrics-label">Trend</span>
          <span className="metrics-val">{row.trend_direction}</span>
        </div>
      ) : null}

      {row.trend_score != null ? (
        <div className="metrics-row">
          <span className="metrics-label">Score</span>
          <span className="metrics-val">{row.trend_score}</span>
        </div>
      ) : null}

      {row.alert_level ? (
        <div className="metrics-row">
          <span className="metrics-label">Alert</span>
          <span className="metrics-val">{row.alert_level}</span>
        </div>
      ) : null}

      {row.actual_interval_minutes ? (
        <div className="metrics-foot">last {row.actual_interval_minutes}m snapshot</div>
      ) : null}
    </aside>
  );
}
