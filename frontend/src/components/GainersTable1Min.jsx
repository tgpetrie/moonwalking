import React, { useMemo, useState } from "react";
import TokenRow from "./TokenRow.jsx";

const INITIAL_LIMIT = 8;
const EXPANDED_LIMIT = 16;

export default function GainersTable1Min({ packet, rows, loading, onInfo, onRowHover }) {
  // support either packet={ rows, loading } or rows prop for backward compatibility
  const packetRows = packet?.rows ?? rows ?? [];
  const isLoading = packet?.loading ?? loading ?? false;

  const [expanded, setExpanded] = useState(false);

  const limit = expanded ? EXPANDED_LIMIT : INITIAL_LIMIT;
  const visible = packetRows.slice(0, Math.min(packetRows.length, limit));

  const [left, right] = useMemo(() => {
    if (visible.length <= 4) return [visible, []];
    // When collapsed show up to 4 on the left and the remainder on the right (4+4)
    // When expanded show up to 8 on the left and the remainder on the right (8+8)
    if (expanded) {
      const first = visible.slice(0, 8);
      const rest = visible.slice(8);
      return [first, rest];
    }
    const first = visible.slice(0, 4);
    const rest = visible.slice(4);
    return [first, rest];
  }, [visible]);

  if (!packetRows.length && isLoading) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2 className="panel-title">1-MIN GAINERS</h2>
        </div>
        <div className="panel-body">
          <div className="panel-empty">Waiting for 1-minute snapshot…</div>
        </div>
      </section>
    );
  }

  if (!packetRows.length && !isLoading) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2 className="panel-title">1-MIN GAINERS</h2>
        </div>
        <div className="panel-body">
          <div className="panel-empty">Waiting for 1-minute snapshot…</div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2 className="panel-title">1-MIN GAINERS</h2>
        <div className="panel-line" />
      </div>

      <div className="panel-body">
        <div className="one-min-grid">
          <div className="one-min-col">
            {left.map((r, i) => (
              <TokenRow
                key={r.symbol || `l-${i}`}
                index={i + 1}
                row={r}
                changeKey="price_change_percentage_1min"
                onInfo={onInfo}
                onHover={onRowHover}
              />
            ))}
          </div>

          {right.length > 0 && (
            <div className="one-min-col">
              {right.map((r, i) => (
                <TokenRow
                  key={r.symbol || `r-${i}`}
                  index={i + 1 + left.length}
                  row={r}
                  changeKey="price_change_percentage_1min"
                  onInfo={onInfo}
                  onHover={onRowHover}
                />
              ))}
            </div>
          )}
        </div>

        {packetRows.length > INITIAL_LIMIT && (
          <div className="panel-show-more">
            <button className="btn-pill" onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Show less" : "Show more"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

