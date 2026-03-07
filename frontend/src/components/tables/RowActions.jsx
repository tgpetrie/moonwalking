// frontend/src/components/tables/RowActions.jsx
function StarIcon({ filled, className = "" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
      className={className}
    >
      <polygon points="12,2 15,9 22,9.5 17,14.5 18.5,22 12,18 5.5,22 7,14.5 2,9.5 9,9" />
    </svg>
  );
}

function TradeIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <circle cx="12" cy="12" r="10" />
      <path d="M14.8 8.3c-.6-.8-1.6-1.3-2.8-1.3-1.8 0-3 1-3 2.4 0 1.6 1.3 2.1 2.9 2.5 1.7.4 3.1.8 3.1 2.5 0 1.4-1.2 2.6-3.2 2.6-1.3 0-2.5-.5-3.3-1.5" />
      <line x1="12" y1="5.7" x2="12" y2="18.3" />
    </svg>
  );
}

const stopEvent = (event) => {
  if (!event) return;
  event.preventDefault();
  event.stopPropagation();
};

export function RowStar({ starred, onToggleStar, className = "" }) {
  const handleStarClick = (event) => {
    stopEvent(event);
    onToggleStar?.();
  };
  return (
    <button
      type="button"
      className={`bh-row-action ${starred ? "is-active" : ""} ${className}`}
      onClick={handleStarClick}
      aria-label="Toggle watchlist"
    >
      <StarIcon filled={starred} className="bh-row-icon" />
    </button>
  );
}

export function RowInfo({ onInfoClick, className = "" }) {
  const handleInfoClick = (event) => {
    stopEvent(event);
    onInfoClick?.();
  };
  return (
    <button
      type="button"
      className={`bh-row-action bh-action bh-action--info ${className}`}
      onMouseDown={(e) => { if (e) { e.preventDefault(); e.stopPropagation(); } }}
      onClick={handleInfoClick}
      aria-label="Open trading page"
      title="Open trading page"
    >
      <TradeIcon className="bh-row-icon" />
    </button>
  );
}

export default function RowActions({ starred, onToggleStar, onInfoClick }) {
  return (
    <div className="bh-row-actions row-actions">
      <RowStar starred={starred} onToggleStar={onToggleStar} />
      <RowInfo onInfoClick={onInfoClick} />
    </div>
  );
}
