import { useMemo, useState } from "react";
import { useData } from "../context/DataContext";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";

export default function AlertsDock({ onOpenAlerts }) {
  const { activeAlerts = [], alertsRecent = [] } = useData() || {};

  // Track unread state via latest alert id
  const latestId = useMemo(() => {
    const merged = [
      ...(Array.isArray(activeAlerts) ? activeAlerts : []),
      ...(Array.isArray(alertsRecent) ? alertsRecent : []),
    ];
    if (!merged.length) return null;

    merged.sort((a, b) => {
      const ta = Number(a?.event_ts_ms ?? a?.ts_ms ?? 0) || 0;
      const tb = Number(b?.event_ts_ms ?? b?.ts_ms ?? 0) || 0;
      return tb - ta;
    });

    for (const a of merged) {
      if (a?.id != null) return String(a.id);
      if (a?.alert_id != null) return String(a.alert_id);
      const sym = String(a?.symbol || a?.product_id || "");
      const type = String(a?.type_key || a?.type || "");
      const ts = Number(a?.event_ts_ms ?? a?.ts_ms ?? 0) || 0;
      if (sym || type || ts) return `${sym}:${type}:${ts}`;
    }
    return null;
  }, [activeAlerts, alertsRecent]);

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
    // Open the dedicated global Alerts entity
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
