import React from "react";
import Gainers3m from "./Gainers3m.jsx";
import Losers3m from "./Losers3m.jsx";

export default function ThreeMinSection({
  gainers = [],
  losers = [],
  loadingGainers = false,
  loadingLosers = false,
  onInfo,
  onShowMore,
}) {
  const anyMore = gainers.length > 8 || losers.length > 8;

  return (
    <div className="three-min-grid">
      <Gainers3m rows={gainers} loading={loadingGainers} onInfo={onInfo} />
      <Losers3m rows={losers} loading={loadingLosers} onInfo={onInfo} />

      {anyMore && (
        <div className="flex justify-center pt-4 col-span-2">
          <button className="show-more-btn" onClick={onShowMore}>
            Show More
          </button>
        </div>
      )}
    </div>
  );
}
