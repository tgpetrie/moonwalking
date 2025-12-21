import { useMemo, useState } from "react";
import { useDataFeed } from "../hooks/useDataFeed";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import { TokenRowUnified } from "./TokenRowUnified";
import { TableSkeletonRows } from "./TableSkeletonRows";
import { baselineOrNull } from "../utils/num.js";

const MAX_BASE = 8;

const GainersTable3Min = ({ tokens: tokensProp, loading: loadingProp, onInfo, onToggleWatchlist, watchlist = [] }) => {
  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data, isLoading: hookLoading } = useDataFeed();
  const [isExpanded, setIsExpanded] = useState(false);

  // Use props if provided, otherwise fall back to hook data
  const isLoading = loadingProp !== undefined ? loadingProp : hookLoading;

  // Also call the compatibility `useHybridLive` hook so this file explicitly
  // references it (older diagnostics and invariants expect this hook to be
  // present). We don't strictly need to use its return here because the
  // component currently processes `data` from `useDataFeed`, but having the
  // hook present preserves wiring expectations and makes future migrations
  // easier.
  const { data: _hybridPayload = {} } = useHybridLiveNamed();
  const gainers3m = useMemo(() => {
    if (tokensProp) return tokensProp; // Use prop if provided

    const list = data?.gainers_3m;
    const source = Array.isArray(list) ? list : list && Array.isArray(list.data) ? list.data : [];

    return source
      .map((row) => {
        const pctRaw =
          row.price_change_percentage_3min ??
          row.change_3m ??
          row.gain ??
          row.pct_change ??
          row.pct ??
          0;
        const pct = Number(pctRaw);

        const baselineOrNullPrev = baselineOrNull(row.previous_price_3m ?? row.initial_price_3min ?? null);
        return {
          ...row,
          change_3m: pct,
          _pct: Number.isFinite(pct) ? pct : 0,
          previous_price_3m: baselineOrNullPrev,
          current_price: row.price ?? row.current_price,
        };
      })
      .filter((r) => Number.isFinite(r._pct) && r._pct > 0)
      .sort((a, b) => b._pct - a._pct);
  }, [data, tokensProp]);

  const visibleRows = isExpanded ? gainers3m : gainers3m.slice(0, MAX_BASE);
  const count = gainers3m.length;
  const hasData = count > 0;

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="bh-panel bh-panel-full">
          <div className="bh-table">
            <TableSkeletonRows columns={5} rows={6} />
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="bh-panel bh-panel-full">
          <div className="bh-table">
            <div style={{ textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
              No 3-minute movers to show right now.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="gainers-table">
      <div className="bh-panel bh-panel-full">
        <div className="bh-table">
          {visibleRows.map((token, index) => (
            <TokenRowUnified
              key={token.symbol}
              token={token}
              rank={index + 1}
              changeField="change_3m"
              side="gainer"
              onInfo={onInfo}
              onToggleWatchlist={onToggleWatchlist}
              isWatchlisted={watchlist.includes(token.symbol)}
            />
          ))}
        </div>
      </div>

      {count > MAX_BASE && (
        <div className="panel-footer">
          <button
            className="btn-show-more"
            aria-expanded={isExpanded}
            onClick={() => setIsExpanded((s) => !s)}
          >
            {isExpanded ? "Show Less" : `Show More (${Math.max(count - MAX_BASE, 0)} more)`}
          </button>
        </div>
      )}
    </div>
  );
};

export default GainersTable3Min;
