import React from "react";
import TokenRow from "./TokenRow.jsx";

export default function GainersTable1Min({ rows = [], loading }) {
  const ready = Array.isArray(rows) && rows.length > 0;
  const twoCol = ready && rows.length > 4; // flip only when > 4
  if (!twoCol) {
    return (
      <table className="bh-table bh-table-1m">
        <thead>
          <tr><th>#</th><th>Asset</th><th>Price</th><th>1m</th><th>★</th></tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <TokenRow key={row.symbol || i} row={row} index={i} changeKey="price_change_percentage_1min" />
          ))}
        </tbody>
      </table>
    );
  }
  // two columns: split list roughly in half
  const mid = Math.ceil(rows.length / 2);
  const left = rows.slice(0, mid);
  const right = rows.slice(mid);
  return (
    <div className="grid grid-cols-2 gap-4">
      {[left, right].map((col, cIdx) => (
        <table key={cIdx} className="bh-table bh-table-1m">
          <thead>
            <tr><th>#</th><th>Asset</th><th>Price</th><th>1m</th><th>★</th></tr>
          </thead>
          <tbody>
            {col.map((row, i) => (
              <TokenRow
                key={(row.symbol || "row") + "-" + i}
                row={row}
                index={i + (cIdx === 0 ? 0 : mid)}
                changeKey="price_change_percentage_1min"
              />
            ))}
          </tbody>
        </table>
      ))}
    </div>
  );
}

