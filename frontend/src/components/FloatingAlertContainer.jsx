// src/components/FloatingAlertContainer.jsx
import React, { useEffect, useState, useRef, useCallback } from "react";
import { getAlertConfig, getAlertColor } from "../config/alertConfig";
import "../styles/alerts.css";

const AUTO_DISMISS_MS = 8000;
const MAX_VISIBLE_ALERTS = 5;

// Format timestamp
const formatAlertTime = (ts) => {
  if (!ts) return "";
  try {
    const date = typeof ts === "number"
      ? (ts > 1e12 ? new Date(ts) : new Date(ts * 1000))
      : new Date(ts);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);

    if (diffSec < 60) return "just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;

    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
};

export function FloatingAlertContainer({ alerts = [], onAlertClick, playSoundForCritical = true }) {
  const [visibleAlerts, setVisibleAlerts] = useState([]);
  const [dismissingIds, setDismissingIds] = useState(new Set());
  const seenAlertIds = useRef(new Set());
  const audioRef = useRef(null);

  // Initialize audio for critical alerts
  useEffect(() => {
    if (playSoundForCritical && typeof Audio !== "undefined") {
      // Using a data URI for a simple beep sound (or you can load an external file)
      // This is a placeholder - you can replace with a proper alert sound file
      try {
        audioRef.current = new Audio();
        audioRef.current.volume = 0.3;
      } catch (err) {
        console.warn("Audio not available:", err);
      }
    }
  }, [playSoundForCritical]);

  // Play sound for critical alerts
  const playAlertSound = useCallback(() => {
    if (!audioRef.current) return;
    try {
      // Simple beep using Web Audio API
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800;
      oscillator.type = "sine";

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.3);
    } catch (err) {
      console.warn("Failed to play alert sound:", err);
    }
  }, []);

  // Process incoming alerts
  useEffect(() => {
    if (!alerts || !Array.isArray(alerts) || alerts.length === 0) return;

    const newAlerts = alerts
      .filter((alert) => {
        if (!alert || !alert.id) return false;
        if (seenAlertIds.current.has(alert.id)) return false;

        // Check if alert is expired
        if (alert.expires_at) {
          const expireTime = new Date(alert.expires_at).getTime();
          if (expireTime < Date.now()) return false;
        }

        return true;
      })
      .slice(0, MAX_VISIBLE_ALERTS);

    if (newAlerts.length === 0) return;

    // Mark as seen
    newAlerts.forEach((alert) => {
      seenAlertIds.current.add(alert.id);

      // Play sound for critical alerts
      const severity = (alert.severity || alert.severity_lc || "").toLowerCase();
      if ((severity === "critical" || severity === "high") && playSoundForCritical) {
        playAlertSound();
      }
    });

    // Add new alerts to visible list
    setVisibleAlerts((prev) => {
      const combined = [...newAlerts.map(a => ({ ...a, addedAt: Date.now() })), ...prev];
      return combined.slice(0, MAX_VISIBLE_ALERTS);
    });

    // Set up auto-dismiss timers
    newAlerts.forEach((alert) => {
      setTimeout(() => {
        dismissAlert(alert.id);
      }, AUTO_DISMISS_MS);
    });
  }, [alerts, playAlertSound, playSoundForCritical]);

  const dismissAlert = useCallback((alertId) => {
    setDismissingIds((prev) => new Set(prev).add(alertId));

    // Remove from visible list after animation
    setTimeout(() => {
      setVisibleAlerts((prev) => prev.filter((a) => a.id !== alertId));
      setDismissingIds((prev) => {
        const next = new Set(prev);
        next.delete(alertId);
        return next;
      });
    }, 300);
  }, []);

  const handleAlertClick = useCallback((alert) => {
    if (typeof onAlertClick === "function") {
      onAlertClick(alert);
    }
    dismissAlert(alert.id);
  }, [onAlertClick, dismissAlert]);

  const handleDismissClick = useCallback((e, alertId) => {
    e.stopPropagation();
    dismissAlert(alertId);
  }, [dismissAlert]);

  if (!visibleAlerts || visibleAlerts.length === 0) return null;

  return (
    <div className="floating-alert-container">
      {visibleAlerts.map((alert) => {
        const alertType = alert.alert_type || alert.type;
        const alertSeverity = (alert.severity || alert.severity_lc || "info").toLowerCase();
        const config = getAlertConfig(alertType);
        const alertColor = getAlertColor(alert);
        const isCritical = alertSeverity === "critical" || alertSeverity === "high";
        const isDismissing = dismissingIds.has(alert.id);

        return (
          <div
            key={alert.id}
            className={`floating-alert-card ${isCritical ? "is-critical" : ""} ${isDismissing ? "is-dismissing" : ""}`}
            style={{ "--alert-color": alertColor }}
            onClick={() => handleAlertClick(alert)}
            role="alert"
            aria-live={isCritical ? "assertive" : "polite"}
          >
            <div className="floating-alert-header">
              <div className="floating-alert-title">
                {config && <span className="floating-alert-icon">{config.icon}</span>}
                <span>{config?.label || alertType || "ALERT"}</span>
              </div>
              <button
                className="floating-alert-close"
                onClick={(e) => handleDismissClick(e, alert.id)}
                aria-label="Dismiss alert"
              >
                ×
              </button>
            </div>

            <div className="floating-alert-symbol">
              {alert.symbol || alert.ticker || "—"}
            </div>

            <div className="floating-alert-message">
              {alert.message || alert.title || "Price alert triggered"}
            </div>

            <div className="floating-alert-footer">
              <div className="floating-alert-time">
                🕐 {formatAlertTime(alert.ts || alert.ts_iso || alert.ts_ms)}
              </div>
              {alert.confidence != null && (
                <div className="floating-alert-confidence">
                  {Math.round(alert.confidence * 100)}% confidence
                </div>
              )}
            </div>

            <div className="floating-alert-progress" />
          </div>
        );
      })}
    </div>
  );
}
