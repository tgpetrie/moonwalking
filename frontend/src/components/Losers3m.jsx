// src/components/Losers3m.jsx
import React, { useState } from "react";
import TokenRow from "./TokenRow.jsx";
import { useDataFeed } from "../hooks/useDataFeed";

export default function Losers3m({
  rows = [],
  loading = false,
  error = null,
  onInfo = () => {},
  showTitle = true,
}) {
  const { data, isLoading: feedLoading, isError: feedError } = useDataFeed();
  const [isExpanded, setIsExpanded] = useState(false);
  const MAX_BASE = 8;
  const MAX_EXPANDED = 16;
  const feedRows = React.useMemo(() => {
    const list = data?.losers_3m;
    if (Array.isArray(list)) return list;
    if (list && Array.isArray(list.data)) return list.data;
    return [];
  }, [data]);

  const allRows = Array.isArray(rows) && rows.length ? rows : feedRows;

  const losers = React.useMemo(() => {
    return allRows
      .map((row) => {
        const key = "price_change_percentage_3min";
        const raw =
          row?.[key] ??
          row?.gain ??
          0;
        const num = Number(raw);
        const pct = Number.isFinite(num) ? num : 0;
        return { ...row, pct, _pct: pct };
      })
      .filter((r) => Number.isFinite(r._pct) && r._pct < 0)
      .sort((a, b) => a._pct - b._pct);
  }, [allRows]);

  const count = losers.length;
  const visible = isExpanded ? losers.slice(0, MAX_EXPANDED) : losers.slice(0, MAX_BASE);
  const status =
    error || feedError ? "error" :
    count > 0 ? "ready" :
    (loading || feedLoading) ? "loading" :
    "empty";
  const renderHeader = () => {
    if (!showTitle) return null;
    return (
      <header className="panel-header">
        <div className="section-head section-head--center section-head-loss">
          <span className="section-head__label">
            TOP LOSERS <span className="section-head__timeframe">3M</span>
          </span>
          <span className="section-head-line section-head-line-loss" />
        </div>
      </header>
    );
  };

  return (
    <div className="panel panel-3m panel-3m-loss">
      {renderHeader()}
      <div className="panel-body">
        {status === "error" && <div className="panel-error">Failed to load 3m losers.</div>}
        {status === "loading" && <div className="panel-empty">Loading…</div>}
        {status === "ready" ? (
          visible.map((row, idx) => {
            const key = "price_change_percentage_3min";
            const forced = -Math.abs(row.pct ?? row._pct ?? 0);
            const cloned = { ...row, [key]: forced };
            const rank = cloned.rank ?? idx + 1;

            return (
              <TokenRow
                key={row.symbol || idx}
                rank={rank}
                symbol={cloned.symbol}
                currentPrice={cloned.current_price}
                previousPrice={cloned.initial_price_3min}
                changePct={cloned[key]}
                rowType="loser"
                onInfo={onInfo}
              />
            );
          })
        ) : (
          status === "empty" && <div className="panel-empty">No 3-min loser data available.</div>
        )}

        {count > MAX_BASE && (
          <div className="panel-footer">
            <div className="panel-show-more">
              <button
                className="btn-show-more"
                aria-expanded={isExpanded}
                aria-controls="losers-3m-list"
                onClick={() => setIsExpanded((s) => !s)}
              >
                {isExpanded ? "Show Less" : "Show More"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
