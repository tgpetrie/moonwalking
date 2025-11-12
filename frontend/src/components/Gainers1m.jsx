import React from "react";
import TokenRow from "./TokenRow.jsx";

function SkeletonRow({ index }) {
  return (
    <tr className="table-row">
      <td className="bh-token-rank">{index + 1}</td>
      <td className="bh-token-symbol">---</td>
      <td className="bh-token-price">--.--</td>
      <td className="bh-token-change">---%</td>
      <td>
        <button type="button" className="bh-star" disabled>
          ★
        </button>
      </td>
    </tr>
  );
}

export default function Gainers1m({
  rows = [],
  loading = false,
  showTitle = true,
}) {
  const skeleton = Array.from({ length: 6 }).map((_, i) => ({ _sk: i }));
  const dataToRender = rows.length ? rows : skeleton;
  const twoCol = dataToRender.length > 4;

  return (
    <section className="mt-4">
      <header className="mb-2 flex items-center gap-2">
        <span className="badge-gold">1-MIN GAINERS</span>
        <span className="rule-gold" />
      </header>

      <div className={twoCol ? "grid grid-cols-2 gap-4" : "grid grid-cols-1 gap-4"}>
        <table className="w-full border-collapse text-[12px] font-mono leading-5">
          <tbody>
            {dataToRender.map((row, idx) =>
              row._sk ? <SkeletonRow key={idx} index={idx} /> : <TokenRow key={row.symbol || idx} row={row} index={idx} isGainer />
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

