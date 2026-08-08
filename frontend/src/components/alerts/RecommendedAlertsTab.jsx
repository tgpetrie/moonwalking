import React, { useEffect, useState } from "react";
import {
  AlertEmpty,
  AlertError,
  AlertLoading,
  AlertSignedOut,
  InlineMessage,
  NOT_ADVICE,
} from "./AlertStates.jsx";

/**
 * Suggestions derived from the user's portfolio and watchlist.
 *
 * Nothing here is ever active on arrival — a suggestion becomes a real rule
 * only when the user presses Enable. Dismiss is optimistic and rolls back if
 * the server rejects it.
 */
export default function RecommendedAlertsTab({
  recommendations,
  loading,
  error,
  authRequired,
  onLoad,
  onAccept,
  onDismiss,
}) {
  const [busyId, setBusyId] = useState(null);
  const [cardError, setCardError] = useState({});

  useEffect(() => {
    onLoad?.();
  }, [onLoad]);

  if (authRequired) return <AlertSignedOut />;
  if (loading && recommendations.length === 0) {
    return <AlertLoading label="Looking at your portfolio and watchlist…" />;
  }
  if (error) return <AlertError message={error} onRetry={() => onLoad?.({ force: true })} />;

  if (recommendations.length === 0) {
    return (
      <AlertEmpty
        title="No suggestions right now"
        detail="Add coins to your portfolio or a watchlist and suggestions will appear here."
      />
    );
  }

  const run = async (id, fn) => {
    setBusyId(id);
    setCardError((prev) => ({ ...prev, [id]: null }));
    try {
      await fn();
    } catch (err) {
      setCardError((prev) => ({ ...prev, [id]: err?.message || "That didn't work." }));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mw-alerts-list">
      {recommendations.map((rec) => (
        <article key={rec.id} className="mw-alert-card">
          <header className="mw-alert-card__head">
            <span className="mw-alert-card__symbol">{rec.symbol}</span>
            <span className="mw-alert-card__badge">
              {rec.basis === "portfolio" ? "In your portfolio" : "On your watchlist"}
            </span>
          </header>

          <p className="mw-alert-card__reason">{rec.reason}</p>

          <div className="mw-alert-card__actions">
            <button
              type="button"
              className="mw-alert-btn mw-alert-btn--primary"
              disabled={busyId === rec.id}
              onClick={() => run(rec.id, () => onAccept(rec.id))}
            >
              {busyId === rec.id ? "Working…" : "Enable"}
            </button>
            <button
              type="button"
              className="mw-alert-btn"
              disabled={busyId === rec.id}
              onClick={() => run(rec.id, () => onDismiss(rec.id))}
            >
              Dismiss
            </button>
          </div>

          <InlineMessage>{cardError[rec.id]}</InlineMessage>
        </article>
      ))}
      <p className="mw-alerts-footnote">{NOT_ADVICE}</p>
    </div>
  );
}
