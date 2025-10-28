import React from "react";

// source comes from the hook: "socket", "poll", or null
export default function ConnectionStatus({ source, timestamp }) {
  const offline = !source; // if no data yet
  const label = offline ? "OFFLINE" : source === "socket" ? "LIVE" : "POLL";

  const chipColor = offline
    ? "bg-bh.danger text-bh.textMain"
    : source === "socket"
    ? "bg-bh.chipBg border border-bh.gold text-bh.gold shadow-glowGold"
    : "bg-bh.chipBg border border-bh.purple text-bh.purple shadow-glowPurple";

  return (
    <div className="flex items-start gap-3 text-[10px] text-bh.textSoft font-mono">
      {timestamp && (
        <div className="hidden md:flex items-center bg-bh.chipBg/80 border border-bh.borderGold rounded-full px-2 py-1 leading-none shadow-glowGold">
          <span className="text-[10px] leading-none text-bh.textSoft">Latest:&nbsp;{timestamp}</span>
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          className="h-6 w-6 rounded-full bg-gradient-to-br from-bh.purple to-bh.purpleDim flex items-center justify-center text-[11px] text-bh.textMain font-bold shadow-glowPurple"
          onClick={() => {
            window.location.reload();
          }}
        >
          ↻
        </button>

        <div className="h-[6px] w-16 bg-bh.chipBg border border-bh.purple rounded-[3px] shadow-glowPurple relative">
          <div
            className={
              "absolute left-0 top-0 h-full rounded-[2px] " +
              (offline ? "bg-bh.danger" : source === "socket" ? "bg-bh.purple" : "bg-bh.purpleDim")
            }
            style={{
              width: offline ? "15%" : source === "socket" ? "90%" : "45%",
              transition: "width 0.3s ease",
            }}
          />
        </div>

        <div className={"rounded-full px-2 py-[2px] leading-none text-[10px] font-bold font-mono uppercase " + chipColor}>
          {label}
        </div>
      </div>
    </div>
  );
}
