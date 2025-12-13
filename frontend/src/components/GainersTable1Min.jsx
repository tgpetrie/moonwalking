import { useMemo, useState } from "react";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";
import { TableSkeletonRows } from "./TableSkeletonRows";

export default function GainersTable1Min({ tokens: tokensProp, loading: loadingProp, onInfo, onToggleWatchlist, watchlist = [] }) {
  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data, isLoading: hookLoading } = useDataFeed();

  // Use props if provided, otherwise fall back to hook data
  const isLoading = loadingProp !== undefined ? loadingProp : hookLoading;

  const gainers1m = useMemo(() => {
    if (tokensProp) return tokensProp; // Use prop if provided

    const list = data?.gainers_1m;
    const source = Array.isArray(list)
      ? list
      : list && Array.isArray(list.data)
      ? list.data
      : [];

    return source
      .map((row) => ({
        ...row,
        change_1m:
          row.change_1m ??
          row.price_change_percentage_1min ??
          row.pct_change ??
          row.pct ??
          row.changePct ??
          0,
        previous_price_1m:
          row.previous_price_1m ??
          row.price_1m_ago ??
          row.previous_price ??
          row.prev_price ??
          row.initial_price_1min ??
          null,
        current_price: row.price ?? row.current_price ?? row.current,
      }))
      .filter((r) => Number(r.change_1m) > 0)
      .sort((a, b) => Number(b.change_1m) - Number(a.change_1m));
  }, [data, tokensProp]);

  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded ? gainers1m : gainers1m.slice(0, 8);

  const hasData = gainers1m.length > 0;

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="bh-panel bh-panel-half">
        <div className="bh-table">
          {/* Use div-based skeleton rows to match TokenRowUnified rendering */}
          <TableSkeletonRows columns={5} rows={6} />
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="bh-panel bh-panel-half">
        <div className="bh-table">
          <div className="token-row token-row--empty">
            <div style={{ width: "100%", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
              No 1-minute movers to show right now.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const MAX_ROWS_PER_COLUMN = 4;
  const MAX_VISIBLE = MAX_ROWS_PER_COLUMN * 2;
  const grids = [];

  for (let i = 0; i < visibleItems.length; i += MAX_VISIBLE) {
    grids.push({
      rows: visibleItems.slice(i, i + MAX_VISIBLE),
      offset: i,
    });
  }

  return (
    <>
      <div className="bh-panel bh-panel-half">
        <div className="bh-table">
          {grids.map(({ rows, offset }, gridIndex) => {
            const total = rows.length;
            const hasSecondColumn = total > MAX_ROWS_PER_COLUMN;
            const density = hasSecondColumn ? "normal" : "tight";
            const visibleTokens = hasSecondColumn
              ? rows.slice(0, MAX_VISIBLE)
              : rows.slice(0, MAX_ROWS_PER_COLUMN);
            const leftColumn = visibleTokens.slice(0, MAX_ROWS_PER_COLUMN);
            const rightColumn = visibleTokens.slice(MAX_ROWS_PER_COLUMN);

            return (
              <div
                key={`bh-1m-grid-${gridIndex}`}
                className={
                  hasSecondColumn
                    ? "bh-1m-grid bh-1m-grid--two-col"
                    : "bh-1m-grid bh-1m-grid--single-col"
                }
              >
                <div className="bh-1m-col">
                  {leftColumn.map((token, index) => (
                    <TokenRowUnified
                      key={token.symbol ?? `${token.base}-${offset + index}`}
                      token={token}
                      rank={offset + index + 1}
                      changeField="change_1m"
                      onInfo={onInfo}
                      onToggleWatchlist={onToggleWatchlist}
                      isWatchlisted={watchlist.includes(token.symbol)}
                      density={density}
                    />
                  ))}
                </div>

                {hasSecondColumn && (
                  <div className="bh-1m-col">
                    {rightColumn.map((token, index) => (
                      <TokenRowUnified
                        key={token.symbol ?? `${token.base}-r${offset + index}`}
                        token={token}
                        rank={offset + MAX_ROWS_PER_COLUMN + index + 1}
                        changeField="change_1m"
                        onInfo={onInfo}
                        onToggleWatchlist={onToggleWatchlist}
                        isWatchlisted={watchlist.includes(token.symbol)}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      {gainers1m.length > 8 && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
            {expanded ? "Show less" : `Show more (${gainers1m.length - 8} more)`}
          </button>
        </div>
      )}
    </>
  );
}
