import { useEffect, useRef, useState } from "react";
import { deriveFreshness, formatAge } from "../../utils/boardFreshness.js";

const LABELS = {
  connecting: "Connecting",
  warming: "Warming baseline",
  live: "Live",
  delayed: "Delayed",
  stale: "Stale",
  offline: "Offline",
};

function describeAge(status, ageSeconds) {
  const age = formatAge(ageSeconds);
  if (status === "live" || status === "delayed") return age ? `${age} ago` : "";
  if (status === "stale") return age ? `${age} old · prices may have moved` : "Age unavailable";
  if (status === "offline") return age ? `last data ${age} ago · retrying` : "Retrying";
  return "";
}

export default function FreshnessStamp({ onStatusChange, previewAtMs, ...sample }) {
  const [nowMs, setNowMs] = useState(Date.now);
  const reportedStatus = useRef(null);

  useEffect(() => {
    if (previewAtMs !== undefined) return;
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [previewAtMs]);

  const { status, ageSeconds } = deriveFreshness({ ...sample, nowMs: previewAtMs ?? nowMs });

  useEffect(() => {
    if (!onStatusChange || reportedStatus.current === status) return;
    reportedStatus.current = status;
    onStatusChange(status);
  }, [status, onStatusChange]);

  const detail = describeAge(status, ageSeconds);
  return (
    <span className={`ui-freshness ui-freshness--${status}`} data-status={status}>
      <span className="ui-freshness__dot" aria-hidden="true" />
      <span className="ui-freshness__label" role="status">{LABELS[status]}</span>
      {detail && <span className="ui-freshness__detail">{detail}</span>}
    </span>
  );
}
