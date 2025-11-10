// frontend/src/components/ThreeMinRow.jsx
import React from "react";
import Gainers3m from "./Gainers3m.jsx";
import Losers3m from "./Losers3m.jsx";

export default function ThreeMinRow({ gainers = [], losers = [], loading, onInfo }) {
  const hasMore = gainers.length > 8 || losers.length > 8;

  return (
    <section className="three-min-shell">
      <div className="three-min-grid">
        <Gainers3m rows={gainers} loading={loading} onInfo={onInfo} />
        <Losers3m rows={losers} loading={loading} onInfo={onInfo} />
      </div>
      {hasMore && (
        <div className="three-min-more">
          <button className="btn-secondary">Show More</button>
        </div>
      )}
    </section>
  );
}

