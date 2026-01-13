import { useEffect, useRef, useState } from "react";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { useData } from "../context/DataContext";
import { getAlertConfig, getSeverityConfig, SEV_TONE } from "../config/alertConfig";

const toTsMs = (value) => {
  if (value == null) return null;
  if (typeof value === "number") return value > 1e12 ? value : value * 1000;
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : null;
};

const fmtTime = (tsMs) => {
  const d = tsMs ? new Date(tsMs) : new Date();
  return d
    .toLocaleTimeString([], {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
    .replace(/\u200E/g, "");
};

const spotUrl = (alert, symbol) => {
  const productId =
    alert?.product_id ||
    alert?.symbol ||
    alert?.ticker ||
    (symbol ? `${symbol}-USD` : null);
  return coinbaseSpotUrl({ product_id: productId, symbol });
};

export default function AnomalyStream() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [logs, setLogs] = useState([
    { id: "init-1", time: "INIT", msg: "ESTABLISHING NEURAL LINK...", tone: "tone-mint" },
    { id: "init-2", time: "INIT", msg: "M3_COPROCESSOR: ONLINE", tone: "tone-mint" },
  ]);

  const scrollRef = useRef(null);
  const lastHeartbeatRef = useRef(0);

  useEffect(() => {
    if (!isCollapsed && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isCollapsed]);

  const { alerts = [] } = useData() || {};

  useEffect(() => {
    const sortedAlerts = [...alerts].sort((a, b) => {
      const ta = toTsMs(a?.ts_ms ?? a?.ts_iso ?? a?.ts) || 0;
      const tb = toTsMs(b?.ts_ms ?? b?.ts_iso ?? b?.ts) || 0;
      return tb - ta;
    });

    const seen = new Set();
    const alertLogs = [];
    for (const alert of sortedAlerts) {
      if (!alert || !alert.id || seen.has(alert.id)) continue;
      seen.add(alert.id);
      const symbol = String(alert?.symbol || alert?.product_id || "").toUpperCase();
      if (!symbol) continue;

      // Get alert type config with icon
      const alertType = alert?.alert_type || alert?.type;
      const alertConfig = getAlertConfig(alertType);

      // Get severity config
      const severityLc = String(alert?.severity_lc || alert?.severity || "info").toLowerCase();
      const severityConfig = getSeverityConfig(severityLc);
      const tone = severityConfig.tone || SEV_TONE[severityLc] || "tone-mint";

      const tsMs = toTsMs(alert?.ts_ms ?? alert?.ts_iso ?? alert?.ts);
      const timeStr = tsMs ? fmtTime(tsMs) : "--:--:--";
      const url = alert?.trade_url || spotUrl(alert, symbol);
      const title = alert?.title || "";
      const message = alert?.message || "";
      const text =
        title && message && message !== title ? `${title} — ${message}` : message || title || "Alert";

      // Map backend severity to display intensity
      // Backend uses formulas: CRITICAL (50%+ pump, 30%+ dump), HIGH (30%+ pump, 20%+ dump), MEDIUM (smaller moves)
      const severityUpper = String(alert?.severity || "").toUpperCase();
      let intensity = null;
      if (severityUpper === "CRITICAL") intensity = "EXTREME";
      else if (severityUpper === "HIGH") intensity = "VERY HIGH";
      else if (severityUpper === "MEDIUM") intensity = "HIGH";
      // INFO/LOW = no intensity label

      alertLogs.push({
        id: alert.id,
        time: timeStr,
        icon: alertConfig.icon,
        label: alertConfig.label,
        symbol,
        text,
        intensity,
        url,
        tone,
        color: alertConfig.color,
      });
      if (alertLogs.length >= 25) break;
    }

    if (alertLogs.length) {
      setLogs(alertLogs);
      return;
    }

    // Show heartbeat only once every 30 seconds when no alerts
    const nowMs = Date.now();
    if (nowMs - lastHeartbeatRef.current > 30000) {
      const systems = ["CACHE_SYNC", "SNAPSHOT_ENGINE", "COINBASE_POLL", "BANNER_LOOP"];
      const sys = systems[Math.floor(Math.random() * systems.length)];
      const timeStr = fmtTime(nowMs);
      const newLogs = [{
        id: `hb-${nowMs}`,
        time: timeStr,
        msg: `PING >> ${sys} heartbeat verified...`,
        tone: "tone-mint-dim",
      }];
      lastHeartbeatRef.current = nowMs;
      setLogs((prev) => [...prev, ...newLogs].slice(-30));
    }
  }, [alerts]);

  return (
    <div className="bh-anom" style={{ height: isCollapsed ? "38px" : "160px" }} data-collapsed={isCollapsed ? "1" : "0"}>
      <button
        type="button"
        className="bh-anom-head"
        onClick={() => setIsCollapsed((v) => !v)}
        aria-expanded={!isCollapsed}
      >
        <div className="bh-anom-title">
          INTELLIGENCE_LOG //{" "}
          <span className={`bh-anom-state ${isCollapsed ? "is-standby" : "is-live"}`}>{isCollapsed ? "STANDBY" : "LIVE"}</span>
        </div>
        <div className="bh-anom-meta">v4.0.2</div>
      </button>

      <div ref={scrollRef} className={`bh-anom-body ${isCollapsed ? "is-hidden" : ""}`}>
        {logs.map((log) => (
          <div key={log.id} className={`bh-anom-line bh-row ${log.tone || "tone-mint"}`} data-side="flat">
            <span className="bh-anom-time">[{log.time}]</span>
            <span className="bh-anom-msg">
              {log.msg ? (
                <span className="bh-anom-text">{log.msg}</span>
              ) : (
                <>
                  {log.icon && log.label ? (
                    <span className="bh-anom-tag" style={{ color: log.color }}>
                      {log.icon} {log.label}
                    </span>
                  ) : log.label ? (
                    <span className="bh-anom-tag">{log.label}</span>
                  ) : null}
                  {log.symbol ? <span className="bh-anom-sym">{log.symbol}</span> : null}
                  {log.intensity ? <span className="bh-anom-intensity">[{log.intensity}]</span> : null}
                  <span className="bh-anom-text">{log.text}</span>
                </>
              )}
            </span>
            {log.url ? (
              <a className="bh-anom-link" href={log.url} target="_blank" rel="noreferrer">
                Trade
              </a>
            ) : null}
          </div>
        ))}
        <div className="bh-anom-cursor">_</div>
      </div>
    </div>
  );
}
