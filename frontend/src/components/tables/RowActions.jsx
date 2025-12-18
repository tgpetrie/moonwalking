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

function InfoIcon({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="8" />
      <line x1="12" y1="11" x2="12" y2="17" />
    </svg>
  );
}

export default function RowActions({ starred, onToggleStar, onInfoClick }) {
  const handleStarClick = (event) => {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    onToggleStar?.();
  };

  const handleInfoClick = (event) => {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    onInfoClick?.();
  };

  return (
    <div className="bh-row-actions row-actions">
      <button
        type="button"
        className={`bh-row-action ${starred ? "is-active" : ""}`}
        onClick={handleStarClick}
        aria-label="Toggle watchlist"
      >
        <StarIcon filled={starred} className="bh-row-icon" />
      </button>

      <button
        type="button"
        className="bh-row-action"
        onClick={handleInfoClick}
        aria-label="Show sentiment"
      >
        <InfoIcon className="bh-row-icon" />
      </button>
    </div>
  );
}
