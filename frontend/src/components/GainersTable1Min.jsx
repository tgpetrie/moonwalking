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
  const maxVisible = showMore ? 16 : 8;
  const visibleRows = useMemo(
    () => allRows.slice(0, maxVisible),
    [allRows, maxVisible]
  );

  const total = allRows.length;
  const hasFew = visibleRows.length <= 4;

  const isTwoColumn = visibleRows.length > 4;

  let leftRows = [];
  let rightRows = [];

  if (isTwoColumn) {
    visibleRows.forEach((row, idx) => {
      const withRank = { ...row, displayRank: row.rank ?? idx + 1 };
      if (idx % 2 === 0) {
        leftRows.push(withRank);
      } else {
        rightRows.push(withRank);
      }
    });
  } else {
    leftRows = visibleRows.map((row, idx) => ({
      ...row,
      displayRank: row.rank ?? idx + 1,
    }));
  }

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

      <div className="panel-body panel-1m-body">
        {total === 0 && (
          <div className="panel-empty">No 1m gainers yet.</div>
        )}

        {total > 0 && hasFew && (
          <div className="panel-1m-col panel-1m-col-single">
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
        )}

        {total > 0 && !hasFew && (
          <div className="panel-1m-grid">
            <div className="panel-1m-col panel-1m-col-left">
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
            <div className="panel-1m-col panel-1m-col-right">
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
