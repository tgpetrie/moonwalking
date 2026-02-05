import React from "react";
import TokenRow from "../components/TokenRow.jsx";

function SkeletonRow({ index }) {
  return (
    <div className="bh-row skeleton" aria-hidden="true">
      <div className="bh-row-hover-glow" />
      <div className="bh-cell bh-cell-rank">{index + 1}</div>
      <div className="bh-cell bh-cell-symbol">---</div>
      <div className="bh-cell bh-cell-price">--.--</div>
      <div className="bh-cell bh-cell-change">---%</div>
      <div className="bh-cell bh-cell-actions">
        <button type="button" className="bh-star" disabled>
          ★
        </button>
      </div>
    </div>
  );
}

export default function ThreeMinuteLosers({ title = "3 MIN LOSERS", rows = [], loading = false, onInfo }) {
  const items = rows; // accept both props for compatibility
  const skeleton = Array.from({ length: 6 }).map((_, i) => ({ _sk: i }));
  const dataToRender = items.length ? items : skeleton;

  return (
    <div>
      <p className="bh-section-heading">{title}</p>
      <div className="bh-table">
        {dataToRender.map((item, idx) =>
          item._sk ? (
            <SkeletonRow key={idx} index={idx} />
          ) : (
            <TokenRow key={item.symbol || idx} index={idx} item={item} changeKey="price_change_percentage_3min" onInfo={onInfo} />
          )
        )}
      </div>
    </div>
  );
}

