import React, { useEffect } from "react";
import {
  AlertEmpty,
  AlertError,
  AlertLoading,
  AlertSignedOut,
  NOT_ADVICE,
} from "./AlertStates.jsx";
import { describeEvent, timeAgo } from "./alertLabels.js";

/**
 * Alerts that actually fired, newest first.
 *
 * The explanation string comes from the backend and is deterministic — it
 * states what happened and why this user received it. Fingerprints are debug
 * detail and appear only in development.
 */
export default function AlertHistoryTab({
  events,
  loading,
  error,
  authRequired,
  onLoad,
}) {
  useEffect(() => {
    onLoad?.();
  }, [onLoad]);

  if (authRequired) return <AlertSignedOut />;
  if (loading && events.length === 0) return <AlertLoading label="Loading your history…" />;
  if (error) return <AlertError message={error} onRetry={() => onLoad?.({ force: true })} />;

  if (events.length === 0) {
    return (
      <AlertEmpty
        title="Nothing has triggered yet"
        detail="When one of your alerts triggers, it will appear here with what happened."
      />
    );
  }

  const isDev = Boolean(import.meta?.env?.DEV);

  return (
    <div className="mw-alerts-list">
      {events.map((event) => (
        <article key={event.id} className="mw-alert-card">
          <header className="mw-alert-card__head">
            <span className="mw-alert-card__symbol">{event.symbol}</span>
            <span className="mw-alert-card__time">{timeAgo(event.triggered_ts)}</span>
          </header>

          <p className="mw-alert-card__rule">{describeEvent(event)}</p>
          <p className="mw-alert-card__explanation">{event.explanation}</p>

          {isDev ? (
            <p className="mw-alert-card__debug">{event.fingerprint}</p>
          ) : null}
        </article>
      ))}
      <p className="mw-alerts-footnote">{NOT_ADVICE}</p>
    </div>
  );
}
