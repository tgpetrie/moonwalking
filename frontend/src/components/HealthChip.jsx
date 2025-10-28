import React from "react";

export default function HealthChip({ source }) {
  const mode =
    source === "socket"
      ? { label: "LIVE", cls: "bg-green-600/30 text-green-300" }
      : source === "poll"
      ? { label: "POLL", cls: "bg-yellow-600/30 text-yellow-200" }
      : { label: "INIT", cls: "bg-slate-600/40 text-slate-200" };

  return (
    <span
      className={
        "px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap " +
        mode.cls
      }
    >
      {mode.label}
    </span>
  );
}
