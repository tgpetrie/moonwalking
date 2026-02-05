// src/components/MoversPanel.jsx
import React, { useMemo, useState } from "react";
import TokenRow from "./TokenRow.jsx";

export default function MoversPanel({ title, variant = "3m-list", packet, onInfo, forceDown = false }) {
  const rows = packet?.rows || [];
  const loading = packet?.loading;
  const message = packet?.message;

  const [limit, setLimit] = useState(8);

  const capped = rows.slice(0, Math.min(limit, 16));

  const baseInterval = variant === "1m-split" ? "1m" : "3m";

  const [left, right] = useMemo(() => {
    if (variant !== "1m-split") return [capped, []];
    if (capped.length <= 4) return [capped, []];
    const mid = Math.ceil(capped.length / 2);
    return [capped.slice(0, mid), capped.slice(mid)];
  }, [variant, capped]);

  const canShowMore = rows.length > limit && limit < 16;

  return (
    <section className="bh-panel-inner">
      <div className="panel-header">
        <h2 className="panel-title">{title}</h2>
        <div className="panel-line" />
      </div>
      <div className="panel-body">
        {loading && !rows.length && <div className="panel-empty">{message || "Loading…"}</div>}

        {!loading && !rows.length && <div className="panel-empty">{message || "No data available for this window."}</div>}

        {rows.length > 0 && (variant === "1m-split" || variant === "1m-left" || variant === "1m-right") && (
          <div className="one-min-grid">
            { (variant === '1m-split' || variant === '1m-left') && (
              <div className="one-min-col">
                {left.map((r, i) => (
                  <TokenRow
                    key={r.symbol || `${i}-l`}
                    index={i + 1}
                    row={r}
                    changeKey="price_change_percentage_1min"
                    interval={baseInterval}
                    onInfo={onInfo}
                  />
                ))}
              </div>
            )}

            { (variant === '1m-split' || variant === '1m-right') && (
              <div className="one-min-col">
                {right.map((r, i) => (
                  <TokenRow
                    key={r.symbol || `${i}-r`}
                    index={i + 1 + left.length}
                    row={r}
                    changeKey="price_change_percentage_1min"
                    interval={baseInterval}
                    onInfo={onInfo}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {rows.length > 0 && variant === "3m-list" && (
          <div className="three-min-list">
            {capped.map((r, i) => (
              <TokenRow
                key={r.symbol || i}
                index={i + 1}
                rank={i + 1}
                row={r}
                changeKey={r.price_change_percentage_3min != null ? "price_change_percentage_3min" : "price_change_percentage_1min"}
                 interval={baseInterval}
                onInfo={onInfo}
                isLoss={!!forceDown}
              />
            ))}
          </div>
        )}

        {canShowMore && (
          <div className="panel-show-more">
            <button type="button" className="btn-pill" onClick={() => setLimit((n) => Math.min(16, n + 8))}>Show more</button>
          </div>
        )}
      </div>
    </section>
  );
}
