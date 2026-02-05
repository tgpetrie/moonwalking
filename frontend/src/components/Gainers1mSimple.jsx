import React from "react";
import TokenRowSimple from "./TokenRowSimple.jsx";

export default function Gainers1mSimple({ title = "1-MINUTE GAINERS", rows = [] }) {
  return (
    <div className="panel">
      <div className="panel-title">{title}</div>
      <div className="panel-body">
        {rows.length === 0 ? (
          <div className="panel-empty">No data.</div>
        ) : (
          rows.map((row, idx) => (
            <TokenRowSimple key={row.symbol || idx} index={idx} row={row} />
          ))
        )}
      </div>
    </div>
  );
}
