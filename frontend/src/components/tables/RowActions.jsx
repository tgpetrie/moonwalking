// frontend/src/components/tables/RowActions.jsx
import { useWatchlist } from "../../context/WatchlistContext.jsx";

export default function RowActions({ symbol, onInfo }) {
  const { has, add, remove } = useWatchlist();
  const watching = has(symbol);

  return (
    <div className="row-actions">
      <button
        type="button"
        className={`wl-btn ${watching ? "wl-btn--active" : ""}`}
        onClick={() => (watching ? remove(symbol) : add(symbol))}
        aria-label={watching ? "Remove from watchlist" : "Add to watchlist"}
      >
        ★
      </button>
      <button
        type="button"
        className="info-btn"
        onClick={() => onInfo?.(symbol)}
      >
        i
      </button>
    </div>
  );
}

