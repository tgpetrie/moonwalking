import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "../styles/alerts.css";
import displaySymbol from "../utils/symbolFmt.js";

// Small floating inbox for alerts (badge + compact list)
export default function AlertInbox({
  alerts = [],
  onAlertClick,
  unreadCount: unreadCountProp,
  markAllRead: markAllReadProp,
  clearAllAlerts: clearAllAlertsProp,
}) {
  const [open, setOpen] = useState(false);
  const [inbox, setInbox] = useState([]);
  const [unread, setUnread] = useState(() => new Set());
  const [muteUntil, setMuteUntil] = useState(0);
  const seenRef = useRef(new Set());
  const maxItems = 120;

  const toTsMs = useCallback((value) => {
    if (value == null) return 0;
    if (typeof value === "number") return value > 1e12 ? value : value * 1000;
    const parsed = Date.parse(String(value));
    return Number.isFinite(parsed) ? parsed : 0;
  }, []);

  const signature = useCallback(
    (a) => {
      if (!a) return null;
      if (a.id) return String(a.id);
      const sym = (a.symbol || a.ticker || "").toString().toUpperCase();
      const typ = (a.alert_type || a.type || "").toString().toUpperCase();
      const sev = (a.severity || a.severity_lc || "").toString().toUpperCase();
      const ts = toTsMs(a.ts_ms ?? a.ts ?? a.ts_iso ?? Date.now());
      return `${sym}|${typ}|${sev}|${Math.round(ts / 1000)}`;
    },
    [toTsMs]
  );

  const formatTime = useCallback((ts) => {
    if (!ts) return "";
    const n = toTsMs(ts);
    if (!n) return "";
    const diffSec = Math.floor((Date.now() - n) / 1000);
    if (diffSec < 60) return "just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return new Date(n).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }, [toTsMs]);

  // Ingest new alerts, dedupe by signature, and track unread
  useEffect(() => {
    if (!Array.isArray(alerts) || alerts.length === 0) return;

    const newcomers = [];
    alerts.forEach((a) => {
      const sig = signature(a);
      if (!sig) return;
      if (seenRef.current.has(sig)) return;
      seenRef.current.add(sig);
      newcomers.push({ ...a, _sig: sig });
    });

    if (!newcomers.length) return;

    const now = Date.now();
    const isMuted = muteUntil && now < muteUntil;

    if (!isMuted) {
      setUnread((prev) => {
        const next = new Set(prev);
        newcomers.forEach((a) => next.add(a._sig));
        return next;
      });
    }

    setInbox((prev) => {
      const map = new Map();
      prev.forEach((item) => {
        const sig = item._sig || signature(item);
        if (sig) map.set(sig, { ...item, _sig: sig });
      });
      newcomers.forEach((item) => map.set(item._sig, item));
      const merged = Array.from(map.values()).sort(
        (a, b) => (toTsMs(b.ts_ms ?? b.ts ?? b.ts_iso) || 0) - (toTsMs(a.ts_ms ?? a.ts ?? a.ts_iso) || 0)
      );
      return merged.slice(0, maxItems);
    });
  }, [alerts, signature, toTsMs, muteUntil]);

  const unreadCount = useMemo(() => {
    if (typeof unreadCountProp === "number") return unreadCountProp;
    return unread.size;
  }, [unread, unreadCountProp]);

  const markAllRead = useCallback(() => {
    if (typeof markAllReadProp === "function") {
      markAllReadProp();
    }
    setUnread(new Set());
  }, [markAllReadProp]);

  const handleItemClick = useCallback(
    (item) => {
      if (!item) return;
      if (typeof onAlertClick === "function") onAlertClick(item);
      setUnread((prev) => {
        const next = new Set(prev);
        if (item._sig) next.delete(item._sig);
        return next;
      });
    },
    [onAlertClick]
  );

  const toggleOpen = useCallback(() => {
    const next = !open;
    setOpen(next);
    if (next) markAllRead();
  }, [open, markAllRead]);

  const clearAll = useCallback(() => {
    if (typeof clearAllAlertsProp === "function") {
      clearAllAlertsProp();
    }
    setInbox([]);
    setUnread(new Set());
    seenRef.current = new Set();
  }, [clearAllAlertsProp]);

  const markRead = useCallback(() => {
    setUnread(new Set());
  }, []);

  const muteFor = useCallback((minutes) => {
    if (!minutes) {
      setMuteUntil(0);
      return;
    }
    setMuteUntil(Date.now() + minutes * 60_000);
  }, []);

  // Auto-unmute when mute window elapses
  useEffect(() => {
    if (!muteUntil) return undefined;
    const now = Date.now();
    const delay = Math.max(0, muteUntil - now);
    const timer = window.setTimeout(() => setMuteUntil(0), delay + 50);
    return () => clearTimeout(timer);
  }, [muteUntil]);

  const muteLabel = useMemo(() => {
    if (!muteUntil) return null;
    const msLeft = muteUntil - Date.now();
    if (msLeft <= 0) return null;
    const min = Math.ceil(msLeft / 60000);
    return `muted ${min}m`;
  }, [muteUntil]);

  if (!Array.isArray(alerts)) return null;

  return (
    <div className="alert-inbox">
      <button className="mw-alert-fab" onClick={toggleOpen} aria-label="Open alert inbox">
        <span className="mw-alert-fab__icon">ALERTS</span>
        {unreadCount > 0 && <span className="mw-alert-fab__badge">{unreadCount}</span>}
      </button>

      {open && (
        <div className="alert-inbox-panel">
          <div className="alert-inbox-head">
            <span>Alerts</span>
            <span className="alert-inbox-meta">
              {inbox.length} stored
              {muteLabel ? ` • ${muteLabel}` : ""}
            </span>
          </div>
          <div className="alert-inbox-controls">
            <button onClick={markRead} className="alert-inbox-ctrl">Mark read</button>
            <button onClick={clearAll} className="alert-inbox-ctrl">Clear all</button>
            <div className="alert-inbox-mute">
              <span>Mute</span>
              <div className="alert-inbox-mute-buttons">
                <button onClick={() => muteFor(5)} className="alert-inbox-ctrl">5m</button>
                <button onClick={() => muteFor(15)} className="alert-inbox-ctrl">15m</button>
                <button onClick={() => muteFor(60)} className="alert-inbox-ctrl">60m</button>
                <button onClick={() => muteFor(0)} className="alert-inbox-ctrl">Off</button>
              </div>
            </div>
          </div>
          <div className="alert-inbox-list">
            {inbox.length === 0 && <div className="alert-inbox-empty">No alerts yet</div>}
            {inbox.map((a) => {
              const sig = a._sig || signature(a);
              const tone = (a.severity_lc || a.severity || "info").toString().toLowerCase();
              const label = (a.alert_type || a.type || "ALERT").toString().toUpperCase();
              const time = formatTime(a.ts_ms ?? a.ts ?? a.ts_iso);
              const isUnread = unread.has(sig);
              const coin = displaySymbol(a.product_id || a.symbol || "");

              return (
                <button
                  key={sig}
                  className={`alert-inbox-row ${tone} ${isUnread ? "is-unread" : ""}`}
                  onClick={() => handleItemClick({ ...a, _sig: sig })}
                >
                  <div className="alert-inbox-row-line1">
                    <div className="mw-alert-row__symbol">{coin}</div>
                    <div className="mw-alert-chips">
                      <span className="mw-alert-pill">{label}</span>
                      <span className={`mw-alert-pill mw-chip--sev mw-chip--${tone || "info"}`}>
                        {tone || "info"}
                      </span>
                    </div>
                  </div>
                  <div className="alert-inbox-row-line2">
                    {time && <span className="alert-inbox-time mw-alert-row__meta">{time}</span>}
                    {Number.isFinite(a.score_signed ?? a.score) && (
                      <span className="mw-alert-row__meta">
                        score {(a.score_signed ?? a.score).toFixed(2)}
                      </span>
                    )}
                    {Number.isFinite(a.confidence_0_1 ?? a.confidence) && (
                      <span className="mw-alert-row__meta">
                        conf {(a.confidence_0_1 ?? a.confidence).toFixed(2)}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
