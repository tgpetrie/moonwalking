import { useMemo, useState } from "react";
import { useData } from "../context/DataContext";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";

export default function AlertsDock({ onOpenAlerts }) {
  const { activeAlerts = [], alertsRecent = [] } = useData() || {};

  // Track unread state via stable alert ids ordered newest-first.
  const orderedAlertIds = useMemo(() => {
    const merged = [
      ...(Array.isArray(activeAlerts) ? activeAlerts : []),
      ...(Array.isArray(alertsRecent) ? alertsRecent : []),
    ];
    if (!merged.length) return [];

    merged.sort((a, b) => {
      const ta = Number(a?.event_ts_ms ?? a?.ts_ms ?? 0) || 0;
      const tb = Number(b?.event_ts_ms ?? b?.ts_ms ?? 0) || 0;
      return tb - ta;
    });

    const ids = [];
    const seen = new Set();
    for (const a of merged) {
      let id = null;
      if (a?.id != null) id = String(a.id);
      else if (a?.alert_id != null) id = String(a.alert_id);
      const sym = String(a?.symbol || a?.product_id || "");
      const type = String(a?.type_key || a?.type || "");
      const ts = Number(a?.event_ts_ms ?? a?.ts_ms ?? 0) || 0;
      if (!id && (sym || type || ts)) id = `${sym}:${type}:${ts}`;
      if (id && !seen.has(id)) {
        seen.add(id);
        ids.push(id);
      }
    }
    return ids;
  }, [activeAlerts, alertsRecent]);

  const latestId = orderedAlertIds[0] || null;

  const [lastSeenId, setLastSeenId] = useState(() => {
    try {
      return localStorage.getItem(LS_SEEN_KEY);
    } catch {
      return null;
    }
  });

  const unreadCount = useMemo(() => {
    if (!latestId || latestId === lastSeenId) return 0;
    const seenIndex = orderedAlertIds.indexOf(lastSeenId);
    return seenIndex >= 0 ? seenIndex : orderedAlertIds.length;
  }, [latestId, lastSeenId, orderedAlertIds]);
  const unread = unreadCount > 0;

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
        title={unread ? `${unreadCount} unread alerts` : "Alerts"}
      >
        <span className="bh-alerts-btn-label">ALERTS</span>
        {unread ? (
          <span className="bh-alerts-badge" aria-label={`${unreadCount} unread alerts`}>
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </button>
    </div>
  );
}
