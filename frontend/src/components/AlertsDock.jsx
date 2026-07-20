import { useEffect, useMemo, useState } from "react";
import { useData } from "../context/DataContext";

const LS_SEEN_KEY = "mw_alerts_last_seen_id";
const LS_BROWSER_ENABLED = "mw_browser_notifications_enabled";
const LS_BROWSER_LAST_ID = "mw_browser_notifications_last_id";

export default function AlertsDock({ onOpenAlerts }) {
  const {
    activeAlerts = [],
    alertsRecent = [],
    signalEvents = [],
    notifyEvents = [],
  } = useData() || {};

  // Track unread state via stable alert ids ordered newest-first.
  const orderedAlertIds = useMemo(() => {
    const grouped = Array.isArray(signalEvents) ? signalEvents : [];
    const merged = grouped.length
      ? [...grouped]
      : [
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
  }, [activeAlerts, alertsRecent, signalEvents]);

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

  const [browserEnabled, setBrowserEnabled] = useState(() => {
    try {
      return localStorage.getItem(LS_BROWSER_ENABLED) === "1";
    } catch {
      return false;
    }
  });
  const browserSupported = typeof window !== "undefined" && "Notification" in window;
  const browserPermission = browserSupported ? window.Notification.permission : "unsupported";

  useEffect(() => {
    if (!browserEnabled || !browserSupported || window.Notification.permission !== "granted") return;
    const candidates = Array.isArray(notifyEvents) ? [...notifyEvents] : [];
    candidates.sort((a, b) => Number(b?.latest_transition_ts_ms ?? b?.event_ts_ms ?? 0) - Number(a?.latest_transition_ts_ms ?? a?.event_ts_ms ?? 0));
    const event = candidates[0];
    if (!event) return;
    const id = String(event.id || "");
    const ts = Number(event.latest_transition_ts_ms ?? event.event_ts_ms ?? 0);
    if (!id || !Number.isFinite(ts) || Date.now() - ts > 90_000) return;
    let lastId = null;
    try { lastId = localStorage.getItem(LS_BROWSER_LAST_ID); } catch {}
    if (lastId === id) return;

    const symbol = String(event.symbol || event.product_id || "").replace(/-USD$/i, "");
    const notification = new window.Notification(event.title || `Moonwalkings signal: ${symbol}`, {
      body: event.message || `${event.primary_state || "Signal"} · confidence ${event.confidence ?? "—"}`,
      tag: String(event.event_id || symbol || id),
      renotify: true,
    });
    notification.onclick = () => {
      try { window.focus(); } catch {}
      onOpenAlerts?.();
      try { notification.close(); } catch {}
    };
    try { localStorage.setItem(LS_BROWSER_LAST_ID, id); } catch {}
  }, [browserEnabled, browserSupported, notifyEvents, onOpenAlerts]);

  const handleBrowserToggle = async () => {
    if (!browserSupported) return;
    if (browserEnabled) {
      setBrowserEnabled(false);
      try { localStorage.setItem(LS_BROWSER_ENABLED, "0"); } catch {}
      return;
    }
    const permission = await window.Notification.requestPermission();
    const enabled = permission === "granted";
    setBrowserEnabled(enabled);
    try { localStorage.setItem(LS_BROWSER_ENABLED, enabled ? "1" : "0"); } catch {}
  };

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
        className="bh-alerts-notify-btn"
        data-enabled={browserEnabled && browserPermission === "granted" ? "true" : "false"}
        onClick={handleBrowserToggle}
        disabled={!browserSupported}
        title={!browserSupported ? "Browser notifications are unavailable" : browserEnabled ? "Disable browser notifications" : "Enable free browser notifications"}
      >
        NOTIFY {browserEnabled && browserPermission === "granted" ? "ON" : "OFF"}
      </button>
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
