// frontend/src/components/LiveStatusBar.jsx

function formatTime(dt) {
  if (!dt) return "—";
  // Handle both Date objects and timestamps
  const date = dt instanceof Date ? dt : new Date(dt);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function LiveStatusBar({ loading, error, lastUpdated, isValidating, heartbeatPulse, lastFetchTs }) {
  let status = "LIVE";
  let statusClass = "live-pill live-pill--ok";
  let label = "Streaming";

  if (error) {
    status = "RETRYING";
    statusClass = "live-pill live-pill--error";
    label = "Error fetching data";
  } else if (loading && !lastUpdated) {
    status = "CONNECTING";
    statusClass = "live-pill live-pill--connecting";
    label = "Initial load…";
  } else if (isValidating && lastUpdated) {
    // lastUpdated exists but we're mid-poll
    status = "UPDATING";
    statusClass = "live-pill live-pill--updating";
    label = "Refreshing…";
  }

  return (
    <div className="live-status-bar">
      <div className="live-status-left">
        <span className={statusClass}>
          <span className="live-dot" />
          {status}
        </span>
        <span className={`live-beat ${heartbeatPulse ? "is-active" : ""}`} data-active={heartbeatPulse ? "1" : "0"} aria-hidden />
        <span className="live-label">{label}</span>
      </div>
      <div className="live-status-right">
        <span className="live-updated-label">Last updated</span>
        <span className="live-updated-time">{formatTime(lastUpdated)}</span>
        <span className="live-updated-subline">{`Last fetch ${formatTime(lastFetchTs)}`}</span>
        {error ? (
          <span className="live-error-msg" title={error?.message || String(error)}>
            {String(error?.message || "Error fetching data").slice(0, 80)}
          </span>
        ) : null}
      </div>
    </div>
  );
}
