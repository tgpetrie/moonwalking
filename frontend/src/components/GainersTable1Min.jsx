import React, { useMemo, useState } from "react";
import TokenRow from "./TokenRow.jsx";

export default function GainersTable1Min({
  rows = [],
  loading,
  error,
  onInfo,
}) {
  const [showMore, setShowMore] = useState(false);
  const allRows = Array.isArray(rows) ? rows : [];

  const normalizedRows = useMemo(() => {
    return allRows
      .map((row) => {
        const pctRaw =
          row.price_change_percentage_1min ??
          row.change_1m ??
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

  const total = normalizedRows.length;
  const visibleCount = showMore
    ? Math.min(total, 16)
    : Math.min(total, 8);

  // Visible slice in canonical rank order (1..N)
  const { visibleRows, leftRows, rightRows, hasFew } = useMemo(() => {
    const slice = normalizedRows.slice(0, visibleCount);

    const withRank = slice.map((row, index) => {
      const displayRank =
        row.rank && row.rank >= 1 ? row.rank : index + 1;
      return { ...row, displayRank };
    });

    const few = withRank.length <= 4;

    // Canonical split:
    // - Collapsed: up to 4 rows in left, 4 in right (5–8).
    // - Expanded: up to 8 rows in left, remaining (9–16) in right.
    const leftLimit = showMore
      ? Math.min(8, withRank.length)
      : Math.min(4, withRank.length);

    const left = withRank.slice(0, leftLimit);
    const right = withRank.slice(leftLimit);

    return {
      visibleRows: withRank,
      leftRows: left,
      rightRows: right,
      hasFew: few,
    };
  }, [normalizedRows, visibleCount, showMore]);

  if (error) {
    return (
      <section className="panel panel-1m panel-1m-gainers">
        <div className="panel-header">
          <h2 className="panel-title">1-MIN GAINERS</h2>
          <div className="panel-line" />
        </div>
        <div className="panel-body">
          <div className="panel-empty">Failed to load 1m gainers.</div>
        </div>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="panel panel-1m panel-1m-gainers">
        <div className="panel-header">
          <h2 className="panel-title">1-MIN GAINERS</h2>
          <div className="panel-line" />
        </div>
        <div className="panel-body">
          <div className="panel-empty">Loading…</div>
        </div>
      </section>
    );
  }


  return (
    <section className="panel panel-1m panel-1m-gainers">
      <div className="panel-header">
        <h2 className="panel-title">1-MIN GAINERS</h2>
        <div className="panel-line" />
      </div>

      <div className={`panel-body panel-1m-body${hasFew ? " panel-1m-body--single" : ""}`}>
        {total === 0 && (
          <div className="panel-empty">No 1m gainers yet.</div>
        )}

        {total > 0 && (
          <div className="one-min-grid">
            <div className="one-min-col panel-1m-col panel-1m-col-left">
              {leftRows.map((row, idx) => (
                <TokenRow
                  key={row.symbol || idx}
                  rank={row.displayRank}
                  row={row}
                  changeKey="price_change_percentage_1min"
                  rowType="gainer"
                  onInfo={onInfo}
                />
              ))}
            </div>

            {!hasFew && (
              <div className="one-min-col panel-1m-col panel-1m-col-right">
                {rightRows.map((row, idx) => (
                  <TokenRow
                    key={row.symbol || idx}
                    rank={row.displayRank}
                    row={row}
                    changeKey="price_change_percentage_1min"
                    rowType="gainer"
                    onInfo={onInfo}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {total > 8 && (
        <div className="panel-footer panel-1m-footer">
          <button
            type="button"
            className="btn-show-more"
            aria-expanded={showMore}
            aria-controls="one-min-list"
            onClick={() => setShowMore((prev) => !prev)}
          >
            {showMore ? "Show Less" : "Show More"}
          </button>
        </div>
      )}
    </section>
  );
}
