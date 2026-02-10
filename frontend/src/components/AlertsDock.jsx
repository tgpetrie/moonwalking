import { useMemo, useState } from "react";
import { useData } from "../context/DataContext";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";

export default function AlertsDock({ onOpenAlerts }) {
  const { alerts = [] } = useData() || {};

  // Track unread state via latest alert id
  const latestId = useMemo(() => {
    const list = Array.isArray(alerts) ? alerts : [];
    if (!list.length) return null;
    // Pick the most recent alert's id
    for (const a of list) {
      if (a?.id) return a.id;
    }
    return null;
  }, [alerts]);

  const [lastSeenId, setLastSeenId] = useState(() => {
    try {
      return localStorage.getItem(LS_SEEN_KEY);
    } catch {
      return null;
    }
  });

  const unread = Boolean(latestId && latestId !== lastSeenId);

  const handleClick = () => {
    // Mark as seen
    if (latestId) {
      setLastSeenId(latestId);
      try {
        localStorage.setItem(LS_SEEN_KEY, latestId);
      } catch {}
    }
    // Open the Alerts tab in the Sentiment popup
    if (onOpenAlerts) {
      onOpenAlerts();
    }
  };

  return (
    <div className="bh-alerts-dock">
      <button
        type="button"
        className="bh-alerts-btn"
        onClick={handleClick}
        title={unread ? "New alerts" : "Alerts"}
      >
        <span className="bh-alerts-btn-label">ALERTS</span>
        {unread ? <span className="bh-alerts-badge" aria-label="unread alerts" /> : null}
      </button>
    </div>
  );
}
