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

export default function ThreeMinuteGainers({ title = "3 MIN GAINERS", rows = [], loading = false }) {
  const items = rows; // accept both props for compatibility
  const skeleton = Array.from({ length: 6 }).map((_, i) => ({ _sk: i }));
  const dataToRender = items.length ? items : skeleton;

  return (
    <div>
      <p className="bh-section-heading">{title}</p>
      <table className="w-full border-collapse text-[12px] font-mono leading-5">
        <tbody>
          {dataToRender.map((item, idx) =>
            item._sk ? <SkeletonRow key={idx} index={idx} /> : <TokenRow key={item.symbol || idx} index={idx} item={item} changeKey="price_change_percentage_3min" />
          )}
        </tbody>
      </table>
    </div>
  );
}

