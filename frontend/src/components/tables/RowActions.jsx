// frontend/src/components/tables/RowActions.jsx
import { useWatchlist } from "../../context/WatchlistContext.jsx";

export default function RowActions({ symbol, price, onInfo }) {
  const { has, add, remove } = useWatchlist();
  const watching = has(symbol);

  const handleStar = (e) => {
    e.stopPropagation();
    watching ? remove(symbol) : add({ symbol, price });
  };

  const handleInfo = (e) => {
    e.stopPropagation();
    onInfo?.({ symbol, price });
  };

  return (
    <div className="row-actions">
      <button
        type="button"
        className={`wl-btn ${watching ? "wl-btn--active" : ""}`}
        onClick={handleStar}
        aria-label={watching ? "Remove from watchlist" : "Add to watchlist"}
      >
        {watching ? "★" : "☆"}
      </button>
      <button
        type="button"
        className="info-btn"
        onClick={handleInfo}
        aria-label={`Info ${symbol}`}
      >
        i
      </button>
    </div>
  );
}
