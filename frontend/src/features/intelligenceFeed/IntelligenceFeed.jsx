// Intelligence Feed — minimum render surface.
//
// Answers exactly one question: "Here is what changed since your last snapshot."
// No charts, no notifications, no AI interpretation. When the LLM explanation
// layer lands it fills the reserved `explanation` field; nothing here changes.

import PropTypes from "prop-types";

import "./styles/intelligence-feed.css";
import { useIntelligenceFeed } from "./useIntelligenceFeed.js";

function EventCard({ event, onDismiss }) {
  return (
    <li className="ifd-card" data-testid="intelligence-event">
      <p className="ifd-card__headline">{event.headline}</p>

      <div className="ifd-card__meta">
        {event.observedAtLabel && <span>{event.observedAtLabel}</span>}
        <span>{event.type}</span>
      </div>

      <div className="ifd-card__impact">
        <span
          className={`ifd-card__impact-pct ifd-card__impact-pct--${event.impact.direction}`}
        >
          {/* Unknown must not masquerade as 0.00%. */}
          {event.impact.changePctLabel ?? "—"}
        </span>
        {event.impact.changeUsdLabel && (
          <span className="ifd-card__impact-usd">{event.impact.changeUsdLabel}</span>
        )}
        {event.impact.previousTotalLabel && event.impact.currentTotalLabel && (
          <span className="ifd-card__impact-range">
            {event.impact.previousTotalLabel} → {event.impact.currentTotalLabel}
          </span>
        )}
      </div>

      {event.affectedAssets.length > 0 && (
        <div className="ifd-card__assets">
          {event.affectedAssets.map((symbol) => (
            <span className="ifd-card__asset" key={symbol}>
              {symbol}
            </span>
          ))}
        </div>
      )}

      {event.reasons.length > 0 && (
        <ul className="ifd-card__reasons">
          {event.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}

      {event.movers.length > 0 && (
        <div className="ifd-card__movers">
          {event.movers.slice(0, 3).map((mover) => (
            <span key={mover.symbol}>
              {mover.symbol} {mover.valueDeltaLabel ?? "—"}
              {mover.contributionLabel ? ` (${mover.contributionLabel} of portfolio)` : ""}
            </span>
          ))}
        </div>
      )}

      <div className="ifd-card__footer">
        <span className={`ifd-card__confidence--${event.confidence.tone}`}>
          {event.confidence.label}
          {!event.evidenceAvailable && " · evidence unavailable"}
        </span>
        {onDismiss && (
          <button
            type="button"
            className="ifd-card__dismiss"
            onClick={() => onDismiss(event.id)}
          >
            Dismiss
          </button>
        )}
      </div>
    </li>
  );
}

EventCard.propTypes = {
  event: PropTypes.object.isRequired,
  onDismiss: PropTypes.func,
};

export default function IntelligenceFeed({ limit = 20, enabled = true, fetcher, statusSetter }) {
  const { feed, status, markEvent } = useIntelligenceFeed({
    limit,
    enabled,
    ...(fetcher ? { fetcher } : {}),
    ...(statusSetter ? { statusSetter } : {}),
  });

  return (
    <section className="ifd" aria-label="Intelligence feed">
      <h2 className="ifd__title">What changed</h2>

      {status === "loading" && (
        <p className="ifd__state">Checking what changed since your last snapshot…</p>
      )}

      {status === "unauthorized" && (
        <p className="ifd__state">Sign in to see what changed in your portfolio.</p>
      )}

      {status === "error" && (
        <p className="ifd__state">
          Intelligence is temporarily unavailable. Nothing has been lost — it will
          appear once the connection recovers.
        </p>
      )}

      {status === "ready" && feed.isEmpty && (
        <p className="ifd__state">
          Nothing material changed since your last snapshot.
        </p>
      )}

      {status === "ready" && !feed.isEmpty && (
        <ul className="ifd__list">
          {feed.events.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              onDismiss={(id) => markEvent(id, "dismissed")}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

IntelligenceFeed.propTypes = {
  limit: PropTypes.number,
  enabled: PropTypes.bool,
  fetcher: PropTypes.func,
  statusSetter: PropTypes.func,
};
