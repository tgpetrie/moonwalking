import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function OneMinuteGainers({ rows = [] }) {
  return (
    <div className="bh-panel bh-panel-nopad">
      <div className="bh-section-heading">1 MIN GAINERS</div>
      {rows.length === 0 && <div className="muted small-pad">No 1m data.</div>}
      {rows.map((row, idx) => (
        <TokenRow key={row.symbol} index={idx} item={row} />
      ))}
    </div>
  );
}
import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function OneMinuteGainers({ title, items = [], loading }) {
  return (
    <div>
      <p className="bh-section-heading">{title}</p>
      {loading && !items.length ? (
        <div style={{ padding: "0.75rem" }}>Loading…</div>
      ) : !items.length ? (
        <div style={{ padding: "0.75rem" }}>No data.</div>
      ) : (
        items.map((item, idx) => (
          <TokenRow
            key={item.symbol || idx}
            index={idx}
            item={item}
            changeKey="price_change_percentage_1min"
          />
        ))
      )}
    </div>
  );
}

