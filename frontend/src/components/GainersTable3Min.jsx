import React, { useMemo, useState } from "react";
import TokenRow from "./TokenRow.jsx";
import { useDataFeed } from "../hooks/useDataFeed";

const MAX_BASE = 8;
const MAX_EXPANDED = 16;

const GainersTable3Min = ({ rows = [], loading = false, error = null, onInfo }) => {
  const { data, isLoading: feedLoading, isError: feedError } = useDataFeed();
  const renderHeader = () => (
    <header className="panel-header">
      <div className="section-head section-head--center section-head-gain">
        <span className="section-head__label">
          TOP GAINERS <span className="section-head__timeframe">3M</span>
        </span>
        <span className="section-head-line section-head-line-gain" />
      </div>
    </header>
  );

  const [isExpanded, setIsExpanded] = useState(false);
  const feedRows = React.useMemo(() => {
    const list = data?.gainers_3m;
    if (Array.isArray(list)) return list;
    if (list && Array.isArray(list.data)) return list.data;
    return [];
  }, [data]);

  const allRows = Array.isArray(rows) && rows.length ? rows : feedRows;

  const gainers = useMemo(() => {
    return allRows
      .map((row) => {
        const pctRaw =
          row.price_change_percentage_3min ??
          row.change_3m ??
          row.gain ??
          row.pct_change ??
          row.pct ??
          0;
        const pct = Number(pctRaw);
        return {
          ...row,
          pct,
          _pct: Number.isFinite(pct) ? pct : 0,
        };
      })
      .filter((r) => Number.isFinite(r._pct) && r._pct > 0)
      .sort((a, b) => b._pct - a._pct);
  }, [allRows]);

  const visibleRows = isExpanded
    ? gainers.slice(0, MAX_EXPANDED)
    : gainers.slice(0, MAX_BASE);
  const count = gainers.length;
  const status =
    error || feedError ? "error" :
    count > 0 ? "ready" :
    (loading || feedLoading) ? "loading" :
    "empty";

  return (
    <section className="panel panel-3m">
      {renderHeader()}
      <div className="panel-body">
        {status === "error" && <div className="panel-error">Failed to load 3m gainers.</div>}
        {status === "loading" && <div className="panel-loading">Loading…</div>}
        {status === "ready" ? (
          visibleRows.map((row, index) => (
            <TokenRow
              key={row.symbol || index}
              rank={row.rank ?? index + 1}
              symbol={row.symbol}
              currentPrice={row.current_price}
              previousPrice={row.initial_price_3min}
              changePct={row.pct}
              rowType="gainer"
              onInfo={onInfo}
            />
          ))
        ) : (
          status === "empty" && <div className="panel-empty">No 3m gainers yet.</div>
        )}

        {count > MAX_BASE && (
          <div className="panel-footer">
            <div className="panel-show-more">
              <button
                className="btn-show-more"
                aria-expanded={isExpanded}
                aria-controls="gainers-3m-list"
                onClick={() => setIsExpanded((s) => !s)}
              >
                {isExpanded ? "Show Less" : "Show More"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default GainersTable3Min;
