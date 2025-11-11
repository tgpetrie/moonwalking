import React from "react";
import TokenRowSimple from "./TokenRowSimple.jsx";

export default function Losers3mSimple({ title = "3-MINUTE LOSERS", rows = [] }) {
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
